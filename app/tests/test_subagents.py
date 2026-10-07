"""Phase 7 tests: subagent parent/child runs."""
import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agent.llm import LLMResponse, ToolCall
from app.agent.langgraph_engine import LangGraphEngine
from app.agent.run_lifecycle import QUEUED, RUNNING
from app.agent.subagents import (
    SubagentError,
    SubagentService,
    get_subagent_service,
)
from app.agent.tools.registry import (
    MAX_SUBAGENT_DEPTH,
    ToolContext,
    default_registry,
)
from app.database.models import (
    AgentDefinition,
    AgentDefinitionStatus,
    AgentRun,
    AgentTask,
)
from app.database.session import async_session_factory


async def _fresh_get(model, obj_id):
    async with async_session_factory() as session:
        return await session.get(model, obj_id)


def _new_run(status=QUEUED, input=None, agent_id="agent_1"):
    return AgentRun(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        version_id="version_1",
        trigger_type="MANUAL",
        initiated_by_id="user_1",
        status=status,
        input=input or {"message": "do things"},
    )


async def _seed_live_agent(
    session, agent_id="agent_2", version_id="version_2"
):
    agent = AgentDefinition(
        id=agent_id,
        name="Helper Agent",
        status=AgentDefinitionStatus.LIVE,
        created_by_id="user_1",
        current_version_id=version_id,
    )
    session.add(agent)
    await session.commit()
    return agent


