"""Phase 3 tests: LLM adapter — native tool calls, accounting, logging."""
import json

import httpx
import pytest
from sqlalchemy import select

from app.agent.llm import LLMService, LLMResponse, ToolCall
from app.database.models import LLMCallLog


def _ollama_chat_handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "model": payload.get("model", ""),
            "message": {"role": "assistant", "content": "Hello from ollama"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        },
    )


def _ollama_tool_call_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "llama3.1",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "query_crm",
                            "arguments": '{"operation": "list_deals"}',
                        },
                    }
                ],
            },
            "prompt_eval_count": 8,
            "eval_count": 3,
        },
    )


def _ollama_error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "ollama is down"})


def _groq_chat_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"role": "assistant", "content": "Hello from groq"}}
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 7},
        },
    )


@pytest.fixture
def ollama_service():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_ollama_chat_handler))
    return LLMService(client=client)


@pytest.fixture
def groq_service():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_groq_chat_handler))
    return LLMService(client=client)


def test_initialization():
    service = LLMService(client=httpx.AsyncClient())
    assert service.ollama_base == "http://localhost:11434"
    assert service.ollama_model == "llama3.1"
    assert service.groq_model == "llama-3.1-70b-versatile"


@pytest.mark.asyncio
async def test_generate_with_ollama(ollama_service):
    response = await ollama_service.generate("Hello", max_tokens=10)
    assert isinstance(response, LLMResponse)
    assert response.provider == "ollama"
    assert response.content == "Hello from ollama"
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.error is None


@pytest.mark.asyncio
async def test_chat_with_groq(groq_service):
    response = await groq_service.chat(
        [{"role": "user", "content": "What is AI?"}],
        model="llama-3.1-70b-versatile",
        max_tokens=10,
    )
    assert response.provider == "groq"
    assert response.content == "Hello from groq"
    assert response.input_tokens == 12
    assert response.output_tokens == 7


@pytest.mark.asyncio
async def test_native_tool_calls(ollama_service):
    ollama_service._client = httpx.AsyncClient(
        transport=httpx.MockTransport(_ollama_tool_call_handler)
    )
    response = await ollama_service.chat(
        [{"role": "user", "content": "list deals"}],
        tools=[{"type": "function", "function": {"name": "query_crm"}}],
    )
    assert response.provider == "ollama"
    # Native tool calls: structured, not scraped from content text.
    assert response.content == ""
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert isinstance(call, ToolCall)
    assert call.id == "call_1"
    assert call.name == "query_crm"
    assert call.arguments == {"operation": "list_deals"}


@pytest.mark.asyncio
async def test_tool_call_arguments_invalid_json(ollama_service):
    ollama_service._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_2",
                                "function": {
                                    "name": "todo",
                                    "arguments": "{not valid json",
                                },
                            }
                        ],
                    }
                },
            )
        )
    )
    response = await ollama_service.chat([{"role": "user", "content": "x"}])
    assert response.tool_calls[0].arguments == {}


@pytest.mark.asyncio
async def test_provider_fallback_to_groq():
    def fallback_handler(request: httpx.Request) -> httpx.Response:
        if "groq.com" in str(request.url):
            return _groq_chat_handler(request)
        return _ollama_error_handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(fallback_handler))
    service = LLMService(client=client)
    # GroQ key is configured in the test environment; when Ollama
    # fails the adapter falls back to GroQ.
    response = await service.generate("Test question", max_tokens=10)
    assert isinstance(response, LLMResponse)
    assert response.provider == "groq"
    assert response.error is None


@pytest.mark.asyncio
async def test_calls_are_logged_to_llm_call_log(ollama_service, db_session):
    await ollama_service.chat(
        [{"role": "user", "content": "log me"}],
        agent_id="agent_1",
        run_id="run_1",
    )
    rows = (
        await db_session.execute(select(LLMCallLog).where(LLMCallLog.run_id == "run_1"))
    ).scalars().all()
    assert len(rows) == 1
    log = rows[0]
    assert log.provider == "ollama"
    assert log.model == "llama3.1"
    assert log.input_tokens == 10
    assert log.output_tokens == 5
    assert log.success is True
    assert log.agent_id == "agent_1"


def test_cost_estimation(ollama_service):
    usage = {"prompt_tokens": 100, "completion_tokens": 50}
    cost = ollama_service._estimate_cost("llama-3.1-70b-versatile", usage)
    assert isinstance(cost, float)
    assert cost >= 0.0


def test_llm_response_defaults():
    response = LLMResponse(content="test", provider="ollama", model="test")
    assert response.content == "test"
    assert response.provider == "ollama"
    assert response.input_tokens == 0
    assert response.output_tokens == 0
    assert response.cost_usd == 0.0
    assert response.tool_calls == []
