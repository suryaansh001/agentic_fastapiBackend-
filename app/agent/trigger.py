import httpx
from datetime import datetime, timedelta
from typing import Optional
from app.database.session import async_session_factory
from app.database.models import AgentTask, AgentDefinition
from sqlalchemy import select, func, desc, update
from app.agent.bridge import bridge
from app.agent.visibility import CANCELLABLE_RUN_STATUSES, AGENT_DISPATCH


class AgentTriggerService:
    def __init__(self):
        self._cancellations_delivered = set()

    async def company_created(self, company_id: str, reason: str = "New company"):
        await self._enqueue(company_id=company_id, kind="brand", reason=reason, priority=900, budget=2)
        await self._enqueue(company_id=company_id, kind="company-profile", reason=reason, priority=40, budget=4)

    async def contact_created(self, contact_id: str, reason: str, required: bool = False) -> bool:
        return await self._enqueue(contact_id=contact_id, kind="identify", reason=reason, priority=100, budget=4, required=required)

    async def meeting_soon(self, contact_id: str, when: datetime):
        await self._enqueue(contact_id=contact_id, kind="meeting-prep", reason=f"Meeting on {when.strftime('%b %d')}", priority=200, budget=10)

    async def workspace_changed(self, website: str, reason: str):
        await self._enqueue(kind="workspace-profile", reason=reason, priority=500, budget=4)

    async def backfill(self, kind: str, reason: str, contact_ids: Optional[list[str]] = None, company_ids: Optional[list[str]] = None, budget: Optional[int] = None):
        ids = list(set((contact_ids or []) + (company_ids or [])))
        if not ids:
            return {"queued": 0, "alreadyQueued": 0}
        subject = "contactId" if contact_ids else "companyId"
        await self._enqueue_batch(ids, kind, reason, priority=50, budget=budget or 4, subject=subject)
        return {"queued": len(ids), "alreadyQueued": 0}

    async def field_backfill_records(self, entity: str, keys: list[str], ids: list[str], reason: str):
        if not ids or not keys:
            return {"queued": 0, "merged": 0}
        queued = 0
        for record_id in ids:
            async with async_session_factory() as session:
                existing = await session.execute(
                    select(AgentTask).where(
                        AgentTask.kind == "field-backfill",
                        AgentTask.finished_at.is_(None),
                        getattr(AgentTask, f"{entity[:-1] if entity.endswith('s') else entity}_id") == record_id,
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue
                await session.add(AgentTask(
                    contact_id=record_id if entity == "contact" else None,
                    company_id=record_id if entity == "company" else None,
                    kind="field-backfill",
                    reason=reason,
                    priority=8,
                    budget=8,
                    due_at=datetime.utcnow(),
                    payload={"entity": entity, "keys": keys},
                ))
                await session.commit()
                queued += 1
        return {"queued": queued, "merged": 0}

    def poke(self):
        self.poke_route("/internal/crm/dispatch")
        self.deployed_agent_run_queued()
        self.builder_conversation_queued()

    def poke_route(self, path: str):
        pass

    def deployed_agent_run_queued(self):
        pass

    def builder_conversation_queued(self):
        pass

    async def drain_queues(self):
        self.poke()

    async def _enqueue(self, contact_id: Optional[str] = None, company_id: Optional[str] = None, deal_id: Optional[str] = None, kind: str = "", reason: str = "", priority: int = 50, budget: int = 2, required: bool = False) -> bool:
        try:
            async with async_session_factory() as session:
                await session.begin_nested()
                existing = await session.execute(
                    select(AgentTask).where(
                        AgentTask.kind == kind,
                        AgentTask.finished_at.is_(None),
                        AgentTask.contact_id == contact_id,
                        AgentTask.company_id == company_id,
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    return False
                session.add(AgentTask(
                    contact_id=contact_id, company_id=company_id, deal_id=deal_id,
                    kind=kind, reason=reason, priority=priority, budget=budget,
                    due_at=datetime.utcnow(),
                ))
                await session.commit()
                self.poke()
                return True
        except Exception as e:
            if required:
                raise
            return False

    async def _enqueue_batch(self, ids: list[str], kind: str, reason: str, priority: int, budget: int, subject: str):
        taken = set()
        fresh_ids = []
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentTask).where(
                    AgentTask.kind == kind,
                    AgentTask.finished_at.is_(None),
                    AgentTask.contact_id.in_(ids) if subject == "contactId" else AgentTask.company_id.in_(ids),
                )
            )
            taken = set()
            for t in result.scalars().all():
                taken.add(t.contact_id or t.company_id)
            fresh_ids = [i for i in ids if i not in taken]
        if fresh_ids:
            async with async_session_factory() as session:
                await session.begin_nested()
                for rid in fresh_ids:
                    session.add(AgentTask(
                        contact_id=rid if subject == "contactId" else None,
                        company_id=rid if subject == "companyId" else None,
                        kind=kind, reason=reason, priority=priority, budget=budget,
                        due_at=datetime.utcnow(),
                    ))
                await session.commit()
        self.poke()

    async def redeliver_cancellations(self):
        since = datetime.utcnow() - timedelta(milliseconds=AGENT_DISPATCH.cancel.redeliverWithinMs)
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentTask).where(
                    AgentTask.status == "CANCELLED",
                    AgentTask.created_at >= since,
                ).limit(AGENT_DISPATCH.cancel.redeliverBatch)
            )
            for task in result.scalars().all():
                if task.id not in self._cancellations_delivered:
                    await self._post_task_to_agent(task)
                    self._cancellations_delivered.add(task.id)

    async def _post_task_to_agent(self, task: AgentTask):
        bridge_instance = bridge()
        if bridge_instance:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        bridge_instance.url_for("/internal/crm/dispatch"),
                        json={"taskId": task.id},
                        timeout=5.0,
                    )
            except Exception:
                pass