# --- SubagentService --------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_creates_child_with_parent_link(db_session):
    await _seed_live_agent(db_session)
    parent = _new_run()
    db_session.add(parent)
    await db_session.commit()

    child = await get_subagent_service().spawn(
        db_session,
        parent_run_id=parent.id,
        agent_id="agent_2",
        input={"message": "help"},
        initiated_by_id="user_1",
    )

    assert child.parent_run_id == parent.id
    assert child.agent_id == "agent_2"
    assert child.version_id == "version_2"
    assert child.trigger_type == "SUBAGENT"
    assert child.status == QUEUED
    # Parent's denormalized child list is updated.
    fresh_parent = await _fresh_get(AgentRun, parent.id)
    assert fresh_parent.child_run_ids == [child.id]
    # A durable task was created for the child.
    async with async_session_factory() as session:
        from sqlalchemy import select

        tasks = (
            (
                await session.execute(
                    select(AgentTask).where(
                        AgentTask.agent_id == "agent_2"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert any(t.payload.get("run_id") == child.id for t in tasks)


@pytest.mark.asyncio
async def test_list_children(db_session):
    await _seed_live_agent(db_session)
    parent = _new_run()
    db_session.add(parent)
    await db_session.commit()

    svc = SubagentService()
    child_a = await svc.spawn(
        db_session,
        parent_run_id=parent.id,
        agent_id="agent_2",
    )
    child_b = await svc.spawn(
        db_session,
        parent_run_id=parent.id,
        agent_id="agent_2",
    )

    children = await svc.list_children(db_session, parent.id)
    assert {c.id for c in children} == {child_a.id, child_b.id}


@pytest.mark.asyncio
async def test_get_parent(db_session):
    await _seed_live_agent(db_session)
    parent = _new_run()
    db_session.add(parent)
    await db_session.commit()

    child = await get_subagent_service().spawn(
        db_session,
        parent_run_id=parent.id,
        agent_id="agent_2",
    )

    fetched = await get_subagent_service().get_parent(
        db_session, child.id
    )
    assert fetched is not None
    assert fetched.id == parent.id
    # A top-level run has no parent.
    assert (
        await get_subagent_service().get_parent(
            db_session, parent.id
        )
        is None
    )


@pytest.mark.asyncio
async def test_spawn_unknown_agent_raises(db_session):
    parent = _new_run()
    db_session.add(parent)
    await db_session.commit()

    with pytest.raises(SubagentError):
        await get_subagent_service().spawn(
            db_session,
            parent_run_id=parent.id,
            agent_id="does_not_exist",
        )


@pytest.mark.asyncio
async def test_spawn_non_live_agent_raises(db_session):
    agent = AgentDefinition(
        id="draft_agent",
        name="Draft",
        status=AgentDefinitionStatus.DRAFT,
        created_by_id="user_1",
    )
    db_session.add(agent)
    parent = _new_run()
    db_session.add(parent)
    await db_session.commit()

    with pytest.raises(SubagentError):
        await get_subagent_service().spawn(
            db_session,
            parent_run_id=parent.id,
            agent_id="draft_agent",
        )


# --- spawn_subagent tool ----------------------------------------------


@pytest.mark.asyncio
async def test_spawn_subagent_tool_runs_executor():
    registry = default_registry()
    captured = {}

    async def fake_executor(
        parent_run_id, user_id, agent_id, input
    ):
        captured["parent"] = parent_run_id
        captured["user"] = user_id
        captured["agent"] = agent_id
        captured["input"] = input
        return {"run_id": "child_1", "status": "SUCCEEDED"}

    ctx = ToolContext(
        run_id="parent_1",
        user_id="user_1",
        subagent_executor=fake_executor,
    )

    result = await registry.execute(
        "spawn_subagent",
        {"agentId": "agent_2", "input": {"message": "go"}},
        ctx,
    )

    assert result["success"] is True
    assert result["run_id"] == "child_1"
    assert captured == {
        "parent": "parent_1",
        "user": "user_1",
        "agent": "agent_2",
        "input": {"message": "go"},
    }


@pytest.mark.asyncio
async def test_spawn_subagent_tool_without_executor():
    registry = default_registry()
    ctx = ToolContext(run_id="parent_1", user_id="user_1")

    result = await registry.execute(
        "spawn_subagent", {"agentId": "agent_2"}, ctx
    )

    assert result["success"] is False
    assert "not available" in result["error"]


@pytest.mark.asyncio
async def test_spawn_subagent_tool_depth_limit():
    registry = default_registry()

    async def fake_executor(*args, **kwargs):
        return {"run_id": "child_1"}

    ctx = ToolContext(
        run_id="parent_1",
        user_id="user_1",
        depth=MAX_SUBAGENT_DEPTH,
        subagent_executor=fake_executor,
    )

    result = await registry.execute(
        "spawn_subagent", {"agentId": "agent_2"}, ctx
    )

    assert result["success"] is False
    assert "depth" in result["error"]


# --- end-to-end: parent spawns a child ------------------------------


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    async def chat(
        self, messages, tools=None, agent_id=None,
        run_id=None, **kwargs,
    ):
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="final answer")


def _tool_response(tool_name, arguments, call_id="call_1"):
    return LLMResponse(
        content="",
        tool_calls=[
            ToolCall(id=call_id, name=tool_name, arguments=arguments)
        ],
    )


@pytest.mark.asyncio
async def test_parent_run_spawns_child_run(db_session):
    await _seed_live_agent(db_session)
    parent = _new_run()
    db_session.add(parent)
    await db_session.commit()

    # 1st: parent asks to spawn agent_2.
    # 2nd: the child answers directly.
    # 3rd: the parent answers directly.
    llm = FakeLLM(
        [
            _tool_response(
                "spawn_subagent",
                {"agentId": "agent_2", "input": {"message": "go"}},
            ),
            LLMResponse(content="child done"),
            LLMResponse(content="parent done"),
        ]
    )
    engine = LangGraphEngine(llm, checkpointer=MemorySaver())

    result = await engine.start_run(
        parent.id, "agent_1", "version_1",
        {"message": "delegate"}, "user_1",
    )

    assert result["status"] == "SUCCEEDED"
    # A child run was created under the parent.
    async with async_session_factory() as session:
        from sqlalchemy import select

        children = (
            (
                await session.execute(
                    select(AgentRun).where(
                        AgentRun.parent_run_id == parent.id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(children) == 1
    child = children[0]
    assert child.agent_id == "agent_2"
    assert child.trigger_type == "SUBAGENT"
    # The child ran to completion.
    assert child.status == "SUCCEEDED"
    # The parent's denormalized list points at the child.
    fresh_parent = await _fresh_get(AgentRun, parent.id)
    assert fresh_parent.child_run_ids == [child.id]
