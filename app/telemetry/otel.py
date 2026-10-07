"""OpenTelemetry telemetry.

Sets up a TracerProvider and exposes :func:`get_tracer`
for span creation. Spans are exported to OTLP when
``OTEL_EXPORTER_OTLP_ENDPOINT`` is configured, to the
console when ``OTEL_CONSOLE_EXPORTER`` is set, and are
otherwise created and dropped.

Instrumented operations:
- LLM calls (provider, model, tokens, cost)
- Tool executions (tool, risk tier, success)
- Run transitions (run_id, from/to status)
- FastAPI HTTP requests (via FastAPIInstrumentor)

The provider is kept module-local so tests can swap in an
in-memory exporter via ``reset_telemetry()`` +
``init_telemetry(provider=...)`` — the process-global
tracer provider can only be set once, so we never rely on
it for span creation.
"""
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "agentic-crm")
_initialized = False
_provider: Optional[TracerProvider] = None
_memory_exporter: Optional[InMemorySpanExporter] = None


def _exporter():
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=endpoint)
    # Console export is opt-in (it spawns a background thread that
    # is noisy in tests). Enable with OTEL_CONSOLE_EXPORTER=true.
    if os.environ.get("OTEL_CONSOLE_EXPORTER", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return ConsoleSpanExporter()
    return None


def init_telemetry(
    provider: Optional[TracerProvider] = None,
    processor: Optional[BatchSpanProcessor] = None,
) -> TracerProvider:
    """Initialize the telemetry provider.

    Accepts an optional provider/processor for tests. When no
    processor is supplied, one is built from the configured
    exporter — if no exporter is configured (e.g. in tests),
    spans are created and dropped. Safe to call multiple times
    (no-op after the first successful initialization).
    """
    global _initialized, _provider, _memory_exporter
    if _initialized:
        return _provider

    if provider is None:
        provider = TracerProvider(
            resource=Resource.create({"service.name": _SERVICE_NAME})
        )
    if processor is None:
        exporter = _exporter()
        if exporter is not None:
            processor = BatchSpanProcessor(exporter)
    if processor is not None:
        provider.add_span_processor(processor)
    _memory_exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(_memory_exporter))
    _provider = provider
    _initialized = True
    # Best-effort: make instrumentors (FastAPIInstrumentor) use
    # our provider. The global provider can only be set once per
    # process, so later calls are no-ops — span creation itself
    # goes through the module-local provider above.
    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    return provider


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer from the module-local provider,
    initializing telemetry on first use."""
    if not _initialized:
        init_telemetry()
    return _provider.get_tracer(name)


def reset_telemetry() -> None:
    """Reset the module-local provider (tests only)."""
    global _initialized, _provider, _memory_exporter
    if _provider is not None:
        _provider.shutdown()
    _provider = None
    _memory_exporter = None
    _initialized = False


def get_spans(limit: int = 100) -> list[dict]:
    """Return recent spans for the local telemetry panel."""
    if _memory_exporter is None:
        return []
    spans = _memory_exporter.get_finished_spans()[-max(1, min(limit, 500)):]
    return [
        {
            "name": span.name,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "status": str(span.status.status_code),
            "attributes": {key: str(value) for key, value in span.attributes.items()},
        }
        for span in spans
    ]
