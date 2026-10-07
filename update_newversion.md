# Agentic CRM — Implementation Update (Phase 0 → 4)

## Overview
This document tracks the implementation of the LangGraph-based agentic architecture for the CRM backend, following the 8-phase plan. Work completed through Phase 4 (engine + checkpointer), with Phases 5–7 pending.

---

## Phase 0 — Security Hardening (✅ 15/15 tests passing)

### Files Created
| File | Purpose |
|------|---------|
| `app/agent/tools/crm_query.py` | Allow-listed, read-only CRM queries (7 operations) with parameterized SQL |
| `app/agent/tools/filesystem.py` | Sandboxed file I/O (resolve, read, write, list, grep) confined to `AGENT_WORKSPACE_ROOT` |
| `app/agent/tools/web_fetch.py` | SSRF-safe HTTP fetch (DNS validation, private IP blocking, redirects, byte limits) |

### Files Rewritten / Hardened
| File | Changes |
|------|---------|
| `app/agent/agents/runner/tools.py` | Removed `bash`, `execute_python`, `create_chart`, `generate_pdf`; delegated to safe tool services |
| `app/agent/agents/runner/router.py` | Reduced to `GET /files/{path}` artifact serving only |
| `app/agent/agents/builder/router.py` | **Deleted** (builder agent removed) |
| `app/agent/orchestrator.py` | Pruned tool sets, removed forced `SELECT *` fallback, fail-closed `_InputObj`, rewrote system prompt |
| `app/dependencies/auth.py` | Real HS256 JWT via `python-jose`; `ROLE_HIERARCHY`; dev-mode via explicit `X-Dev-User-Email` (no `*`) |
| `app/agent/access.py` | Real RBAC against `Member.role`; `MANAGE_ROLES = ("owner", "admin")` |
| `app/config/settings.py` | Added `ENV`, `AUTH_DEV_MODE`, `AGENT_WORKSPACE_ROOT`, `AGENT_MAX_ITERATIONS`, `AGENT_MAX_TOOL_SECONDS`, `WEB_FETCH_*` |

### Test Infrastructure
| File | Purpose |
|------|---------|
| `app/tests/test_fixtures.py` | HS256 token minting, `seed_data` fixture (user_1, org_1, company_1, contact_1, deal_1) |
| `app/tests/test_agent_runner.py` | 15 security tests (endpoint removal, auth rejection, FS sandbox, SSRF, CRM validation) |
| `app/tests/conftest.py` | Sync `setup_db` (avoids `MissingGreenlet`); `seed_data` autouse via import |

### Dependency Fixes
- `pyproject.toml`: `python-multipart>=0.0.20` (was unsatisfiable `>=0.20.0`), `build-backend = "setuptools.build_meta"`
- Added: `asyncpg`, `langgraph`, `langgraph-checkpoint-postgres`, `opentelemetry-*`, `python-jose`

---

## Phase 1 — PostgreSQL + Durable Lifecycle (✅)

### Phase 1.1 — PostgreSQL Migration
- **Database**: Host PostgreSQL 18 on `127.0.0.1:5432` (role `suri`, password `crm_dev_pw`, DB `crm`)
- **Alembic scaffolding**: `alembic/env.py` (async), `alembic/script.py.mako`, baseline migration `05d363568d0c_baseline.py`
- **Migration strategy**: `Base.metadata.create_all(bind=...)` in baseline (handles circular FKs: `agentDefinition ↔ agentVersion`)
- **Schema additions**: `AgentRun.graph_thread_id` (nullable, indexed) for LangGraph checkpointer
- **Configuration**: `.env` → `DATABASE_URL=postgresql+asyncpg://suri:crm_dev_pw@127.0.0.1:5432/crm`

### Phase 1.2 — Durable Worker (`app/agent/worker.py`)
- **Claim loop**: `SELECT ... FOR UPDATE SKIP LOCKED` (priority, due_at, created_at ordering)
- **Lease**: `leased_until = now() + 300s`, `attempts++`
- **Recovery**: Stale leases → `PENDING` (retry) or `FAILED` (after 3 attempts)
- **Settlement**: Task + parent `AgentRun` (via `task.payload["run_id"]`)
- **Executor protocol**: Pluggable `TaskExecutor`; default `BridgeTaskExecutor` (POST to bridge)

### Phase 1.3 — Run Lifecycle (`app/agent/run_lifecycle.py`)
- **State machine**: `QUEUED → RUNNING → {WAITING_FOR_APPROVAL, SUCCEEDED, FAILED, CANCELLED}`
- **Validated transitions** via `TRANSITIONS` table; `InvalidTransition` exception on violation
- **Event sourcing**: Every status change emits `AgentRunEvent` with sequence number
- **Helpers**: `transition_run()`, `settle_run()`, `emit_event()`, `can_transition()`

---

## Phase 2 — Canonical Tool Registry (✅)

### `app/agent/tools/registry.py`
- **14 tools** declared with: name, description, JSON-schema parameters, risk tier, handler
- **Risk tiers**: `safe`, `approval_required` (write_file, create_crm_activity, post_slack_message)
- **Execution context**: `ToolContext(user_id, workspace_root, session)` — session optional for engine checkpointer
- **LLM schemas**: `registry.llm_schemas()` → OpenAI/Anthropic function-calling format
- **Handler pattern**: `async def handler(ctx: ToolContext, args: dict) -> dict`

### Canonical Input Schemas (moved from `tools.py`)
All pydantic models now live in the registry: `AskQuestionInput`, `QueryCRMInput`, `WriteFileInput`, `GlobInput`, `GrepInput`, `TodoInput`, `WebFetchInput`, `WebSearchInput`, `ReadFileInput`, `ReadCRMRecordInput`, `FinishRunInput`, `InspectRunInput`, `PostSlackMessageInput`, `CreateCrmActivityInput`.

### `app/agent/agents/runner/tools.py`
Now **imports** input models from the registry; `RunnerAgentTools` class retained for orchestrator until Phase 4 deletion.

### Fixes
- `crm_query.py:_rows` — fixed double-mapping bug + ORM-entity expansion (`select(Deal)` → flat column dict)

### Tests (`app/tests/test_tool_registry.py`)
10 tests covering: tool count, schema shape, unknown tool, safe tool execution, traversal blocking, risk tiers, singleton.

---

## Phase 3 — LLM Adapter Rewrite (✅ 9/9 tests passing)

### `app/agent/llm.py`
| Feature | Implementation |
|---------|----------------|
| **Native tool calls** | `ToolCall(id, name, arguments)` parsed from provider `tool_calls`; **no JSON scraping** |
| **Token extraction** | Ollama: `prompt_eval_count` / `eval_count`; GroQ: `usage.prompt_tokens` / `completion_tokens` |
| **Cost accounting** | GroQ cost via `_estimate_cost()`; Ollama = $0.0 |
| **LLMCallLog persistence** | Every call logged via `async_session_factory` with `agent_id`, `run_id`, tokens, cost, error |
| **Provider fallback** | Ollama error + GroQ key configured → retry on GroQ |
| **Provider resolution** | Explicit model → GroQ; else Ollama if configured; else GroQ |

### `app/tests/test_llm.py` (rewritten)
- Mocked via `httpx.MockTransport` (no network)
- Tests: native tool calls, argument parsing (invalid JSON → `{}`), fallback, LLMCallLog persistence, cost estimation

---

## Phase 4 — AgentExecutionEngine + LangGraphEngine (✅ 13/13 tests passing)

### Architecture
```
AgentExecutionEngine (interface)
    └── LangGraphEngine (implementation)
        ├── StateGraph (agent → tools → agent)
        ├── AsyncPostgresSaver (same PG instance, public schema)
        ├── interrupt() for approval gates
        └── Command(resume=...) for resume
```

### Files Created / Rewritten

| File | Purpose |
|------|---------|
| `app/agent/engine.py` | `AgentExecutionEngine` ABC: `start_run`, `resume_run`, `cancel_run`, `get_state` |
| `app/agent/langgraph_engine.py` | Full engine with two-phase tools node, checkpointer, system prompt |
| `app/agent/unified_router.py` | Rewritten to use `LangGraphEngine`; supports thread continuation + HITL |
| `app/agent/orchestrator.py` | **Deleted** (single engine replaces plan-then-execute loop) |

### Engine Details (`langgraph_engine.py`)

**State (`AgentState`)**
```python
messages: Annotated[list, add_messages]
run_id, agent_id, version_id, user_id: str
iteration: int
files: list
error: Optional[str]
```

**Graph Nodes**
1. **agent** — calls `llm.chat()` with `registry.llm_schemas()`, returns `AIMessage` (+ `tool_calls`)
2. **tools** — two-phase:
   - Phase 1: scan all tool calls; `interrupt()` for `approval_required` **before any execution**
   - Phase 2: execute **every** call exactly once (safe + approved); emit `tool_called` events
3. **routing** — `agent → tools` if `tool_calls` else `END`

**Run Transitions**
- `start_run`: `QUEUED → RUNNING` (if run exists) → `ainvoke()` → `_finish()`
- `resume_run`: `WAITING_FOR_APPROVAL → RUNNING` → `ainvoke(Command(resume=...))` → `_finish()`
- `_finish()` inspects `snapshot.next`:
  - interrupted → `WAITING_FOR_APPROVAL`
  - error → `FAILED`
  - clean → `SUCCEEDED` + summary

**Checkpointer**
- `AsyncPostgresSaver` on same PG instance (`asyncpg` connection from `settings.DATABASE_URL`)
- Thread ID = `run_id` (maps to `AgentRun.graph_thread_id`)

**Thread Continuation**
- `start_run` detects existing checkpoint via `graph.aget_state(thread_id)`
- If state exists: seeds only new `HumanMessage`; else seeds `SystemMessage` + history + new message
- `conversation_history` in input dict rebuilds prior turns

### Worker Integration (`app/agent/worker.py`)
- **WorkerExecutor**: routes tasks by payload
  - `payload["run_id"]` → `AgentExecutionEngine.start_run()`
  - else → `BridgeTaskExecutor` (CRM dispatch)
- `get_worker()` returns `AgentWorker(executor=WorkerExecutor(get_engine()))`

### Services (`app/agent/services.py`)
- `run_now` now stores `input_data` in `AgentRun.input` (JSON) for durable re-execution
- Creates `AgentTask` with `payload={"run_id": run_id}` for worker pickup

### Unified Router (`app/agent/unified_router.py`)
- `/chat` → creates synthetic `thread_id`, calls `engine.start_run()` inline, returns `ChatResponse`
- `/tasks/{task_id}/approve` → `engine.resume_run(task_id, {"approved": True})`
- Supports `conversation_history` seeding, `paused` / `pending_tool` in response

### Model Change
- `AgentRun.input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` — migration `6a38d7f18f65`

---

## Test Status

| Suite | Tests | Status |
|-------|-------|--------|
| `test_agent_runner.py` | 15 | ✅ |
| `test_agent_lifecycle.py` | 14 | ✅ |
| `test_tool_registry.py` | 10 | ✅ |
| `test_llm.py` | 9 | ✅ |
| `test_agent_root.py` | 22 | ✅ |
| `test_agent_crud.py` | 7 | ✅ |
| `test_agent_utils.py` | 3 | ✅ |
| `test_langgraph_engine.py` | 13 | ✅ |
| `test_agent_approval.py` | 12 | ✅ |
| `test_otel.py` | 6 | ✅ |
| `test_subagents.py` | 9 | ✅ |

**Total: 141 tests passing.**

### Phase 4 Bugs Fixed During Testing
1. **Identity-map staleness**: engine writes via its own session; tests must read via fresh sessions (`_fresh_get` helper), not the shared `db_session` fixture.
2. **LangChain tool_call key**: langchain `tool_calls` dicts use key `args`, not `arguments`. The tools node originally accessed `tool_call["arguments"]` → `KeyError` → interrupt never fired. Fixed to `tool_call["args"]`.
3. **Two-phase tools node**: a node's state updates are discarded when it interrupts, so tools executed before an interrupt would re-run on resume. Fixed by resolving ALL approval gates first (Phase 1: interrupt scan), then executing every call exactly once (Phase 2).
4. **Run transitions**: `start_run` transitions `QUEUED → RUNNING`; `resume_run` transitions `WAITING_FOR_APPROVAL → RUNNING` before resuming.

## Phase 5 — Durable HITL (✅ 12/12 tests passing)

### `AgentApproval` Model (`models.py`)
| Column | Type | Notes |
|--------|------|-------|
| `id` | String PK | uuid |
| `run_id` | String FK → agentRun.id | indexed |
| `tool_call_id` | String | the gated tool call |
| `tool_name` | String | e.g. `write_file` |
| `args` | JSON | tool arguments |
| `status` | String | PENDING / APPROVED / DENIED (indexed) |
| `approver_id` | String FK → user.id | nullable |
| `idempotency_key` | String | unique |
| `created_at` / `decided_at` | DateTime | |

### `app/agent/approval.py` — ApprovalService
- **`record_pending(run_id, interrupt_value)`** — persists PENDING approval; idempotent per (run_id, tool_call_id)
- **`list_for_run(run_id)`** — all approvals for a run
- **`decide(run_id, tool_call_id, decision, approver_id, idempotency_key)`**:
  - **Authorization**: approver must be `run.initiated_by_id` OR org owner/admin (`AgentAccessService.can_admin`)
  - **Idempotency**: repeated `idempotency_key` returns the recorded decision without re-processing
  - **Validation**: decision must be `approve` / `deny`

### Engine Integration
- `_finish()` calls `_record_pending_approval()` when the graph pauses → PENDING `AgentApproval` row created automatically

### API Endpoints (`unified_router.py`)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agents/unified/runs/{run_id}/approvals` | GET | List approvals for a run |
| `/api/agents/unified/runs/{run_id}/approvals` | POST | Decide + resume engine |

**POST body**: `{tool_call_id, decision: "approve"|"deny", idempotency_key?}`
**Response**: `{approval: {...}, run_result: {...}}`

### Test Event-Loop Fix
Endpoint tests use `httpx.AsyncClient` + `ASGITransport` (not `TestClient`), so endpoints execute in the test's event loop and share aiosqlite connections with the open `db_session`. `TestClient` runs in a separate loop and cannot see data committed by the still-open session.

## Phase 6 — OpenTelemetry (✅ 6/6 tests passing)

### `app/telemetry/otel.py`
- `init_telemetry(provider=None, processor=None)` — module-local `TracerProvider` (NOT the process-global one, which can only be set once and breaks per-test in-memory exporters)
- `get_tracer(name)` — returns a tracer from the module-local provider
- `reset_telemetry()` — shuts down and clears (tests only)
- **Exporter selection**: OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; console when `OTEL_CONSOLE_EXPORTER=true`; otherwise spans are created and dropped (no background thread — avoids the "I/O operation on closed file" shutdown error in tests)
- `init_telemetry` also best-effort calls `trace.set_tracer_provider()` so `FastAPIInstrumentor` picks it up in production

### Instrumented operations (manual spans)
| Span | Location | Key attributes |
|------|----------|----------------|
| `llm.chat` | `agent/llm.py` | `llm.provider`, `llm.model`, `llm.tools`, `llm.agent_id`, `llm.run_id`, `llm.input_tokens`, `llm.output_tokens`, `llm.cost_usd`; ERROR status on failure |
| `tool.execute` | `agent/tools/registry.py` | `tool.name`, `tool.risk`, `tool.success`; ERROR on unknown tool / failure |
| `run.transition` | `agent/run_lifecycle.py` | `run.id`, `run.from`, `run.to`; ERROR on invalid transition |
| HTTP requests | `main.py` | `FastAPIInstrumentor.instrument_app(app)` (production `create_app` only; `create_test_app` is un-instrumented) |

### Tests (`test_otel.py`)
In-memory exporter via session-scoped fixture; verifies run transitions (valid + invalid→ERROR), tool execution (valid + unknown→ERROR), and LLM chat (success + error→ERROR) all emit spans with correct attributes.

---

## Phase 7 — Subagents (✅ 9/9 tests passing)

### Data Model (`models.py`, migration `4b2a91c7d0e3`)
- `AgentRun.parent_run_id` — String FK → agentRun.id, nullable, indexed
- `AgentRun.child_run_ids` — JSON array (denormalized for easy listing)

