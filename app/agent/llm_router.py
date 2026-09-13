from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from typing import Any
from app.agent.llm import LLMService, get_llm_service, LLMResponse
from app.dependencies.auth import get_current_user, CurrentUser

router = APIRouter(prefix="/api/agents/llm", tags=["llm"])

class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7

class ChatRequest(BaseModel):
    messages: list[dict]
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7

@router.post("/generate", response_model=dict)
async def generate(request: GenerateRequest, current_user: CurrentUser = Depends(get_current_user)):
    svc = get_llm_service()
    response = await svc.generate(request.prompt, model=request.model, max_tokens=request.max_tokens, temperature=request.temperature)
    return {"content": response.content, "provider": response.provider, "model": response.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cost_usd": response.cost_usd, "error": response.error}

@router.post("/chat", response_model=dict)
async def chat(request: ChatRequest, current_user: CurrentUser = Depends(get_current_user)):
    svc = get_llm_service()
    response = await svc.chat(request.messages, model=request.model, max_tokens=request.max_tokens, temperature=request.temperature)
    return {"content": response.content, "provider": response.provider, "model": response.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens, "cost_usd": response.cost_usd, "error": response.error}

@router.get("/status")
async def llm_status(current_user: CurrentUser = Depends(get_current_user)):
    svc = get_llm_service()
    return {"ollama_available": bool(svc.ollama_base), "ollama_model": svc.ollama_model, "groq_configured": bool(svc.groq_api_key), "groq_model": svc.groq_model}