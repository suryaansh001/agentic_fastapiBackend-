"""Phase 5 tests: durable human-in-the-loop approvals."""
import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agent.approval import (
    APPROVED,
    DENIED,
    PENDING,
    ApprovalService,
    get_approval_service,
)
from app.agent.langgraph_engine import LangGraphEngine
from app.agent.llm import LLMResponse, ToolCall
from app.agent.run_lifecycle import QUEUED, RUNNING, SUCCEEDED, WAITING_FOR_APPROVAL
from app.database.models import AgentApproval, AgentRun
from app.database.session import async_session_factory
from app.tests.test_fixtures import (
    auth_headers,
    create_test_app,
    mint_token,
)


class FakeLLM:
    def __init__(self, responses=None):
        self.responses = list(responses or [])

    async def chat(self, messages, tools=None, agent_id=None, run_id=None, **kwargs):
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="final")


def _new_run(initiated_by="user_1", status=QUEUED):
    return AgentRun(
        id=str(uuid.uuid4()),
        agent_id="agent_1",
        version_id="version_1",
        trigger_type="MANUAL",
        initiated_by_id=initiated_by,
        status=status,
        input={"message": "note contact"},
    )


async def _fresh_get(model, obj_id):
    async with async_session_factory() as session:
        return await session.get(model, obj_id)


# --- service: record_pending ---------------------------------------

@pytest.mark.asyncio
async def test_record_pending_creates_approval(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    service = get_approval_service()
    approval = await service.record_pending(
        run.id,
        {"tool_call_id": "call_1", "tool": "write_file", "args": {"path": "a.txt"}},
    )

    assert approval is not None
    assert approval.run_id == run.id
    assert approval.tool_call_id == "call_1"
    assert approval.tool_name == "write_file"
    assert approval.status == PENDING


@pytest.mark.asyncio
async def test_record_pending_idempotent(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    service = get_approval_service()
    first = await service.record_pending(
        run.id, {"tool_call_id": "call_1", "tool": "write_file", "args": {}}
    )
    second = await service.record_pending(
        run.id, {"tool_call_id": "call_1", "tool": "write_file", "args": {}}
    )

    assert first.id == second.id


@pytest.mark.asyncio
async def test_record_pending_ignores_missing_tool_call_id(db_session):
    run = _new_run()
    db_session.add(run)
    await db_session.commit()

    service = get_approval_service()
    approval = await service.record_pending(run.id, {"tool": "write_file"})
    assert approval is None


# --- service: decide ------------------------------------------------

@pytest.mark.asyncio
async def test_decide_approve_by_initiator(db_session):
    run = _new_run(initiated_by="user_1")
    approval_row = AgentApproval(
        id="appr_1",
        run_id=run.id,
        tool_call_id="call_1",
        tool_name="write_file",
        args={"path": "a.txt"},
        status=PENDING,
    )
    db_session.add_all([run, approval_row])
    await db_session.commit()

    service = get_approval_service()
    result = await service.decide(
        run.id, "call_1", "approve", "user_1", idempotency_key="key_1"
    )

    assert result.status == APPROVED
    assert result.approver_id == "user_1"
    assert result.idempotency_key == "key_1"
    assert result.decided_at is not None


@pytest.mark.asyncio
async def test_decide_deny(db_session):
    run = _new_run(initiated_by="user_1")
    approval_row = AgentApproval(
        id="appr_1",
        run_id=run.id,
        tool_call_id="call_1",
        tool_name="write_file",
        status=PENDING,
    )
    db_session.add_all([run, approval_row])
    await db_session.commit()

    service = get_approval_service()
    result = await service.decide(run.id, "call_1", "deny", "user_1")

    assert result.status == DENIED


@pytest.mark.asyncio
async def test_decide_idempotent(db_session):
    run = _new_run(initiated_by="user_1")
    approval_row = AgentApproval(
        id="appr_1",
        run_id=run.id,
        tool_call_id="call_1",
        tool_name="write_file",
        status=PENDING,
    )
    db_session.add_all([run, approval_row])
    await db_session.commit()

    service = get_approval_service()
    first = await service.decide(
        run.id, "call_1", "approve", "user_1", idempotency_key="key_1"
    )
    # A second request with a different tool_call_id but the same
    # idempotency key returns the recorded decision.
    second = await service.decide(
        run.id, "call_1", "deny", "user_1", idempotency_key="key_1"
    )

    assert first.id == second.id
    assert second.status == APPROVED


@pytest.mark.asyncio
async def test_decide_rejects_invalid_decision(db_session):
    run = _new_run(initiated_by="user_1")
    db_session.add(run)
    await db_session.commit()

    service = get_approval_service()
    with pytest.raises(Exception):
        await service.decide(run.id, "call_1", "maybe", "user_1")


@pytest.mark.asyncio
async def test_decide_forbidden_for_non_initiator_non_admin(db_session):
    # A second user with a non-admin role.
    from app.database.models import Member

    run = _new_run(initiated_by="user_1")
    member = Member(
        id="member_2",
        organization_id="org_1",
        user_id="user_2",
        role="member",
    )
    approval_row = AgentApproval(
        id="appr_1",
        run_id=run.id,
        tool_call_id="call_1",
        tool_name="write_file",
        status=PENDING,
    )
    db_session.add_all([run, member, approval_row])
    await db_session.commit()

    service = get_approval_service()
    with pytest.raises(Exception):
        await service.decide(run.id, "call_1", "approve", "user_2")


# --- engine integration ---------------------------------------------

@pytest.mark.asyncio
async def test_engine_pause_records_pending_approval(db_session):
    run = _new_run(initiated_by="user_1")
    db_session.add(run)
    await db_session.commit()

    from langgraph.checkpoint.memory import MemorySaver

    llm = FakeLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="write_file",
                        arguments={"path": "notes.txt", "content": "x"},
                    )
                ],
            )
        ]
    )
    engine = LangGraphEngine(llm, checkpointer=MemorySaver())
    result = await engine.start_run(
        run.id, "agent_1", "version_1", {"message": "write file"}, "user_1"
    )

    assert result["status"] == WAITING_FOR_APPROVAL

    async with async_session_factory() as session:
        approvals = (
            await session.execute(
                select(AgentApproval).where(AgentApproval.run_id == run.id)
            )
        ).scalars().all()
    assert len(approvals) == 1
    assert approvals[0].status == PENDING
    assert approvals[0].tool_name == "write_file"
    assert approvals[0].tool_call_id == "call_1"


