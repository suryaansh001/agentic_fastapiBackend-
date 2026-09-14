from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.dependencies.auth import get_current_user, CurrentUser
from app.agent.orchestrator import get_orchestrator
from app.agent.llm import get_llm_service

router = APIRouter(prefix="/api/agents/unified", tags=["unified-agent"])

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    agent_used: str
    tools_called: List[str] = []
    plan_summary: str = ""
    steps_executed: int = 0
    raw_results: dict = {}
    files: List[dict] = []

@router.post("/chat", response_model=ChatResponse)
async def unified_chat(request: ChatRequest, current_user: CurrentUser = Depends(get_current_user)):
    orchestrator = get_orchestrator(get_llm_service())
    
    plan = await orchestrator.plan(request.message, request.conversation_history)
    
    if not plan.steps:
        llm = get_llm_service()
        llm_response = await llm.chat([
            {"role": "system", "content": "You are a helpful CRM assistant. Be concise and helpful."},
            *(request.conversation_history or []),
            {"role": "user", "content": request.message}
        ])
        return ChatResponse(
            response=llm_response.content,
            agent_used="llm",
            tools_called=[],
            plan_summary="General conversation",
            steps_executed=0,
            raw_results={},
            files=[]
        )
    
    execution_result = await orchestrator.execute(plan, request.conversation_history)
    
    tools_called = []
    for step in plan.steps:
        tools_called.append(f"{step.agent.value}.{step.tool}")
    
    results = execution_result.get("results", {})
    final_result = results.get(len(plan.steps) - 1, {}) if plan.steps else {}
    
    files = []
    response_text = f"Plan: {plan.summary}\n\n"
    response_text += f"Executed {execution_result['steps_executed']} steps.\n\n"
    
    for i, (step_key, result) in enumerate(results.items()):
        if result.get("output_path"):
            files.append({"path": result["output_path"], "step": i, "description": plan.steps[i].description})
        if result.get("success"):
            if result.get("stdout"):
                response_text += f"\nStep {i}: {plan.steps[i].description}\n{result['stdout'][:500]}"
        elif result.get("error"):
            response_text += f"\nStep {i}: {plan.steps[i].description} - Error: {result['error'][:200]}"
    
    if not any(r.get("output_path") for r in results.values()):
        if isinstance(final_result, dict):
            if "stdout" in final_result:
                response_text += f"\nOutput:\n{final_result['stdout'][:2000]}"
            elif "content" in final_result:
                response_text += f"\nContent:\n{final_result['content'][:2000]}"
            elif "error" in final_result:
                response_text += f"\nError: {final_result['error']}"
        else:
            response_text += f"\nResult: {str(final_result)[:2000]}"
    
    return ChatResponse(
        response=response_text,
        agent_used="orchestrator",
        tools_called=list(set(tools_called)),
        plan_summary=plan.summary,
        steps_executed=execution_result["steps_executed"],
        raw_results=results,
        files=files
    )