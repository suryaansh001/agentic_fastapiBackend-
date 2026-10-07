"""Subagent parent/child run management.

A subagent is a child ``AgentRun`` spawned by a parent
run. The relationship is engine-neutral: the parent
records ``child_run_ids`` and the child records
``parent_run_id``. Execution of the child is delegated
back to the ``AgentExecutionEngine`` — this service only
manages the durable parent/child records.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AgentDefinition, AgentRun, AgentTask


class SubagentError(Exception):
    """Raised when a subagent cannot be spawned."""


class SubagentService:
    """Create and query parent/child run relationships."""

    async def spawn(
        self,
        session: AsyncSession,
        *,
        parent_run_id: str,
        agent_id: str,
        input: Optional[dict] = None,
        initiated_by_id: Optional[str] = None,
    ) -> AgentRun:
        """Spawn a child run for ``agent_id`` under ``parent_run_id``.

        Creates the child ``AgentRun`` (with ``parent_run_id``
        set), a durable ``AgentTask`` the worker can claim,
        and appends the child id to the parent's
        ``child_run_ids``. Does NOT execute the child — the
        caller runs it via the engine.
        """
        result = await session.execute(
            select(AgentDefinition).where(
                AgentDefinition.id == agent_id
            )
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise SubagentError(f"unknown agent: {agent_id}")
        if agent.status != "LIVE":
            raise SubagentError(
                f"agent is not live: {agent_id} ({agent.status})"
            )

        child_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        child = AgentRun(
            id=child_id,
            agent_id=agent_id,
            version_id=agent.current_version_id or "",
            trigger_type="SUBAGENT",
            initiated_by_id=initiated_by_id,
            parent_run_id=parent_run_id,
            status="QUEUED",
            input=input,
        )
        session.add(child)
        session.add(
            AgentTask(
                id=task_id,
                agent_id=agent_id,
                kind="agent-run",
                reason="Subagent run",
                priority=500,
                budget=4,
                due_at=datetime.utcnow(),
                payload={"run_id": child_id},
            )
        )
        # Link parent -> child (denormalized for listing).
        parent = await session.get(AgentRun, parent_run_id)
        if parent is not None:
            children = list(parent.child_run_ids or [])
            if child_id not in children:
                children.append(child_id)
            parent.child_run_ids = children
        await session.commit()
        return child

    async def list_children(
        self, session: AsyncSession, run_id: str
    ) -> list[AgentRun]:
        """Return the direct children of ``run_id``."""
        result = await session.execute(
            select(AgentRun).where(AgentRun.parent_run_id == run_id)
        )
        return list(result.scalars().all())

    async def get_parent(
        self, session: AsyncSession, run_id: str
    ) -> Optional[AgentRun]:
        """Return the parent of ``run_id``, if any."""
        run = await session.get(AgentRun, run_id)
        if run is None or not run.parent_run_id:
            return None
        return await session.get(AgentRun, run.parent_run_id)


_subagent_service: Optional[SubagentService] = None


def get_subagent_service() -> SubagentService:
    global _subagent_service
    if _subagent_service is None:
        _subagent_service = SubagentService()
    return _subagent_service
