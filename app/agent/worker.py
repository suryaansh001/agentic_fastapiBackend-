"""Durable agent task worker.

Claims ``agentTask`` rows with ``SELECT ... FOR UPDATE SKIP LOCKED`` so
multiple workers can share a queue without double-processing, leases each
claimed task (with expiry) so a crashed worker's tasks are recovered, and
settles both the task and its parent ``AgentRun`` (linked via
``task.payload["run_id"]``).

Execution is delegated to a pluggable ``TaskExecutor``. The default
:class:`BridgeTaskExecutor` dispatches to the bridge service (the current
runtime); Phase 4 swaps in the LangGraph-backed engine executor.

Run a dedicated worker process with::

    python -m app.agent.worker
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Protocol

import httpx
from sqlalchemy import select

from app.agent.bridge import bridge
from app.agent.run_lifecycle import (
    QUEUED,
    RUNNING,
    SUCCEEDED,
    FAILED,
    TERMINAL_STATUSES,
    transition_run,
)
from app.database.models import AgentTask, AgentRun
from app.database.session import async_session_factory

LEASE_SECONDS = 300
MAX_ATTEMPTS = 3
POLL_INTERVAL_SECONDS = 1.0

CLAIMABLE_STATUSES = ("PENDING", "QUEUED")


class TaskResult:
    def __init__(self, ok: bool, summary: str = "", error: Optional[str] = None):
        self.ok = ok
        self.summary = summary
        self.error = error


class TaskExecutor(Protocol):
    async def execute(self, task: AgentTask) -> TaskResult:
        ...


class BridgeTaskExecutor:
    """Default executor: POST the task to the bridge dispatch endpoint."""

    async def execute(self, task: AgentTask) -> TaskResult:
        bridge_instance = bridge()
        if bridge_instance is None:
            return TaskResult(ok=False, error="bridge not configured")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    bridge_instance.url_for("/internal/crm/dispatch"),
                    json={"taskId": task.id},
                    headers=bridge_instance.headers(),
                    timeout=5.0,
                )
        except Exception as exc:
            return TaskResult(ok=False, error=str(exc))
        if response.status_code >= 400:
            return TaskResult(
                ok=False, error=f"bridge returned {response.status_code}"
            )
        return TaskResult(ok=True, summary=f"dispatched to bridge ({response.status_code})")


class AgentWorker:
    def __init__(
        self,
        worker_id: str,
        executor: Optional[TaskExecutor] = None,
        lease_seconds: int = LEASE_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self.worker_id = worker_id
        self.executor = executor or BridgeTaskExecutor()
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self._running = False

    async def claim_next_task(self) -> Optional[AgentTask]:
        """Claim the highest-priority due task, or None if the queue is empty.

        The claim is atomic: rows are locked with FOR UPDATE SKIP LOCKED so
        concurrent workers never claim the same task.
        """
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentTask)
                .where(AgentTask.status.in_(CLAIMABLE_STATUSES))
                .where(AgentTask.due_at <= datetime.utcnow())
                .order_by(
                    AgentTask.priority.desc(),
                    AgentTask.due_at,
                    AgentTask.created_at,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            task = result.scalar_one_or_none()
            if task is None:
                return None
            task.status = "RUNNING"
            task.attempts = (task.attempts or 0) + 1
            task.leased_until = datetime.utcnow() + timedelta(seconds=self.lease_seconds)
            await session.commit()
            return task

    async def recover_stale_leases(self) -> int:
        """Requeue tasks whose lease expired (worker died mid-task).

        Tasks that exceeded MAX_ATTEMPTS are settled as FAILED instead of
        being retried forever.
        """
        now = datetime.utcnow()
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentTask).where(AgentTask.status == "RUNNING").where(
                    AgentTask.leased_until < now
                )
            )
            stale = result.scalars().all()
            recovered = 0
            for task in stale:
                if (task.attempts or 0) >= self.max_attempts:
                    task.status = "FAILED"
                    task.finished_at = now
                else:
                    task.status = "PENDING"
                    task.leased_until = None
                recovered += 1
            if recovered:
                await session.commit()
        return recovered

    async def settle_task(
        self,
        task_id: str,
        ok: bool,
        summary: str = "",
        error: Optional[str] = None,
    ) -> None:
        """Mark a task finished and settle its parent run, if any."""
        async with async_session_factory() as session:
            task = (
                await session.execute(select(AgentTask).where(AgentTask.id == task_id))
            ).scalar_one_or_none()
            if task is None:
                return
            task.status = "SUCCEEDED" if ok else "FAILED"
            task.finished_at = datetime.utcnow()
            run_id = (task.payload or {}).get("run_id")
            if run_id:
                run = await session.get(AgentRun, run_id)
                if run and run.status not in TERMINAL_STATUSES:
                    await transition_run(
                        session,
                        run,
                        SUCCEEDED if ok else FAILED,
                        error_message=error,
                    )
            await session.commit()

    async def process_task(self, task: AgentTask) -> None:
        run_id = (task.payload or {}).get("run_id")
        if run_id:
            async with async_session_factory() as session:
                run = await session.get(AgentRun, run_id)
                if run and run.status == QUEUED:
                    await transition_run(session, run, RUNNING)
                    await session.commit()
        try:
            result = await self.executor.execute(task)
        except Exception as exc:  # executor must never kill the worker loop
            result = TaskResult(ok=False, error=str(exc))
        await self.settle_task(task.id, result.ok, result.summary, result.error)

    async def run_loop(self, poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
        self._running = True
        while self._running:
            try:
                await self.recover_stale_leases()
                task = await self.claim_next_task()
                if task is None:
                    await asyncio.sleep(poll_interval)
                    continue
                await self.process_task(task)
            except asyncio.CancelledError:
                self._running = False
                raise
            except Exception:
                await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        self._running = False


_worker: Optional[AgentWorker] = None


class WorkerExecutor:
    """Routes tasks to the right executor.

    Tasks carrying a ``run_id`` in their payload are agent runs and
    execute through the :class:`AgentExecutionEngine`; everything
    else (CRM dispatch tasks) goes to the bridge as before.
    """

    def __init__(self, engine=None):
        self._engine = engine
        self.bridge = BridgeTaskExecutor()

    async def execute(self, task: AgentTask) -> TaskResult:
        run_id = (task.payload or {}).get("run_id")
        if run_id:
            return await self._execute_run(task, run_id)
        return await self.bridge.execute(task)

    async def _execute_run(self, task: AgentTask, run_id: str) -> TaskResult:
        from app.agent.engine import AgentExecutionEngine
        from app.agent.langgraph_engine import get_engine
        from app.agent.run_lifecycle import RUNNING

        engine: AgentExecutionEngine = self._engine or get_engine()
        try:
            async with async_session_factory() as session:
                run = await session.get(AgentRun, run_id)
            if run is None:
                return TaskResult(ok=False, error=f"run {run_id} not found")
            if run.status != RUNNING:
                return TaskResult(ok=True, summary=f"run already {run.status}")
            await engine.start_run(
                run_id,
                run.agent_id,
                run.version_id,
                run.input or {},
                run.initiated_by_id,
            )
            return TaskResult(ok=True, summary="agent run executed")
        except Exception as exc:
            return TaskResult(ok=False, error=str(exc))


def get_worker() -> AgentWorker:
    global _worker
    if _worker is None:
        import socket

        _worker = AgentWorker(
            worker_id=f"worker-{socket.gethostname()}",
            executor=WorkerExecutor(),
        )
    return _worker


if __name__ == "__main__":
    worker = get_worker()
    try:
        asyncio.run(worker.run_loop())
    except KeyboardInterrupt:
        worker.stop()
