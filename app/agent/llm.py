import httpx
import os
import json
import time
from dataclasses import dataclass
from typing import Optional
from app.config.settings import settings


@dataclass
class LLMResponse:
    content: str = ""
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None


class LLMService:
    def __init__(self):
        self.ollama_base = settings.OLLAMA_BASE_URL
        self.ollama_model = settings.OLLAMA_MODEL
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model = settings.GROQ_MODEL
        self._client = httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, model: Optional[str] = None, max_tokens: int = 4096, temperature: float = 0.7) -> LLMResponse:
        if not model:
            model = self.ollama_model

        if model == self.groq_model or (not self._ollama_available() and self.groq_api_key):
            return await self._call_groq(prompt, model, max_tokens, temperature)
        return await self._call_ollama(prompt, model, max_tokens, temperature)

    def _ollama_available(self) -> bool:
        return bool(self.ollama_base and self.ollama_model)

    async def _call_ollama(self, prompt: str, model: str, max_tokens: int, temperature: float) -> LLMResponse:
        url = f"{self.ollama_base}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                content=data.get("response", ""),
                provider="ollama",
                model=model,
                input_tokens=data.get("eval_count", 0),
                output_tokens=data.get("eval_count", 0),
            )
        except Exception as e:
            if self.groq_api_key and model != self.groq_model:
                return await self._call_groq(prompt, self.groq_model, max_tokens, temperature)
            return LLMResponse(provider="ollama", model=model, error=str(e))

    async def _call_groq(self, prompt: str, model: str, max_tokens: int, temperature: float) -> LLMResponse:
        if not self.groq_api_key:
            return LLMResponse(provider="groq", model=model, error="GROQ_API_KEY not configured")
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                provider="groq",
                model=model,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                cost_usd=self._estimate_cost(model, usage),
            )
        except Exception as e:
            return LLMResponse(provider="groq", model=model, error=str(e))

    def _estimate_cost(self, model: str, usage: dict) -> float:
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        if "70b" in model.lower():
            return (input_tokens * 0.0000006 + output_tokens * 0.0000009) / 1000
        return (input_tokens * 0.00000027 + output_tokens * 0.00000035) / 1000

    async def chat(self, messages: list[dict], model: Optional[str] = None, max_tokens: int = 4096, temperature: float = 0.7) -> LLMResponse:
        if not model:
            model = self.ollama_model
        if model == self.groq_model or (not self._ollama_available() and self.groq_api_key):
            return await self._call_groq_chat(messages, model, max_tokens, temperature)
        return await self._call_ollama_chat(messages, model, max_tokens, temperature)

    async def _call_ollama_chat(self, messages: list[dict], model: str, max_tokens: int, temperature: float) -> LLMResponse:
        url = f"{self.ollama_base}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                provider="ollama",
                model=model,
            )
        except Exception as e:
            if self.groq_api_key and model != self.groq_model:
                return await self._call_groq_chat(messages, self.groq_model, max_tokens, temperature)
            return LLMResponse(provider="ollama", model=model, error=str(e))

    async def _call_groq_chat(self, messages: list[dict], model: str, max_tokens: int, temperature: float) -> LLMResponse:
        if not self.groq_api_key:
            return LLMResponse(provider="groq", model=model, error="GROQ_API_KEY not configured")
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                provider="groq",
                model=model,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )
        except Exception as e:
            return LLMResponse(provider="groq", model=model, error=str(e))

    async def close(self):
        await self._client.aclose()


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service