### `app/agent/subagents.py` — SubagentService
- **`spawn(session, *, parent_run_id, agent_id, input, initiated_by_id)`** — resolves the child `AgentDefinition` (must exist and be `LIVE`), creates a child `AgentRun` (`trigger_type="SUBAGENT"`, `parent_run_id` set, `version_id` = agent's `current_version_id`), creates a durable `AgentTask` the worker can claim, and appends the child id to the parent's `child_run_ids`. Does **not** execute the child — the caller runs it via the engine.
- **`list_children(session, run_id)`** — direct children of a run
- **`get_parent(session, run_id)`** — parent of a run, if any
- `SubagentError` for unknown / non-LIVE agents

### `spawn_subagent` Tool (canonical registry)
- Input: `{agentId, input?}`
- Handler uses `ToolContext.subagent_executor` (engine-supplied) — the registry stays engine-neutral; the engine provides execution
- Guards: no executor → error; `ctx.depth >= MAX_SUBAGENT_DEPTH` (3) → error

### Engine Integration (`langgraph_engine.py`)
- `AgentState` gains `depth` (subagent nesting level, 0 = top-level)
- `tools_node` builds `ToolContext` with `run_id`, `depth`, and a per-run `subagent_executor` closure that calls `_execute_subagent(..., depth=current_depth + 1)`
- **`_execute_subagent`** — spawns the child via `SubagentService`, then runs it to completion via `start_run(child.id, ..., depth=depth)`
- `start_run` accepts `depth` and seeds it into the graph state

### End-to-end
A parent run whose LLM calls `spawn_subagent` creates a child `AgentRun` (with `parent_run_id` set, `child_run_ids` updated on the parent), executes the child to `SUCCEEDED`, and returns the child's result to the parent as a `ToolMessage`.

### Tests (`test_subagents.py`)
Spawn/parent-link/task creation, list_children, get_parent, unknown-agent and non-LIVE-agent errors, tool executor wiring, no-executor and depth-limit guards, and a full parent→child engine run.

---

## All Phases Complete

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Security (sandboxed tools, JWT auth, RBAC) | ✅ |
| 1 | PostgreSQL, durable worker, run lifecycle | ✅ |
| 2 | Canonical tool registry | ✅ |
| 3 | LLM adapter (native tool calls, cost accounting) | ✅ |
| 4 | LangGraph execution engine | ✅ |
| 5 | Durable human-in-the-loop approvals | ✅ |
| 6 | OpenTelemetry tracing | ✅ |
| 7 | Subagent parent/child runs | ✅ |

---

## Key Files Index

```
app/
├── agent/
│   ├── engine.py                    # AgentExecutionEngine ABC
│   ├── langgraph_engine.py          # LangGraphEngine (core)
│   ├── worker.py                    # Worker + WorkerExecutor
│   ├── run_lifecycle.py             # State machine + events
│   ├── unified_router.py            # Chat + approve endpoints
│   ├── llm.py                       # LLM adapter (native tool calls)
│   ├── tools/
│   │   ├── registry.py              # Canonical tool registry
│   │   ├── crm_query.py             # Allow-listed CRM queries
│   │   ├── filesystem.py            # Sandboxed FS
│   │   └── web_fetch.py             # SSRF-safe HTTP
│   ├── agents/runner/tools.py       # Runner tools (imports from registry)
│   ├── dependencies/auth.py         # JWT + dev-mode auth
│   ├── access.py                    # RBAC
│   └── config/settings.py           # Settings
├── database/
│   ├── models.py                    # AgentRun.input, graph_thread_id
│   └── session.py                   # Async engine/session
├── alembic/
│   ├── env.py                       # Async env
│   ├── script.py.mako               # Template
│   └── versions/
│       ├── 05d363568d0c_baseline.py
│       └── 6a38d7f18f65_agent_run_input_column.py
└── tests/
    ├── test_agent_runner.py
    ├── test_agent_lifecycle.py
    ├── test_tool_registry.py
    ├── test_llm.py
    ├── test_langgraph_engine.py
    └── conftest.py                  # Sync seed + async fixtures
```

---

## Commands

```bash
# Run all tests (except pre-existing LLM network failures)
cd /home/suri/proj/crm/backend
.venv/bin/python -m pytest app/tests/ -q --ignore=app/tests/test_llm.py

# Run engine tests specifically
.venv/bin/python -m pytest app/tests/test_langgraph_engine.py -q

# DB migrations
.venv/bin/alembic revision --autogenerate -m "message"
.venv/bin/alembic upgrade head

# Worker (separate process)
.venv/bin/python -m app.agent.worker
```

---

## Notes for Next Session

1. The engine uses `MemorySaver` in tests; production uses `AsyncPostgresSaver` (same PG instance). Consider an `AsyncSqliteSaver` for closer test/prod parity if needed.
2. Endpoint tests must use `AsyncClient` + `ASGITransport` (same event loop) when they read DB state written by an open `db_session`.
3. Telemetry: the module-local provider pattern in `otel.py` is required because the process-global tracer provider can only be set once — do not switch back to `trace.get_tracer()`.
4. Subagents: `MAX_SUBAGENT_DEPTH = 3` in `registry.py` guards recursion. The registry stays engine-neutral — the engine injects `subagent_executor` via `ToolContext`.
5. `start_all.sh` still runs bare `python3 -m uvicorn` and seeds via raw sqlite3 — needs venv/PG update.
6. Remaining nice-to-haves: LangGraph `Send` for fan-out/map-reduce (currently subagents are sequential spawn-and-wait), and an admin endpoint to list a run's children via `SubagentService.list_children`.