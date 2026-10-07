"""Durable human-in-the-loop approval service.

When the engine pauses at an approval gate, the gated
tool call is persisted as a PENDING ``AgentApproval``
row. Approvers decide through the approval API; the
decision is recorded durably and the engine resumes.

Authorization: the run's initiator or an organization
owner/admin may decide. Idempotency: a request that
repeats an ``idempotency_key`` returns the recorded
decision without re-processing.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select

from app.agent.access import AgentAccessService
from app.database.models import AgentApproval, AgentRun
from app.database.session import async_session_factory

PENDING = "PENDING"
APPROVED = "APPROVED"
DENIED = "DENIED"

DECISION_VALUES = {"approve": APPROVED, "deny": DENIED}


class ApprovalService:
    def __init__(self, access: Optional[AgentAccessService] = None):
        self.access = access or AgentAccessService()

    async def record_pending(
        self,
        run_id: str,
        interrupt_value: dict,
    ) -> Optional[AgentApproval]:
        """Persist a PENDING approval for a gated tool call.

        Idempotent per (run_id, tool_call_id): a second
        pause for the same call returns the existing row.
        """
        tool_call_id = interrupt_value.get("tool_call_id")
        if not tool_call_id:
            return None
        async with async_session_factory() as session:
            existing = await session.execute(
                select(AgentApproval).where(
                    AgentApproval.run_id == run_id,
                    AgentApproval.tool_call_id == tool_call_id,
                )
            )
            approval = existing.scalar_one_or_none()
            if approval is not None:
                return approval
            approval = AgentApproval(
                id=str(uuid.uuid4()),
                run_id=run_id,
                tool_call_id=tool_call_id,
                tool_name=interrupt_value.get("tool", ""),
                args=interrupt_value.get("args") or {},
                status=PENDING,
            )
            session.add(approval)
            await session.commit()
            return approval

    async def list_for_run(self, run_id: str) -> list[AgentApproval]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentApproval)
                .where(AgentApproval.run_id == run_id)
                .order_by(AgentApproval.created_at)
            )
            return list(result.scalars().all())

    async def _authorize(self, run: AgentRun, approver_id: str) -> None:
        if run.initiated_by_id == approver_id:
            return
        if await self.access.can_admin(approver_id):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the run initiator or an org admin may approve",
        )

    async def decide(
        self,
        run_id: str,
        tool_call_id: str,
        decision: str,
        approver_id: str,
        idempotency_key: Optional[str] = None,
    ) -> AgentApproval:
        """Record an approval decision.

        Idempotent: a repeated ``idempotency_key`` returns
        the already-recorded decision.
        """
        normalized = DECISION_VALUES.get(decision)
        if normalized is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="decision must be 'approve' or 'deny'",
            )
        async with async_session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Run not found",
                )
            await self._authorize(run, approver_id)

            if idempotency_key:
                existing = await session.execute(
                    select(AgentApproval).where(
                        AgentApproval.idempotency_key == idempotency_key
                    )
                )
                recorded = existing.scalar_one_or_none()
                if recorded is not None:
                    return recorded

            result = await session.execute(
                select(AgentApproval).where(
                    AgentApproval.run_id == run_id,
                    AgentApproval.tool_call_id == tool_call_id,
                )
            )
            approval = result.scalar_one_or_none()
            if approval is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Pending approval not found",
                )
            if approval.status != PENDING:
                return approval

            approval.status = normalized
            approval.approver_id = approver_id
            approval.idempotency_key = idempotency_key
            approval.decided_at = datetime.utcnow()
            await session.commit()
            return approval


_approval_service: Optional[ApprovalService] = None


def get_approval_service() -> ApprovalService:
    global _approval_service
    if _approval_service is None:
        _approval_service = ApprovalService()
    return _approval_service
