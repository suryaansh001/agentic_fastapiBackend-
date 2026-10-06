"""Phase 1 tests: AgentRun lifecycle state machine + durable task worker."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.agent.run_lifecycle import (
    QUEUED,
    RUNNING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    TERMINAL_STATUSES,
    InvalidTransition,
    can_transition,
    emit_event,
    next_sequence,
    settle_run,
    transition_run,
)
from app.agent.worker import AgentWorker, TaskResult
from app.database.models import AgentRun, AgentRunEvent, AgentTask
from app.database.session import async_session_factory


async def _fresh_get(model, obj_id):
    """Read an object from the database with a fresh session.

    The worker commits through its own session, so the test's db_session
    identity map would return stale in-memory objects.
    """
    async with async_session_factory() as session:
        return await session.get(model, obj_id)


def _new_run(agent_id: str = "agent_1") -> AgentRun:
    return AgentRun(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        version_id="version_1",
        trigger_type="MANUAL",
        initiated_by_id="user_1",
        status=QUEUED,
    )


def _new_task(**overrides) -> AgentTask:
    values = dict(
        id=str(uuid.uuid4()),
        agent_id="agent_1",
        kind="agent-run",
        reason="test",
        priority=100,
        budget=4,
        due_at=datetime.utcnow(),
        payload={},
    )
    values.update(overrides)
    return AgentTask(**values)


class StubExecutor:
    def __init__(self, result: TaskResult):
        self.result = result
        self.calls: list[str] = []

    async def execute(self, task: AgentTask) -> TaskResult:
        self.calls.append(task.id)
        return self.result


# --- lifecycle state machine -------------------------------------------------

@pytest.mark.asyncio
async def test_transition_queued_to_running(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    await transition_run(db_session, run, RUNNING)
    await db_session.commit()

    assert run.status == RUNNING
    assert run.started_at is not None
    events = (
        await db_session.execute(select(AgentRunEvent).where(AgentRunEvent.run_id == run.id))
    ).scalars().all()
    assert len(events) == 1
    assert events[0].type == "status_changed"
    assert events[0].data == {"from": QUEUED, "to": RUNNING}
    assert events[0].sequence == 1


@pytest.mark.asyncio
async def test_transition_rejects_invalid(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    with pytest.raises(InvalidTransition):
        await transition_run(db_session, run, SUCCEEDED)


@pytest.mark.asyncio
async def test_settle_run_records_terminal_status_and_result(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()
    await transition_run(db_session, run, RUNNING)
    await settle_run(db_session, run, SUCCEEDED, summary="done", result={"rows": 3})
    await db_session.commit()

    assert run.status == SUCCEEDED
    assert run.finished_at is not None
    assert run.summary == "done"
    assert run.result == {"rows": 3}
    sequences = [
        e.sequence
        for e in (
            await db_session.execute(select(AgentRunEvent).where(AgentRunEvent.run_id == run.id))
        ).scalars().all()
    ]
    assert sequences == [1, 2]


@pytest.mark.asyncio
async def test_event_sequences_increment(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    await emit_event(db_session, run.id, "note", {"n": 1})
    await emit_event(db_session, run.id, "note", {"n": 2})
    await db_session.commit()

    assert await next_sequence(db_session, run.id) == 3


def test_transition_table_rules():
    assert can_transition(QUEUED, RUNNING)
    assert can_transition(QUEUED, CANCELLED)
    assert can_transition(RUNNING, SUCCEEDED)
    assert not can_transition(QUEUED, SUCCEEDED)
    assert not can_transition(SUCCEEDED, RUNNING)
    for terminal in TERMINAL_STATUSES:
        assert not can_transition(terminal, RUNNING)


# --- worker ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_claims_task_with_lease(db_session):
    task = _new_task()
    db_session.add(task)
    await db_session.commit()

    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True)))
    claimed = await worker.claim_next_task()

    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status == "RUNNING"
    assert claimed.attempts == 1
    assert claimed.leased_until is not None
    assert claimed.leased_until > datetime.utcnow()


@pytest.mark.asyncio
async def test_worker_claim_returns_none_when_queue_empty(db_session):
    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True)))
    assert await worker.claim_next_task() is None


@pytest.mark.asyncio
async def test_worker_skips_future_due_tasks(db_session):
    task = _new_task(due_at=datetime.utcnow() + timedelta(hours=1))
    db_session.add(task)
    await db_session.commit()

    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True)))
    assert await worker.claim_next_task() is None


@pytest.mark.asyncio
async def test_worker_prioritizes_higher_priority(db_session):
    low = _new_task(priority=10)
    high = _new_task(priority=900)
    db_session.add_all([low, high])
    await db_session.commit()

    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True)))
    claimed = await worker.claim_next_task()
    assert claimed is not None
    assert claimed.id == high.id


@pytest.mark.asyncio
async def test_worker_process_task_settles_run_and_task(db_session):
    run = _new_run()
    task = _new_task(payload={"run_id": run.id})
    db_session.add_all([run, task])
    await db_session.commit()

    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True, summary="ok")))
    await worker.process_task(task)

    refreshed_run = await _fresh_get(AgentRun, run.id)
    refreshed_task = await _fresh_get(AgentTask, task.id)
    assert refreshed_run.status == SUCCEEDED
    assert refreshed_task.status == "SUCCEEDED"
    assert refreshed_task.finished_at is not None


@pytest.mark.asyncio
async def test_worker_process_task_marks_failure(db_session):
    run = _new_run()
    task = _new_task(payload={"run_id": run.id})
    db_session.add_all([run, task])
    await db_session.commit()

    worker = AgentWorker(
        worker_id="w1",
        executor=StubExecutor(TaskResult(ok=False, error="boom")),
    )
    await worker.process_task(task)

    refreshed_run = await _fresh_get(AgentRun, run.id)
    assert refreshed_run.status == FAILED
    assert refreshed_run.error_message == "boom"


@pytest.mark.asyncio
async def test_worker_recovers_stale_lease(db_session):
    task = _new_task(
        status="RUNNING",
        attempts=1,
        leased_until=datetime.utcnow() - timedelta(seconds=1),
    )
    db_session.add(task)
    await db_session.commit()

    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True)))
    recovered = await worker.recover_stale_leases()

    assert recovered == 1
    refreshed = await _fresh_get(AgentTask, task.id)
    assert refreshed.status == "PENDING"
    assert refreshed.leased_until is None


@pytest.mark.asyncio
async def test_worker_fails_task_after_max_attempts(db_session):
    task = _new_task(
        status="RUNNING",
        attempts=3,
        leased_until=datetime.utcnow() - timedelta(seconds=1),
    )
    db_session.add(task)
    await db_session.commit()

    worker = AgentWorker(worker_id="w1", executor=StubExecutor(TaskResult(ok=True)))
    await worker.recover_stale_leases()

    refreshed = await _fresh_get(AgentTask, task.id)
    assert refreshed.status == "FAILED"
    assert refreshed.finished_at is not None


@pytest.mark.asyncio
async def test_worker_claim_is_idempotent_across_workers(db_session):
    task = _new_task()
    db_session.add(task)
    await db_session.commit()

    worker_a = AgentWorker(worker_id="a", executor=StubExecutor(TaskResult(ok=True)))
    worker_b = AgentWorker(worker_id="b", executor=StubExecutor(TaskResult(ok=True)))

    claimed_a = await worker_a.claim_next_task()
    claimed_b = await worker_b.claim_next_task()

    assert claimed_a is not None
    # The claimed task is now RUNNING, so a second worker must not claim it.
    assert claimed_b is None
