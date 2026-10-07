"""OpenTelemetry instrumentation tests.

Verifies that LLM calls, tool executions, and run
transitions create spans with the expected attributes.
Uses an in-memory exporter via the module-local
provider (see app.telemetry.otel).
"""
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.agent.llm import LLMResponse, LLMService
from app.agent.run_lifecycle import (
    QUEUED,
    RUNNING,
    transition_run,
)
from app.agent.tools.registry import default_registry
from app.database.models import AgentRun
from app.telemetry.otel import init_telemetry, reset_telemetry


@pytest.fixture(scope="session")
def otel_exporter():
    reset_telemetry()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    init_telemetry(
        provider=provider,
        processor=SimpleSpanProcessor(exporter),
    )
    yield exporter
    reset_telemetry()


@pytest.fixture
def spans(otel_exporter):
    otel_exporter.clear()
    yield otel_exporter


def _span_names(spans):
    return [s.name for s in spans.get_finished_spans()]


def _find_span(spans, name):
    return next(
        (s for s in spans.get_finished_spans() if s.name == name),
        None,
    )


@pytest.mark.asyncio
async def test_run_transition_creates_span(spans, db_session):
    run = AgentRun(
        id="run_otel",
        agent_id="agent_1",
        version_id="version_1",
        status=QUEUED,
    )
    db_session.add(run)
    await db_session.commit()

    await transition_run(db_session, run, RUNNING)
    await db_session.commit()

    span = _find_span(spans, "run.transition")
    assert span is not None
    assert span.attributes["run.id"] == "run_otel"
    assert span.attributes["run.from"] == QUEUED
    assert span.attributes["run.to"] == RUNNING


@pytest.mark.asyncio
async def test_run_transition_invalid_is_error_span(spans, db_session):
    run = AgentRun(
        id="run_otel_bad",
        agent_id="agent_1",
        version_id="version_1",
        status=RUNNING,
    )
    db_session.add(run)
    await db_session.commit()

    from app.agent.run_lifecycle import InvalidTransition

    with pytest.raises(InvalidTransition):
        await transition_run(db_session, run, QUEUED)

    span = _find_span(spans, "run.transition")
    assert span is not None
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.asyncio
async def test_tool_execute_creates_span(spans):
    registry = default_registry()
    result = await registry.execute(
        "ask_question", {"question": "hi?"}
    )

    assert result["question"] == "hi?"
    span = _find_span(spans, "tool.execute")
    assert span is not None
    assert span.attributes["tool.name"] == "ask_question"
    assert span.attributes["tool.success"] is True


@pytest.mark.asyncio
async def test_tool_execute_unknown_tool_is_error_span(spans):
    registry = default_registry()
    result = await registry.execute("nope_tool", {})

    assert result["success"] is False
    span = _find_span(spans, "tool.execute")
    assert span is not None
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR


@pytest.mark.asyncio
async def test_llm_chat_creates_span(spans, monkeypatch):
    svc = LLMService()

    async def fake_call_ollama(
        messages, model, max_tokens, temperature, tools
    ):
        return LLMResponse(
            content="ok",
            input_tokens=3,
            output_tokens=4,
            cost_usd=0.0,
        )

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "_call_ollama", fake_call_ollama)
    monkeypatch.setattr(svc, "_log_call", fake_log)

    response = await svc.chat(
        [{"role": "user", "content": "hi"}]
    )

    assert response.content == "ok"
    span = _find_span(spans, "llm.chat")
    assert span is not None
    assert span.attributes["llm.provider"] == "ollama"
    assert span.attributes["llm.input_tokens"] == 3
    assert span.attributes["llm.output_tokens"] == 4


@pytest.mark.asyncio
async def test_llm_chat_error_is_error_span(spans, monkeypatch):
    svc = LLMService()
    # Disable the GroQ fallback so the fake error is returned.
    monkeypatch.setattr(svc, "groq_api_key", None)

    async def fake_call_ollama(
        messages, model, max_tokens, temperature, tools
    ):
        return LLMResponse(error="boom")

    async def fake_log(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "_call_ollama", fake_call_ollama)
    monkeypatch.setattr(svc, "_log_call", fake_log)

    response = await svc.chat(
        [{"role": "user", "content": "hi"}]
    )

    assert response.error == "boom"
    span = _find_span(spans, "llm.chat")
    assert span is not None
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR
