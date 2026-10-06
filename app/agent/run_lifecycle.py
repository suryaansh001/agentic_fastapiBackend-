"""Durable AgentRun lifecycle: validated state machine plus event sourcing.

Every status change goes through :func:`transition_run`, which rejects
invalid transitions and records an ``agentRunEvent`` row. The run's
history is therefore reconstructable from the database after a crash,
and the worker can resume or settle runs that were in flight.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AgentRun, AgentRunEvent, AgentRunStatus

QUEUED = AgentRunStatus.QUEUED.value
RUNNING = AgentRunStatus.RUNNING.value
WAITING_FOR_APPROVAL = AgentRunStatus.WAITING_FOR_APPROVAL.value
SUCCEEDED = AgentRunStatus.SUCCEEDED.value
FAILED = AgentRunStatus.FAILED.value
CANCELLED = AgentRunStatus.CANCELLED.value

TERMINAL_STATUSES = frozenset({SUCCEEDED, FAILED, CANCELLED})

# Allowed transitions. Anything not listed is rejected by transition_run.
TRANSITIONS = {
    QUEUED: frozenset({RUNNING, CANCELLED}),
    RUNNING: frozenset({WAITING_FOR_APPROVAL, SUCCEEDED, FAILED, CANCELLED}),
    WAITING_FOR_APPROVAL: frozenset({RUNNING, FAILED, CANCELLED}),
    SUCCEEDED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}


class InvalidTransition(Exception):
    def __init__(self, current: str, new: str):
        super().__init__(f"Invalid AgentRun transition {current} -> {new}")
        self.current = current
        self.new = new


def can_transition(current: str, new: str) -> bool:
    return new in TRANSITIONS.get(current, frozenset())


async def next_sequence(session: AsyncSession, run_id: str) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(AgentRunEvent.sequence), 0)).where(
            AgentRunEvent.run_id == run_id
        )
    )
    return int(result.scalar_one() or 0) + 1


async def emit_event(
    session: AsyncSession, run_id: str, event_type: str, data: Optional[dict] = None
) -> AgentRunEvent:
    event = AgentRunEvent(
        id=str(uuid.uuid4()),
        run_id=run_id,
        sequence=await next_sequence(session, run_id),
        type=event_type,
        data=data or {},
        emitted_at=datetime.utcnow(),
    )
    session.add(event)
    return event


async def transition_run(
    session: AsyncSession,
    run: AgentRun,
    new_status: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> AgentRun:
    """Move a run to a new status, recording a status_changed event."""
    if not can_transition(run.status, new_status):
        raise InvalidTransition(run.status, new_status)
    previous = run.status
    run.status = new_status
    if new_status == RUNNING and run.started_at is None:
        run.started_at = datetime.utcnow()
    if new_status in TERMINAL_STATUSES:
        run.finished_at = datetime.utcnow()
        if error_code:
            run.error_code = error_code
        if error_message:
            run.error_message = error_message
    await emit_event(
        session,
        run.id,
        "status_changed",
        {"from": previous, "to": new_status},
    )
    return run


async def settle_run(
    session: AsyncSession,
    run: AgentRun,
    status: str,
    summary: Optional[str] = None,
    result: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> AgentRun:
    """Settle a run in a terminal status, attaching summary/result."""
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"settle_run requires a terminal status, got {status}")
    await transition_run(
        session, run, status, error_message=error_message
    )
    if summary:
        run.summary = summary
    if result is not None:
        run.result = result
    return run
