import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from app.dependencies.auth import get_current_user, CurrentUser
from app.agent.langgraph_engine import get_engine
from app.agent.approval import (
    APPROVED,
    ApprovalService,
    get_approval_service,
)

router = APIRouter(prefix="/api/agents/unified", tags=["unified-agent"])


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None
    context: Optional[dict] = None
    model: Optional[str] = None
    task_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    agent_used: str
    tools_called: List[str] = []
    steps_executed: int = 0
    files: List[dict] = []
    task_id: str = ""
    status: str = ""
    paused: bool = False
    pending_tool: Optional[dict] = None


@router.post("/chat", response_model=ChatResponse)
async def unified_chat(request: ChatRequest, current_user: CurrentUser = Depends(get_current_user)):
    engine = get_engine()
    # Continue a prior conversation when a task_id (thread id) is
    # given; otherwise start a new thread.
    thread_id = request.task_id or str(uuid.uuid4())
    result = await engine.start_run(
        thread_id,
        agent_id="unified",
        version_id="",
        input={
            "message": request.message,
            "conversation_history": request.conversation_history,
        },
        initiated_by=current_user.id,
    )
    files = [
        {"path": path, "description": "Generated file"}
        for path in result.get("files") or []
    ]
    return ChatResponse(
        response=result.get("response", ""),
        agent_used="runner",
        tools_called=result.get("tools_called") or [],
        steps_executed=result.get("steps_executed") or 0,
        files=files,
        task_id=thread_id,
        status=result.get("status", ""),
        paused=bool(result.get("paused")),
        pending_tool=result.get("pending_tool"),
    )


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, current_user: CurrentUser = Depends(get_current_user)):
    engine = get_engine()
    result = await engine.resume_run(task_id, {"approved": True})
    return result


# --- durable human-in-the-loop approvals -----------------------------


class ApprovalDecisionRequest(BaseModel):
    tool_call_id: str
    decision: str  # "approve" | "deny"
    idempotency_key: Optional[str] = None


class ApprovalDecisionResponse(BaseModel):
    approval: dict
    run_result: Optional[dict] = None


@router.get("/runs/{run_id}/approvals", response_model=List[dict])
async def list_approvals(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_approval_service()
    approvals = await service.list_for_run(run_id)
    return [_approval_dict(a) for a in approvals]


@router.post(
    "/runs/{run_id}/approvals", response_model=ApprovalDecisionResponse
)
async def decide_approval(
    run_id: str,
    request: ApprovalDecisionRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_approval_service()
    approval = await service.decide(
        run_id,
        request.tool_call_id,
        request.decision,
        current_user.id,
        request.idempotency_key,
    )
    # Resume the engine with the approver's decision.
    engine = get_engine()
    run_result = await engine.resume_run(
        run_id, {"approved": approval.status == APPROVED}
    )
    return ApprovalDecisionResponse(
        approval=_approval_dict(approval),
        run_result=run_result,
    )


def _approval_dict(approval) -> dict:
    return {
        "id": approval.id,
        "runId": approval.run_id,
        "toolCallId": approval.tool_call_id,
        "tool": approval.tool_name,
        "args": approval.args or {},
        "status": approval.status,
        "approverId": approval.approver_id,
        "createdAt": approval.created_at.isoformat() if approval.created_at else None,
        "decidedAt": approval.decided_at.isoformat() if approval.decided_at else None,
    }
