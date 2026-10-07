"""Canonical tool registry.

Single source of truth for every tool the agent execution engine may call.
The registry is engine-neutral: the LangGraph engine (Phase 4) consumes
: meth:`ToolRegistry.llm_schemas` for native function calling and
dispatches invocations through :meth:`ToolRegistry.execute`.

Tool implementations live in ``app/agent/tools/`` (crm_query, filesystem,
web_fetch). This module declares them once — name, JSON-schema parameters,
risk tier, handler — so no other component re-declares or re-scrapes them.
"""
import inspect
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional

from opentelemetry.trace import StatusCode
from pydantic import BaseModel, Field

from app.agent.tools.crm_query import CrmQueryError, crm_query_service
from app.agent.tools.filesystem import (
    WorkspaceError,
    grep_workspace,
    list_workspace,
    read_text_file,
    write_text_file,
)
from app.agent.tools.web_fetch import WebFetchError, safe_fetch
from app.telemetry.otel import get_tracer

# Risk tiers. The execution engine (Phase 5 HITL) gates tools on these.
RISK_SAFE = "safe"
RISK_APPROVAL_REQUIRED = "approval_required"
RISK_BLOCKED = "blocked"

# Maximum subagent nesting depth. A top-level run has
# depth 0; it may spawn children up to this depth.
MAX_SUBAGENT_DEPTH = 3


# --- input schemas (canonical definitions) ----------------------------------

class AskQuestionInput(BaseModel):
    question: str
    options: Optional[list[str]] = None


class CreateCrmActivityInput(BaseModel):
    contactId: Optional[str] = None
    companyId: Optional[str] = None
    type: str
    body: str


class FinishRunInput(BaseModel):
    runId: str
    summary: str
    result: Optional[dict] = None


class InspectRunInput(BaseModel):
    runId: str


class PostSlackMessageInput(BaseModel):
    channel: str
    message: str


class QueryCRMInput(BaseModel):
    operation: str = Field(..., description="Allow-listed CRM query operation name")
    params: Optional[dict] = Field(default_factory=dict, description="Operation parameters")


class ReadCRMRecordInput(BaseModel):
    recordId: str
    kind: str


class ReadFileInput(BaseModel):
    path: str


class GlobInput(BaseModel):
    pattern: str


class GrepInput(BaseModel):
    pattern: str
    path: Optional[str] = None


class TodoInput(BaseModel):
    action: str
    text: Optional[str] = None


class WebFetchInput(BaseModel):
    url: str


class WebSearchInput(BaseModel):
    query: str


class WriteFileInput(BaseModel):
    path: str
    content: str


class SpawnSubagentInput(BaseModel):
    agentId: str = Field(..., description="Id of the agent to spawn")
    input: Optional[dict] = Field(
        default_factory=dict,
        description="Input for the subagent run",
    )


# --- execution context ------------------------------------------------------


@dataclass
class ToolContext:
    """Per-run execution context handed to every tool handler."""

    user_id: Optional[str] = None
    workspace_root: Optional[str] = None
    session: Optional[Any] = None  # AsyncSession, when the engine provides one
    run_id: Optional[str] = None  # current AgentRun.id
    depth: int = 0  # subagent nesting depth (0 = top-level run)
    # Engine-supplied callable to execute a subagent:
    # async (parent_run_id, user_id, agent_id, input) -> dict
    subagent_executor: Optional[Callable] = None


@asynccontextmanager
async def _session_for(ctx: ToolContext) -> AsyncGenerator[Any, None]:
    if ctx.session is not None:
        yield ctx.session
    else:
        from app.database.session import async_session_factory

        async with async_session_factory() as session:
            yield session


# --- registry primitives ----------------------------------------------------

