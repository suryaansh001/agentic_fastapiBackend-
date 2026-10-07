"""LangGraph-backed agent execution engine.

Implements :class:`AgentExecutionEngine` with a LangGraph
``StateGraph``: an ``agent`` node calls the LLM with the
canonical tool registry's function-calling schemas, a
``tools`` node executes the returned tool calls through the
registry, and approval-required tools pause the graph with
``interrupt()`` so a human can approve or deny them.

State is checkpointed to PostgreSQL (same instance as the
CRM database) via ``AsyncPostgresSaver``; the run's
``graph_thread_id`` is the checkpoint thread id, so a crashed
worker's run is resumable from its last checkpoint.
"""
import json
import uuid
from typing import Any, Optional

from psycopg import AsyncConnection
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import Annotated, TypedDict

from app.agent.engine import AgentExecutionEngine
from app.agent.llm import LLMService
from app.agent.run_lifecycle import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    TERMINAL_STATUSES,
    WAITING_FOR_APPROVAL,
    emit_event,
    settle_run,
    transition_run,
)
from app.agent.subagents import get_subagent_service
from app.agent.tools.filesystem import WorkspaceError
from app.agent.tools.registry import (
    RISK_APPROVAL_REQUIRED,
    ToolContext,
    default_registry,
)
from app.config.settings import settings
from app.database.models import AgentRun
from app.database.session import async_session_factory

MAX_ITERATIONS = 15


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    run_id: str
    agent_id: str
    version_id: str
    user_id: str
    iteration: int
    files: list
    error: Optional[str]
    depth: int


def _default_system_prompt(registry) -> str:
    tools = registry.list_tools()
    lines = "\n".join(f"- {t.name}: {t.description}" for t in tools)
    return (
        "You are the CRM agent. Answer the user's request by calling "
        "the available tools, then give a concise final answer.\n\n"
        f"Available tools:\n{lines}\n\n"
        "Rules:\n"
        "- Use tools for any CRM data access or file operation; never "
        "invent data.\n"
        "- If a tool returns an error, explain it and try a different "
        "approach.\n"
        "- When the task is done, summarize the result for the user."
    )


def _to_provider_messages(messages: list) -> list[dict]:
    """Convert langchain messages to the provider wire format."""
    out = []
    for message in messages:
        if isinstance(message, SystemMessage):
            out.append({"role": "system", "content": message.content or ""})
        elif isinstance(message, HumanMessage):
            out.append({"role": "user", "content": message.content or ""})
        elif isinstance(message, AIMessage):
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }
            if message.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("args", {})),
                        },
                    }
                    for tc in message.tool_calls
                ]
            out.append(entry)
        elif isinstance(message, ToolMessage):
            out.append(
                {
                    "role": "tool",
                    "content": message.content or "",
                    "tool_call_id": message.tool_call_id,
                }
            )
    return out


def _asyncpg_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


