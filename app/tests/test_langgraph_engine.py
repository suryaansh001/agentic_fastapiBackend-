"""Phase 4 tests: LangGraph execution engine."""
import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agent.llm import LLMResponse, ToolCall
from app.agent.langgraph_engine import LangGraphEngine
from app.agent.run_lifecycle import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    WAITING_FOR_APPROVAL,
)
from app.agent.worker import AgentWorker, WorkerExecutor
from app.database.models import AgentRun, AgentRunEvent, AgentTask
from app.database.session import async_session_factory


async def _fresh_get(model, obj_id):
    """Read with a fresh session.

    The engine commits through its own session; the test's
    db_session identity map would return stale objects.
    """
    async with async_session_factory() as session:
        return await session.get(model, obj_id)


class FakeLLM:
    """Canned LLM responses; records every chat() call."""

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    async def chat(self, messages, tools=None, agent_id=None, run_id=None, **kwargs):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "agent_id": agent_id,
                "run_id": run_id,
            }
        )
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="final answer")


def _engine(responses=None):
    llm = FakeLLM(responses)
    engine = LangGraphEngine(llm, checkpointer=MemorySaver())
    return engine, llm


def _new_run(status=QUEUED, input=None, agent_id="agent_1"):
    return AgentRun(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        version_id="version_1",
        trigger_type="MANUAL",
        initiated_by_id="user_1",
        status=status,
        input=input or {"message": "list deals"},
    )


def _tool_response(tool_name, arguments, call_id="call_1"):
    return LLMResponse(
        content="",
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments=arguments)],
    )


# --- direct answers ------------------------------------------------------

@pytest.mark.asyncio
async def test_start_run_direct_answer(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine([LLMResponse(content="Hello there")])
    result = await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "hi"}, "user_1"
    )

    assert result["status"] == "SUCCEEDED"
    assert result["response"] == "Hello there"
    assert result["tools_called"] == []
    assert result["steps_executed"] == 1

    refreshed = await _fresh_get(AgentRun, run.id)
    assert refreshed.status == SUCCEEDED
    assert refreshed.summary == "Hello there"


@pytest.mark.asyncio
async def test_start_run_without_durable_run():
    # Chat path: no AgentRun row, synthetic thread id.
    engine, llm = _engine([LLMResponse(content="No run row")])
    result = await engine.start_run(
        str(uuid.uuid4()), "unified", "", {"message": "hi"}
    )
    assert result["status"] == "SUCCEEDED"
    assert result["response"] == "No run row"


@pytest.mark.asyncio
async def test_llm_receives_tool_schemas_and_context(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine([LLMResponse(content="ok")])
    await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "hi"}, "user_1"
    )

    call = llm.calls[0]
    assert call["tools"]  # function-calling schemas
    assert any(t["function"]["name"] == "query_crm" for t in call["tools"])
    assert call["agent_id"] == "agent_1"
    assert call["run_id"] == run.id
    # System prompt + user message
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["role"] == "user"


# --- safe tool execution ---------------------------------------------------

@pytest.mark.asyncio
async def test_start_run_executes_safe_tool(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine(
        [
            _tool_response("query_crm", {"operation": "list_deals", "params": {"limit": 5}}),
            LLMResponse(content="Here are the deals"),
        ]
    )
    result = await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "list deals"}, "user_1"
    )

    assert result["status"] == "SUCCEEDED"
    assert result["response"] == "Here are the deals"
    assert result["tools_called"] == ["query_crm"]
    assert result["steps_executed"] == 2

    refreshed = await _fresh_get(AgentRun, run.id)
    assert refreshed.status == SUCCEEDED

    # A tool_called event was written for the execution.
    async with async_session_factory() as session:
        events = (
            await session.execute(
                AgentRunEvent.__table__.select().where(
                    AgentRunEvent.run_id == run.id
                )
            )
        ).fetchall()
    types = [e.type for e in events]
    assert "status_changed" in types
    assert "tool_called" in types


@pytest.mark.asyncio
async def test_start_run_rejects_unknown_tool(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine(
        [
            _tool_response("does_not_exist", {}),
            LLMResponse(content="recovered"),
        ]
    )
    result = await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "x"}, "user_1"
    )
    # The unknown tool returns an error message but the run completes.
    assert result["status"] == "SUCCEEDED"
    assert result["response"] == "recovered"


# --- approval gate (HITL) --------------------------------------------------