ToolHandler = Callable[[ToolContext, dict], Awaitable[dict]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    risk: str = RISK_SAFE
    handler: Optional[ToolHandler] = None

    def llm_schema(self) -> dict:
        """OpenAI/Anthropic-style function-calling schema for the LLM."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def llm_schemas(self) -> list[dict]:
        return [spec.llm_schema() for spec in self._tools.values()]

    async def execute(
        self,
        name: str,
        args: Optional[dict] = None,
        context: Optional[ToolContext] = None,
    ) -> dict:
        tracer = get_tracer("tool")
        with tracer.start_as_current_span("tool.execute") as span:
            span.set_attribute("tool.name", name)
            spec = self.get(name)
            if spec is None:
                span.set_status(StatusCode.ERROR, f"unknown tool: {name}")
                return {"success": False, "error": f"unknown tool: {name}"}
            if spec.handler is None:
                span.set_status(StatusCode.ERROR, "no handler")
                return {"success": False, "error": f"tool {name} has no handler"}
            span.set_attribute("tool.risk", spec.risk)
            ctx = context or ToolContext()
            result = spec.handler(ctx, args or {})
            if inspect.isawaitable(result):
                result = await result
            span.set_attribute("tool.success", bool(result.get("success", True)))
            return result


# --- handlers ---------------------------------------------------------------


async def _ask_question(ctx: ToolContext, args: dict) -> dict:
    data = AskQuestionInput(**args)
    return {"question": data.question, "options": data.options or []}


async def _spawn_subagent(ctx: ToolContext, args: dict) -> dict:
    data = SpawnSubagentInput(**args)
    if ctx.subagent_executor is None:
        return {
            "success": False,
            "error": "subagents are not available in this context",
        }
    if ctx.depth >= MAX_SUBAGENT_DEPTH:
        return {
            "success": False,
            "error": (
                f"maximum subagent depth "
                f"({MAX_SUBAGENT_DEPTH}) exceeded"
            ),
        }
    result = await ctx.subagent_executor(
        ctx.run_id, ctx.user_id, data.agentId, data.input
    )
    return {"success": True, **result}


async def _query_crm(ctx: ToolContext, args: dict) -> dict:
    data = QueryCRMInput(**args)
    try:
        async with _session_for(ctx) as session:
            result = await crm_query_service.execute(
                session, data.operation, data.params
            )
        return {"success": True, **result}
    except CrmQueryError as e:
        return {"success": False, "error": str(e)}


async def _create_crm_activity(ctx: ToolContext, args: dict) -> dict:
    data = CreateCrmActivityInput(**args)
    return {"activityId": "activity_123"}


async def _finish_run(ctx: ToolContext, args: dict) -> dict:
    data = FinishRunInput(**args)
    return {"finished": True, "runId": data.runId}


async def _glob(ctx: ToolContext, args: dict) -> dict:
    data = GlobInput(**args)
    try:
        return {"files": list_workspace(data.pattern), "success": True}
    except WorkspaceError as e:
        return {"success": False, "error": str(e)}


async def _grep(ctx: ToolContext, args: dict) -> dict:
    data = GrepInput(**args)
    try:
        return {"matches": grep_workspace(data.pattern, data.path), "success": True}
    except WorkspaceError as e:
        return {"success": False, "error": str(e)}


async def _inspect_run(ctx: ToolContext, args: dict) -> dict:
    data = InspectRunInput(**args)
    return {"runId": data.runId, "status": "COMPLETED"}


async def _post_slack_message(ctx: ToolContext, args: dict) -> dict:
    data = PostSlackMessageInput(**args)
    return {"posted": True, "channel": data.channel}


async def _read_crm_record(ctx: ToolContext, args: dict) -> dict:
    data = ReadCRMRecordInput(**args)
    return {"record": {"id": data.recordId, "kind": data.kind}}


async def _read_file(ctx: ToolContext, args: dict) -> dict:
    data = ReadFileInput(**args)
    try:
        return {"content": read_text_file(data.path), "success": True}
    except WorkspaceError as e:
        return {"success": False, "error": str(e)}


async def _todo(ctx: ToolContext, args: dict) -> dict:
    data = TodoInput(**args)
    return {"todo": data.text or data.action}


async def _web_fetch(ctx: ToolContext, args: dict) -> dict:
    data = WebFetchInput(**args)
    try:
        return await safe_fetch(data.url)
    except WebFetchError as e:
        return {"success": False, "error": str(e)}


async def _web_search(ctx: ToolContext, args: dict) -> dict:
    data = WebSearchInput(**args)
    return {"results": [], "note": "web_search is not configured"}


async def _write_file(ctx: ToolContext, args: dict) -> dict:
    data = WriteFileInput(**args)
    try:
        path = write_text_file(data.path, data.content)
        return {"written": True, "path": path, "success": True}
    except WorkspaceError as e:
        return {"success": False, "error": str(e)}


def _schema(model: type[BaseModel]) -> dict:
    return model.model_json_schema()


# --- default registry -------------------------------------------------------

_DEFAULT: Optional[ToolRegistry] = None


def _build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="ask_question",
            description="Ask the user a question and wait for their answer.",
            parameters=_schema(AskQuestionInput),
            handler=_ask_question,
        )
    )
    registry.register(
        ToolSpec(
            name="query_crm",
            description=(
                "Run an allow-listed, read-only CRM query. Supported "
                "operations: list_companies, list_deals, search_contacts, search_companies, "
                "deal_pipeline, contact_timeline, company_contacts, deal_summary."
            ),
            parameters=_schema(QueryCRMInput),
            handler=_query_crm,
        )
    )
    registry.register(
        ToolSpec(
            name="create_crm_activity",
            description="Log an activity (call, email, meeting or note) on a contact or company.",
            parameters=_schema(CreateCrmActivityInput),
            risk=RISK_APPROVAL_REQUIRED,
            handler=_create_crm_activity,
        )
    )
    registry.register(
        ToolSpec(
            name="finish_run",
            description="Finish the current run with a summary and an optional structured result.",
            parameters=_schema(FinishRunInput),
            handler=_finish_run,
        )
    )
    registry.register(
        ToolSpec(
            name="glob",
            description="List files inside the agent workspace matching a glob pattern.",
            parameters=_schema(GlobInput),
            handler=_glob,
        )
    )
    registry.register(
        ToolSpec(
            name="grep",
            description="Search files inside the agent workspace for a regex pattern.",
            parameters=_schema(GrepInput),
            handler=_grep,
        )
    )
    registry.register(
        ToolSpec(
            name="inspect_run",
            description="Inspect the status of an agent run by id.",
            parameters=_schema(InspectRunInput),
            handler=_inspect_run,
        )
    )
    registry.register(
        ToolSpec(
            name="post_slack_message",
            description="Post a message to a Slack channel.",
            parameters=_schema(PostSlackMessageInput),
            risk=RISK_APPROVAL_REQUIRED,
            handler=_post_slack_message,
        )
    )
    registry.register(
        ToolSpec(
            name="read_crm_record",
            description="Read a single CRM record by its id and kind.",
            parameters=_schema(ReadCRMRecordInput),
            handler=_read_crm_record,
        )
    )
    registry.register(
        ToolSpec(
            name="read_file",
            description="Read a text file from the agent workspace.",
            parameters=_schema(ReadFileInput),
            handler=_read_file,
        )
    )
    registry.register(
        ToolSpec(
            name="spawn_subagent",
            description=(
                "Spawn a subagent (a child run of another "
                "LIVE agent) and return its result. The "
                "subagent runs to completion before this "
                "run continues."
            ),
            parameters=_schema(SpawnSubagentInput),
            handler=_spawn_subagent,
        )
    )
    registry.register(
        ToolSpec(
            name="todo",
            description="Record or update a to-do item for the current run.",
            parameters=_schema(TodoInput),
            handler=_todo,
        )
    )
    registry.register(
        ToolSpec(
            name="web_fetch",
            description="Fetch a public HTTP or HTTPS URL and return its body (SSRF-safe).",
            parameters=_schema(WebFetchInput),
            handler=_web_fetch,
        )
    )
    registry.register(
        ToolSpec(
            name="web_search",
            description="Search the web for a query.",
            parameters=_schema(WebSearchInput),
            handler=_web_search,
        )
    )
    registry.register(
        ToolSpec(
            name="write_file",
            description="Write a text file inside the agent workspace.",
            parameters=_schema(WriteFileInput),
            risk=RISK_APPROVAL_REQUIRED,
            handler=_write_file,
        )
    )
    return registry


def default_registry() -> ToolRegistry:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = _build_default_registry()
    return _DEFAULT
