import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.dependencies.auth import get_current_user, CurrentUser
from app.agent.langgraph_engine import get_engine

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