class LangGraphEngine(AgentExecutionEngine):
    def __init__(
        self,
        llm_service: LLMService,
        registry=None,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.llm_service = llm_service
        self.registry = registry or default_registry()
        self._checkpointer = checkpointer
        self._checkpointer_conn: Optional[AsyncConnection] = None
        self._graph = None
        self._system_prompt = system_prompt or _default_system_prompt(
            self.registry
        )
        self.max_iterations = max_iterations

    # -- graph construction ------------------------------------------

    async def _get_checkpointer(self) -> AsyncPostgresSaver:
        if self._checkpointer is not None:
            return self._checkpointer
        self._checkpointer_conn = await AsyncConnection.connect(
            _asyncpg_url(settings.DATABASE_URL),
            autocommit=True,
        )
        self._checkpointer = AsyncPostgresSaver(self._checkpointer_conn)
        await self._checkpointer.setup()
        return self._checkpointer

    async def _get_graph(self):
        if self._graph is None:
            checkpointer = await self._get_checkpointer()
            self._graph = self._build_graph(checkpointer)
        return self._graph

    def _build_graph(self, checkpointer):
        llm = self.llm_service
        registry = self.registry
        system_prompt = self._system_prompt
        max_iterations = self.max_iterations

        async def agent_node(state: AgentState) -> dict:
            if state.get("error"):
                return {}
            if state["iteration"] >= max_iterations:
                return {"error": "max_iterations_reached"}
            response = await llm.chat(
                _to_provider_messages(state["messages"]),
                tools=registry.llm_schemas(),
                agent_id=state.get("agent_id") or None,
                run_id=state.get("run_id") or None,
            )
            if response.error:
                return {"error": response.error}
            if response.tool_calls:
                message = AIMessage(
                    content=response.content or "",
                    tool_calls=[
                        {
                            "name": tc.name,
                            "args": tc.arguments,
                            "id": tc.id or str(uuid.uuid4()),
                            "type": "tool_call",
                        }
                        for tc in response.tool_calls
                    ],
                )
            else:
                message = AIMessage(content=response.content or "")
            return {
                "messages": [message],
                "iteration": state["iteration"] + 1,
            }

        async def tools_node(state: AgentState) -> dict:
            last = state["messages"][-1]
            tool_calls = getattr(last, "tool_calls", None) or []
            current_depth = state.get("depth") or 0

            async def subagent_executor(
                parent_run_id, user_id, agent_id, input
            ):
                return await self._execute_subagent(
                    parent_run_id,
                    user_id,
                    agent_id,
                    input,
                    depth=current_depth + 1,
                )

            ctx = ToolContext(
                user_id=state.get("user_id") or None,
                run_id=state.get("run_id") or None,
                depth=current_depth,
                subagent_executor=subagent_executor,
            )
            # Phase 1: resolve every approval gate before any tool
            # executes. A node's state updates are discarded when it
            # interrupts, so executing tools before an interrupt would
            # re-run them on resume; gating first guarantees each tool
            # executes exactly once.
            decisions = {}
            for tool_call in tool_calls:
                spec = registry.get(tool_call["name"])
                if spec is not None and spec.risk == RISK_APPROVAL_REQUIRED:
                    decisions[tool_call["id"]] = interrupt(
                        {
                            "tool_call_id": tool_call["id"],
                            "tool": tool_call["name"],
                            "args": tool_call["args"],
                        }
                    )
            # Phase 2: execute every call exactly once.
            results = {}
            files = list(state.get("files") or [])
            for tool_call in tool_calls:
                decision = decisions.get(tool_call["id"])
                if decision is not None and not (
                    isinstance(decision, dict) and decision.get("approved")
                ):
                    results[tool_call["id"]] = {
                        "success": False,
                        "error": "approval denied",
                    }
                    continue
                try:
                    result = await registry.execute(
                        tool_call["name"], tool_call["args"], ctx
                    )
                except Exception as exc:  # a tool must not kill the run
                    result = {"success": False, "error": str(exc)}
                results[tool_call["id"]] = result
                if result.get("written") and result.get("path"):
                    path = result["path"]
                    if path not in files:
                        files.append(path)
                await _emit_tool_event(
                    state.get("run_id"),
                    tool_call["name"],
                    tool_call["id"],
                )
            return {
                "messages": [
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=call_id,
                    )
                    for call_id, result in results.items()
                ],
                "files": files,
            }

        def route_after_agent(state: AgentState) -> str:
            if state.get("error"):
                return END
            if state["iteration"] >= max_iterations:
                return END
            last = state["messages"][-1] if state["messages"] else None
            if last is not None and getattr(last, "tool_calls", None):
                return "tools"
            return END

        builder = StateGraph(AgentState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", tools_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent", route_after_agent, {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "agent")
        return builder.compile(checkpointer=checkpointer)

    # -- AgentExecutionEngine contract -------------------------------

    async def start_run(
        self,
        run_id: str,
        agent_id: str,
        version_id: str,
        input: Optional[dict] = None,
        initiated_by: Optional[str] = None,
        depth: int = 0,
    ) -> dict:
        graph = await self._get_graph()
        config = {"configurable": {"thread_id": run_id}}
        data = input or {}
        message = data.get("message") or data.get("prompt") or ""
        if not message and isinstance(data, str):
            message = data
        existing = await graph.aget_state(config)
        has_state = bool(existing and existing.values)
        messages = _seed_messages(data.get("conversation_history"))
        if not has_state:
            messages.insert(0, SystemMessage(content=self._system_prompt))
        messages.append(HumanMessage(content=message))
        await self._transition(run_id, QUEUED, RUNNING)
        result = None
        error = None
        try:
            result = await graph.ainvoke(
                {
                    "messages": messages,
                    "run_id": run_id,
                    "agent_id": agent_id or "",
                    "version_id": version_id or "",
                    "user_id": initiated_by or "",
                    "iteration": 0,
                    "files": [],
                    "error": None,
                    "depth": depth,
                },
                config,
            )
        except Exception as exc:
            error = str(exc)
        return await self._finish(run_id, graph, config, result, error)

    async def resume_run(
        self, run_id: str, approval: Optional[dict] = None
    ) -> dict:
        graph = await self._get_graph()
        config = {"configurable": {"thread_id": run_id}}
        await self._transition(
            run_id, WAITING_FOR_APPROVAL, RUNNING
        )
        result = None
        error = None
        try:
            result = await graph.ainvoke(
                Command(resume=approval or {}), config
            )
        except Exception as exc:
            error = str(exc)
        return await self._finish(run_id, graph, config, result, error)

    async def _execute_subagent(
        self,
        parent_run_id: Optional[str],
        user_id: Optional[str],
        agent_id: str,
        input: Optional[dict],
        depth: int = 1,
    ) -> dict:
        """Spawn and execute a child run of ``agent_id``.

        Called by the ``spawn_subagent`` tool through the
        per-run executor closure. Creates the durable
        parent/child records via the SubagentService, then
        runs the child to completion through this engine.
        """
        if not parent_run_id:
            return {
                "success": False,
                "error": "subagent spawn requires a parent run",
            }
        async with async_session_factory() as session:
            child = await get_subagent_service().spawn(
                session,
                parent_run_id=parent_run_id,
                agent_id=agent_id,
                input=input,
                initiated_by_id=user_id,
            )
        return await self.start_run(
            child.id,
            agent_id,
            child.version_id,
            input=input,
            initiated_by=user_id,
            depth=depth,
        )

    async def cancel_run(self, run_id: str) -> dict:
        async with async_session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is not None and run.status not in TERMINAL_STATUSES:
                await transition_run(session, run, CANCELLED)
                await session.commit()
        return {"run_id": run_id, "status": CANCELLED}

    async def get_state(self, run_id: str) -> Optional[dict]:
        graph = await self._get_graph()
        config = {"configurable": {"thread_id": run_id}}
        snapshot = await graph.aget_state(config)
        if snapshot is None or not snapshot.values:
            return None
        values = dict(snapshot.values)
        values["messages"] = [
            _message_to_dict(message)
            for message in values.get("messages") or []
        ]
        values["interrupted"] = bool(snapshot.next)
        return values

    # -- internals -----------------------------------------------------

    async def _transition(
        self, run_id: str, from_status: str, to_status: str
    ) -> None:
        """Transition a durable run if it currently sits in
        ``from_status`` (no-op otherwise)."""
        async with async_session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is not None and run.status == from_status:
                await transition_run(session, run, to_status)
                await session.commit()

    async def _record_pending_approval(
        self, run_id: str, interrupt_value: dict
    ) -> None:
        """Persist the gated tool call as a PENDING approval."""
        from app.agent.approval import get_approval_service

        try:
            await get_approval_service().record_pending(
                run_id, interrupt_value
            )
        except Exception:
            pass  # approval recording must not break the run

    async def _finish(
        self,
        run_id: str,
        graph,
        config: dict,
        result: Optional[dict],
        error: Optional[str],
    ) -> dict:
        paused = False
        pending_tool = None
        snapshot = await graph.aget_state(config)
        if snapshot is not None and snapshot.next:
            # Graph paused at an approval gate.
            paused = True
            pending_tool = _first_interrupt_value(snapshot)
            if pending_tool is not None:
                await self._record_pending_approval(run_id, pending_tool)
        async with async_session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is not None and run.status not in TERMINAL_STATUSES:
                if paused:
                    await transition_run(session, run, WAITING_FOR_APPROVAL)
                elif error:
                    await settle_run(
                        session, run, FAILED, error_message=error
                    )
                else:
                    await settle_run(
                        session,
                        run,
                        SUCCEEDED,
                        summary=_final_answer(result),
                    )
                await session.commit()
        result_dict = self._result_dict(run_id, result, error)
        if paused:
            result_dict["status"] = "WAITING_FOR_APPROVAL"
            result_dict["paused"] = True
            result_dict["pending_tool"] = pending_tool
        return result_dict

    def _result_dict(
        self,
        run_id: str,
        result: Optional[dict],
        error: Optional[str],
    ) -> dict:
        response = ""
        tools_called: list[str] = []
        steps = 0
        files: list[str] = []
        if result:
            for message in result.get("messages") or []:
                if isinstance(message, AIMessage) and not message.tool_calls:
                    response = message.content or ""
                for tool_call in getattr(message, "tool_calls", None) or []:
                    tools_called.append(tool_call.get("name", ""))
            steps = result.get("iteration", 0) or 0
            files = list(result.get("files") or [])
        if error:
            response = f"Error: {error}"
        return {
            "run_id": run_id,
            "status": "FAILED" if error else "SUCCEEDED",
            "response": response,
            "tools_called": tools_called,
            "steps_executed": steps,
            "files": files,
        }


def _message_to_dict(message) -> dict:
    return {
        "role": getattr(message, "type", "unknown"),
        "content": message.content if isinstance(message.content, str) else "",
        "tool_calls": getattr(message, "tool_calls", None) or None,
        "tool_call_id": getattr(message, "tool_call_id", None),
    }


def _seed_messages(history: Optional[list[dict]]) -> list:
    """Rebuild client-supplied conversation history as messages."""
    messages = []
    for entry in history or []:
        role = entry.get("role")
        content = entry.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _first_interrupt_value(snapshot) -> Optional[dict]:
    for task in getattr(snapshot, "tasks", None) or []:
        for interrupt_obj in getattr(task, "interrupts", None) or []:
            value = getattr(interrupt_obj, "value", None)
            return value if isinstance(value, dict) else None
    return None


def _final_answer(result: Optional[dict]) -> str:
    if not result:
        return ""
    for message in reversed(result.get("messages") or []):
        if isinstance(message, AIMessage) and not message.tool_calls:
            content = message.content or ""
            if content:
                return content
    return ""


async def _emit_tool_event(
    run_id: Optional[str], tool_name: str, tool_call_id: str
) -> None:
    if not run_id:
        return
    try:
        async with async_session_factory() as session:
            await emit_event(
                session,
                run_id,
                "tool_called",
                {"tool": tool_name, "tool_call_id": tool_call_id},
            )
            await session.commit()
    except Exception:
        pass


_engine: Optional[LangGraphEngine] = None


def get_engine() -> LangGraphEngine:
    global _engine
    if _engine is None:
        from app.agent.llm import get_llm_service

        _engine = LangGraphEngine(get_llm_service())
    return _engine
