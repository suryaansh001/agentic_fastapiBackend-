"""LLM provider adapter with native tool calling and call logging.

Normalizes Ollama and GroQ (OpenAI-compatible) behind one async
interface. Providers return structured ``tool_calls`` — the adapter
never scrapes tool invocations out of response text. Every call is
persisted to ``llmCallLog`` for token and cost accounting.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.config.settings import settings
from app.database.models import LLMCallLog
from app.database.session import async_session_factory


@dataclass
class ToolCall:
    id: str = ""
    name: str = ""
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str = ""
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)


def _parse_arguments(raw) -> dict:
    """Parse provider tool-call arguments (JSON string or dict)."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_tool_calls(raw_calls) -> list[ToolCall]:
    """Normalize OpenAI-style tool_calls into ToolCall objects."""
    if not raw_calls:
        return []
    calls = []
    for raw in raw_calls:
        function = raw.get("function", {}) or {}
        calls.append(
            ToolCall(
                id=raw.get("id", "") or "",
                name=function.get("name", "") or "",
                arguments=_parse_arguments(function.get("arguments")),
            )
        )
    return calls


class LLMService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.ollama_base = settings.OLLAMA_BASE_URL
        self.ollama_model = settings.OLLAMA_MODEL
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model = settings.GROQ_MODEL
        self._client = client or httpx.AsyncClient(timeout=120.0)
        self._own_client = client is None

    # -- provider selection ---------------------------------------------

    def _ollama_available(self) -> bool:
        return bool(self.ollama_base and self.ollama_model)

    def _resolve_provider(self, model: Optional[str]) -> tuple[str, str]:
        """Return (provider, resolved model) for a request."""
        if model:
            if model == self.groq_model or model != self.ollama_model:
                return "groq", model
            return "ollama", model
        if self._ollama_available():
            return "ollama", self.ollama_model
        if self.groq_api_key:
            return "groq", self.groq_model
        return "ollama", self.ollama_model

    # -- public API ----------------------------------------------------

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> LLMResponse:
        return await self.chat(
            [{"role": "user", "content": prompt}],
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            agent_id=agent_id,
            run_id=run_id,
        )

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[list] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> LLMResponse:
        provider, resolved_model = self._resolve_provider(model)
        if provider == "groq":
            response = await self._call_groq(
                messages, resolved_model, max_tokens, temperature, tools
            )
        else:
            response = await self._call_ollama(
                messages, resolved_model, max_tokens, temperature, tools
            )
            if response.error and self.groq_api_key:
                # Ollama unreachable: fall back to GroQ.
                response = await self._call_groq(
                    messages, self.groq_model, max_tokens, temperature, tools
                )
        await self._log_call(
            response, messages, agent_id=agent_id, run_id=run_id
        )
        return response

    # -- providers -------------------------------------------------------

    async def _call_ollama(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list] = None,
    ) -> LLMResponse:
        url = f"{self.ollama_base}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if tools:
            payload["tools"] = tools
        try:
            resp = await self._client.post(url, json=payload)
            if resp.status_code == 400 and tools:
                # Model without tool support: retry without tools.
                payload.pop("tools", None)
                resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {}) or {}
            return LLMResponse(
                content=msg.get("content", "") or "",
                provider="ollama",
                model=model,
                input_tokens=data.get("prompt_eval_count", 0) or 0,
                output_tokens=data.get("eval_count", 0) or 0,
                tool_calls=_extract_tool_calls(msg.get("tool_calls")),
            )
        except Exception as e:
            return LLMResponse(provider="ollama", model=model, error=str(e))

    async def _call_groq(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list] = None,
    ) -> LLMResponse:
        if not self.groq_api_key:
            return LLMResponse(
                provider="groq", model=model, error="GROQ_API_KEY not configured"
            )
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            usage = data.get("usage", {}) or {}
            return LLMResponse(
                content=msg.get("content", "") or "",
                provider="groq",
                model=model,
                input_tokens=usage.get("prompt_tokens", 0) or 0,
                output_tokens=usage.get("completion_tokens", 0) or 0,
                cost_usd=self._estimate_cost(model, usage),
                tool_calls=_extract_tool_calls(msg.get("tool_calls")),
            )
        except Exception as e:
            return LLMResponse(provider="groq", model=model, error=str(e))

    # -- accounting ------------------------------------------------------

    def _estimate_cost(self, model: str, usage: dict) -> float:
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        if "70b" in model.lower():
            return (input_tokens * 0.0000006 + output_tokens * 0.0000009) / 1000
        return (input_tokens * 0.00000027 + output_tokens * 0.00000035) / 1000

    async def _log_call(
        self,
        response: LLMResponse,
        messages: list[dict],
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """Persist the call to llmCallLog. Never fails the request."""
        try:
            response_text = response.content
            if response.tool_calls:
                response_text = json.dumps(
                    {
                        "content": response.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }
                            for tc in response.tool_calls
                        ],
                    },
                    default=str,
                )
            async with async_session_factory() as session:
                session.add(
                    LLMCallLog(
                        agent_id=agent_id,
                        run_id=run_id,
                        provider=response.provider,
                        model=response.model,
                        prompt=json.dumps(messages, default=str),
                        response=response_text,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        cost_usd=f"{response.cost_usd:.6f}",
                        success=response.error is None,
                        error_message=response.error,
                    )
                )
                await session.commit()
        except Exception:
            pass

    async def close(self):
        if self._own_client:
            await self._client.aclose()


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