# --- API endpoints ----------------------------------------------------
# Endpoints run via httpx AsyncClient + ASGITransport so they
# execute in the test's event loop, sharing the aiosqlite
# connections (TestClient runs in a separate loop and cannot
# see data committed by the open db_session).


class _FakeEngine:
    def __init__(self):
        self.resumed = []

    async def resume_run(self, run_id, approval=None):
        self.resumed.append((run_id, approval))
        return {"run_id": run_id, "status": "SUCCEEDED", "response": "done"}


def _approval_client(app, monkeypatch):
    fake_engine = _FakeEngine()
    import app.agent.unified_router as unified_module

    monkeypatch.setattr(unified_module, "get_engine", lambda: fake_engine)
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ), fake_engine


@pytest.mark.asyncio
async def test_list_approvals_endpoint(db_session, monkeypatch):
    app = create_test_app()
    client, _ = _approval_client(app, monkeypatch)
    run = _new_run(initiated_by="user_1")
    approval_row = AgentApproval(
        id="appr_1",
        run_id=run.id,
        tool_call_id="call_1",
        tool_name="write_file",
        status=PENDING,
    )
    db_session.add_all([run, approval_row])
    await db_session.commit()

    response = await client.get(
        f"/api/agents/unified/runs/{run.id}/approvals",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["toolCallId"] == "call_1"
    assert data[0]["status"] == PENDING
    await client.aclose()


@pytest.mark.asyncio
async def test_decide_approval_endpoint(db_session, monkeypatch):
    app = create_test_app()
    client, fake_engine = _approval_client(app, monkeypatch)
    run = _new_run(initiated_by="user_1")
    approval_row = AgentApproval(
        id="appr_1",
        run_id=run.id,
        tool_call_id="call_1",
        tool_name="write_file",
        status=PENDING,
    )
    db_session.add_all([run, approval_row])
    await db_session.commit()

    response = await client.post(
        f"/api/agents/unified/runs/{run.id}/approvals",
        json={
            "tool_call_id": "call_1",
            "decision": "approve",
            "idempotency_key": "key_1",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approval"]["status"] == APPROVED
    # The engine was resumed with the approval decision.
    assert fake_engine.resumed == [(run.id, {"approved": True})]
    await client.aclose()


@pytest.mark.asyncio
async def test_decide_approval_endpoint_requires_auth(db_session, monkeypatch):
    app = create_test_app()
    client, _ = _approval_client(app, monkeypatch)
    run = _new_run(initiated_by="user_1")
    db_session.add(run)
    await db_session.commit()

    response = await client.post(
        f"/api/agents/unified/runs/{run.id}/approvals",
        json={"tool_call_id": "call_1", "decision": "approve"},
    )

    assert response.status_code == 401
    await client.aclose()