@pytest.mark.asyncio
async def test_start_run_pauses_for_approval(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine(
        [_tool_response("create_crm_activity", {"type": "note", "body": "hi"})]
    )
    result = await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "note contact"}, "user_1"
    )

    assert result["status"] == "WAITING_FOR_APPROVAL"
    assert result["paused"] is True
    assert result["pending_tool"]["tool"] == "create_crm_activity"

    refreshed = await _fresh_get(AgentRun, run.id)
    assert refreshed.status == WAITING_FOR_APPROVAL

    # The gated tool did NOT execute.
    state = await engine.get_state(run.id)
    assert state["interrupted"] is True


@pytest.mark.asyncio
async def test_resume_run_approved(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine(
        [
            _tool_response("create_crm_activity", {"type": "note", "body": "hi"}),
            LLMResponse(content="Activity logged"),
        ]
    )
    await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "note contact"}, "user_1"
    )
    result = await engine.resume_run(run.id, {"approved": True})

    assert result["status"] == "SUCCEEDED"
    assert result["response"] == "Activity logged"

    refreshed = await _fresh_get(AgentRun, run.id)
    assert refreshed.status == SUCCEEDED


@pytest.mark.asyncio
async def test_resume_run_denied(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine(
        [
            _tool_response("write_file", {"path": "notes.txt", "content": "x"}),
            LLMResponse(content="Denied, nothing written"),
        ]
    )
    await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "write file"}, "user_1"
    )
    result = await engine.resume_run(run.id, {"approved": False})

    assert result["status"] == "SUCCEEDED"
    assert result["response"] == "Denied, nothing written"
    # The denial is visible to the LLM in the tool result.
    tool_messages = [
        m for m in llm.calls[-1]["messages"] if m.get("role") == "tool"
    ]
    assert tool_messages
    assert "approval denied" in tool_messages[0]["content"]


# --- cancellation and state -------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_run(db_session):
    run = _new_run(status=RUNNING)
    db_session.add(run)
    await db_session.commit()

    engine, llm = _engine()
    result = await engine.cancel_run(run.id)

    assert result["status"] == CANCELLED
    refreshed = await _fresh_get(AgentRun, run.id)
    assert refreshed.status == CANCELLED


@pytest.mark.asyncio
async def test_get_state_returns_none_for_unknown_thread():
    engine, llm = _engine()
    assert await engine.get_state(str(uuid.uuid4())) is None


@pytest.mark.asyncio
async def test_thread_continuation(db_session):
    thread_id = str(uuid.uuid4())
    engine, llm = _engine(
        [
            LLMResponse(content="first"),
            LLMResponse(content="second"),
        ]
    )
    await engine.start_run(thread_id, "unified", "", {"message": "one"})
    result = await engine.start_run(
        thread_id, "unified", "", {"message": "two"}
    )
    assert result["response"] == "second"
    # The second call saw the first turn's messages.
    second_call_messages = llm.calls[-1]["messages"]
    contents = [m["content"] for m in second_call_messages]
    assert "first" in contents
    assert "two" in contents


# --- worker integration ------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_executes_agent_run_task(db_session):
    run = _new_run(input={"message": "list deals"})
    task = AgentTask(
        id=str(uuid.uuid4()),
        agent_id="agent_1",
        kind="agent-run",
        reason="Manual run",
        priority=500,
        budget=4,
        due_at=__import__("datetime").datetime.utcnow(),
        payload={"run_id": run.id},
    )
    db_session.add_all([run, task])
    await db_session.commit()

    engine, llm = _engine([LLMResponse(content="worker did the work")])
    worker = AgentWorker(worker_id="w1", executor=WorkerExecutor(engine=engine))
    claimed = await worker.claim_next_task()
    assert claimed is not None

    await worker.process_task(claimed)

    # The worker transitioned the run QUEUED -> RUNNING -> SUCCEEDED.
    settled = await _fresh_get(AgentRun, run.id)
    assert settled.status == SUCCEEDED
    assert settled.summary == "worker did the work"
    settled_task = await _fresh_get(AgentTask, task.id)
    assert settled_task.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_worker_skips_non_agent_tasks(db_session):
    task = AgentTask(
        id=str(uuid.uuid4()),
        kind="identify",
        reason="contact created",
        priority=100,
        budget=4,
        due_at=__import__("datetime").datetime.utcnow(),
        payload={},
    )
    db_session.add(task)
    await db_session.commit()

    engine, llm = _engine()
    worker = AgentWorker(worker_id="w1", executor=WorkerExecutor(engine=engine))
    claimed = await worker.claim_next_task()
    # Bridge dispatch fails (no bridge reachable) but the task settles.
    await worker.process_task(claimed)
    settled = await _fresh_get(AgentTask, task.id)
    assert settled.status in ("SUCCEEDED", "FAILED")
