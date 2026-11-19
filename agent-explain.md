# Agentic Layer — Architecture & Implementation Explained

A complete walkthrough of the agentic layer in `backend/app/agent/`: what LangGraph
is, how it is wired, how many agents exist, how the graph flows, how SQL queries /
file operations / code execution / web access work, human-in-the-loop approvals,
subagents, telemetry, and a technical Q&A.

---

## Table of Contents

1. [Big Picture](#1-big-picture)
2. [What is LangGraph?](#2-what-is-langgraph)
3. [The Graph (nodes, edges, state)](#3-the-graph)
4. [How Many Agents Are There?](#4-how-many-agents-are-there)
5. [The Tool Registry & Risk Tiers](#5-the-tool-registry--risk-tiers)
6. [End-to-End Request Flow](#6-end-to-end-request-flow)
7. [Human-in-the-Loop (Approvals)](#7-human-in-the-loop-approvals)
8. [How SQL Queries Work](#8-how-sql-queries-work)
9. [How File Operations Work](#9-how-file-operations-work)
10. [How Code Execution Works (and what is disabled)](#10-how-code-execution-works)
11. [How Web Access Works (SSRF-safe)](#11-how-web-access-works)
12. [How Subagents Work](#12-how-subagents-work)
13. [The Durable Worker](#13-the-durable-worker)
14. [LLM Adapter](#14-llm-adapter)
15. [Classification with Laya](#15-classification-with-laya)
16. [Telemetry (OpenTelemetry)](#16-telemetry-opentelemetry)
17. [Technical Q&A](#17-technical-qa)
18. [Future Scope](#18-future-scope)

---

## 1. Big Picture

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  Frontend (Vite + React 19) │        │  Backend (FastAPI + Python)      │
│  crm-ui/src/pages/          │  HTTP  │  app/                            │
│   UnifiedChatPage.jsx       │───────▶│   agent/                         │
│   TelemetryPage.jsx         │        │    unified_router.py  (API)      │
│  crm-ui/src/lib/api.js      │◀───────│    langgraph_engine.py (engine)  │
└─────────────────────────────┘        │    tools/registry.py (15 tools)  │
                                       │    llm.py (Ollama/GroQ adapter)  │
                                       │    approval.py (HITL)            │
                                       │    subagents.py (child runs)     │
                                       │    worker.py (durable tasks)     │
                                       │    run_lifecycle.py (state mach.)│
                                       │    telemetry/otel.py (OTel)      │
                                       └──────────────┬───────────────────┘
                                                      │
                        ┌─────────────────────────────┼─────────────────────────┐
                        ▼                             ▼                         ▼
                 ┌─────────────┐            ┌──────────────────┐       ┌──────────────┐
                 │ PostgreSQL  │            │  LLM providers   │       │  Web (SSRF-  │
                 │  - CRM data │            │  Ollama (local)  │       │  safe) APIs  │
                 │  - checkpoints│           │  GroQ (cloud)    │       │              │
                 │  - approvals│            └──────────────────┘       └──────────────┘
                 │  - LLM logs │
                 └─────────────┘
```

The **Unified Agent** is the only agent that runs the full LangGraph engine. It plans,
calls tools, loops, pauses for human approval, and can spawn child runs (subagents).

---

## 2. What is LangGraph?

**LangGraph** is a library for building **stateful, multi-step agent workflows as graphs**.

Mental model: a flowchart that an LLM drives.

- **Node** = a unit of work (a Python async function). Here: `agent` (call the LLM) and `tools` (run tool calls).
- **Edge** = an allowed transition between nodes. Can be unconditional (`add_edge`) or conditional (`add_conditional_edges` with a router function).
- **State** = a shared dictionary (`AgentState`) that flows through the graph and accumulates. Each node returns a *partial* update that is merged in.
- **Checkpointer** = saves state after every step so a crashed run resumes from its last checkpoint.
- **`interrupt()`** = pauses the graph and hands control back to the caller (used for human approval).
- **`Command(resume=...)`** = resumes an interrupted graph with a value.

Key property: a graph is **not** a free-form loop — the LLM can only move between nodes you declared, and only along edges you declared. This makes the agent's behavior bounded and auditable.

---

## 3. The Graph

File: `backend/app/agent/langgraph_engine.py` (`_build_graph`, line ~167).

### Nodes

```
START ──▶ [agent] ──route_after_agent──▶ (tool_calls?) ──yes──▶ [tools] ──▶ [agent] ──...
                            │
                            no
                            ▼
                           END
```

- **`agent_node`**: calls `llm.chat(...)` with all 15 tool schemas (`registry.llm_schemas()`). Returns an `AIMessage` (with `tool_calls` if the LLM wants tools, else plain content). Increments `iteration`.
- **`tools_node`**: executes the returned tool calls via `registry.execute(...)`. Two-phase (see §7). Returns `ToolMessage`s.
- **`route_after_agent`**: returns `"tools"` if the last message has `tool_calls`, else `END`. Also ends on `error` or `iteration >= MAX_ITERATIONS` (15).

### State

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # auto-append reducer
    run_id: str
    agent_id: str
    version_id: str
    user_id: str
    iteration: int      # loop guard (max 15)
    files: list         # generated artifact paths
    error: Optional[str]
    depth: int          # subagent nesting level (0 = top-level)
```

`add_messages` is a **reducor**: each node's `{"messages": [new_msg]}` is appended to the existing list rather than replacing it.

### Is the graph bidirectional?

**No — it is a directed graph.** Edges have a direction:
- `START → agent` (unconditional)
- `agent → tools` (conditional, when tool calls exist)
- `agent → END` (conditional, when no tool calls / error / max iterations)
- `tools → agent` (unconditional — the loop back)

There is **no edge from `tools` back to `START`** and **no edge from `END` to anything**. The only cycle is the `agent → tools → agent` loop, bounded by `MAX_ITERATIONS = 15`. So execution always terminates.

### Checkpointer

```python
AsyncPostgresSaver(asyncpg_connection)   # production
MemorySaver()                            # tests
```
The checkpointer stores state in PostgreSQL (the **same instance** as the CRM DB — deliberately, per the architecture constraints). The run's `graph_thread_id` is the checkpoint thread id, so a crashed worker's run is resumable.

---

## 4. How Many Agents Are There?

**Four agent surfaces + subagents.** Only one uses the full LangGraph engine.

| Agent | API prefix | Role | Implementation |
|-------|-----------|------|----------------|
| **Unified Agent** | `/api/agents/unified` | Main agentic agent: plans, calls tools, loops, asks for approvals, spawns subagents | `LangGraphEngine` (full `StateGraph`) |
| **Root Agent** | `/api/agents/root/*` | CRM intelligence: `search_crm`, `research_person`, `research_company`, `identify_contact`, `list_deals`, `write_brief`, … | `CRMService` (direct service calls, **no graph**) |
| **Runner Agent** | `/api/agents/runner/*` | Serves generated artifacts (charts/PDFs) via `GET /files/{path}`. Its *tools* are invoked **only** by the engine, never as public routes | `get_file` endpoint only |
| **Builder Agent** | `/api/agents/builder/*` | Workspace/code agent: `bash`, `read_file`, `write_file`, `glob`, `grep`, … | Direct tool endpoints |
| **Subagents** | — | Child runs spawned by the unified agent via the `spawn_subagent` tool | `SubagentService` + recursive `start_run` |

**Important security boundary:** Runner's tools (bash, query_crm, write_file, …) are **not** exposed as HTTP endpoints. They live in the canonical registry and are invoked only by the engine. This prevents the LLM-tool surface from being a public API.

---

## 5. The Tool Registry & Risk Tiers

File: `backend/app/agent/tools/registry.py`.

The registry is the **single source of truth** for tools. Each `ToolSpec` has:
`name`, `description`, `parameters` (JSON schema), `risk`, `handler`.

**15 tools:**

| Tool | Risk | Purpose |
|------|------|---------|
| `ask_question` | safe | Ask the user a question |
| `query_crm` | safe | Allow-listed read-only CRM queries (§8) |
| `finish_run` | safe | Finish the run with a summary/result |
| `glob` | safe | List files in the workspace |
| `grep` | safe | Search workspace file contents |
| `inspect_run` | safe | Inspect an agent run by id |
| `read_crm_record` | safe | Read a single CRM record |
| `read_file` | safe | Read a workspace text file |
| `spawn_subagent` | safe | Spawn a child run (§12) |
| `todo` | safe | Record/update a to-do item |
| `web_fetch` | safe | SSRF-safe HTTP fetch (§11) |
| `web_search` | safe | Web search |
| `create_crm_activity` | **approval_required** | Log a call/email/meeting/note |
| `post_slack_message` | **approval_required** | Post to a Slack channel |
| `write_file` | **approval_required** | Write a file in the workspace |

**Risk tiers** (`RISK_SAFE`, `RISK_APPROVAL_REQUIRED`, `RISK_BLOCKED`): the engine gates tools on these. `approval_required` tools pause the graph via `interrupt()`.

The registry is **engine-neutral** — it knows nothing about LangGraph. The engine injects a `subagent_executor` closure into `ToolContext` so `spawn_subagent` can create child runs.

---

## 6. End-to-End Request Flow

### Example A — read-only query
> **User:** "Show me the deals pipeline"

```
Frontend                                Backend                                   LangGraph
  │  POST /api/agents/unified/chat       │                                           │
  │  {message:"Show deals..."}           │                                           │
  │─────────────────────────────────────▶│ unified_chat()                            │
  │                                      │ thread_id = task_id or uuid4()            │
  │                                      │ engine.start_run(thread_id,"unified",…)   │
  │                                      │──────────────────────────────────────────▶│
  │                                      │  transition_run(QUEUED→RUNNING)           │
  │                                      │  graph.ainvoke({messages:[System,Human]}) │
  │                                      │                                           │
  │                                      │   ┌─[agent] LLM → tool_calls:[query_crm] │
  │                                      │   │  route_after_agent → "tools"          │
  │                                      │   │ [tools] query_crm is SAFE → execute   │
  │                                      │   │  → ToolMessage(pipeline rows)         │
  │                                      │   │ loop back to [agent]                  │
  │                                      │   └─[agent] LLM → text summary (no calls)│
  │                                      │  no tool_calls → END                      │
  │                                      │  settle_run(SUCCEEDED)                    │
  │                                      │◀──────────────────────────────────────────│
  │◀─ {response, tools_called:["query_crm"], status:"SUCCEEDED", run_id, …} ───────│
```

### Example B — write operation needing approval
> **User:** "Log a call with John at Acme"

```
[agent] → LLM returns create_crm_activity tool_call
[tools] → Phase 1: create_crm_activity is APPROVAL_REQUIRED
          → interrupt({tool_call_id, tool, args})
          → graph PAUSES, state checkpointed
          → engine._finish() detects pause → WAITING_FOR_APPROVAL
          → _record_pending_approval() → AgentApproval row (PENDING)
Backend returns {paused:true, pending_tool, run_id}
Frontend polls GET /api/agents/unified/runs/{run_id}/approvals
User clicks Approve:
  POST /runs/{run_id}/approvals {tool_call_id, decision:"approve", idempotency_key}
  → ApprovalService.decide()  (authz + idempotency)
  → engine.resume_run(run_id, {approved:true})
  → graph resumes: tools_node Phase 2 executes create_crm_activity
  → loop to [agent] → final answer
```

### Example C — delegation to a subagent
> **User:** "Research the company and write a brief"

```
[agent] → LLM returns spawn_subagent(agentId="research_agent", input={…})
[tools] → handler → ctx.subagent_executor(run_id, user_id, agent_id, input)
          → engine._execute_subagent():
              SubagentService.spawn() → child AgentRun (parent_run_id set,
                                        parent.child_run_ids appended)
              engine.start_run(child.id, …, depth=parent.depth+1)
              → child runs its own full graph loop to SUCCEEDED
          → child result returned as ToolMessage to parent
[agent] → LLM uses child result → final answer
```
Depth guard: `MAX_SUBAGENT_DEPTH = 3`.

---

## 7. Human-in-the-Loop (Approvals)

### Why two-phase tools node?
A node's state updates are **discarded** when it interrupts. So if you executed tools *then* interrupted, the executed work would be lost and re-run on resume. Solution:

- **Phase 1** — scan all tool calls; for every `approval_required` one, call `interrupt(...)`. No tool runs yet.
- **Phase 2** — execute every call exactly once (denied ones short-circuit to `{success:false, error:"approval denied"}`).

This guarantees **exactly-once** tool execution across pause/resume.

### The approval record
`AgentApproval` model (`models.py`): `id`, `run_id` (FK), `tool_call_id`, `tool_name`, `args` (JSON), `status` (PENDING/APPROVED/DENIED), `approver_id`, `idempotency_key` (unique), `created_at`, `decided_at`.

### ApprovalService (`approval.py`)
- `record_pending(run_id, interrupt_value)` — idempotent per `(run_id, tool_call_id)`.
- `list_for_run(run_id)`.
- `decide(run_id, tool_call_id, decision, approver_id, idempotency_key)`:
  - **Authorization**: approver must be `run.initiated_by_id` OR org owner/admin (`AgentAccessService.can_admin`).
  - **Idempotency**: a repeated `idempotency_key` returns the recorded decision without re-processing.
  - **Validation**: `decision` must be `approve` / `deny`.

### API
- `GET /api/agents/unified/runs/{run_id}/approvals` → list approvals.
- `POST /api/agents/unified/runs/{run_id}/approvals` body `{tool_call_id, decision, idempotency_key?}` → decide + resume engine → `{approval, run_result}`.

---

## 8. How SQL Queries Work

**The LLM never writes SQL.** Raw LLM-generated SQL execution was deliberately removed (it was a SQL-injection / data-exfiltration risk). Instead:

`query_crm` tool → `CrmQueryService` (`tools/crm_query.py`) → an **allow-list** of 8 parameterized operations, all built with SQLAlchemy against the ORM models:

| Operation | Required params | Optional |
|-----------|-----------------|----------|
| `list_companies` | — | `limit` |
| `list_deals` | — | `stage`, `owner_id`, `company_id`, `limit` |
| `search_contacts` | — | `query` (≥2 chars), `limit` |
| `search_companies` | — | `query` (≥2 chars), `limit` |
| `deal_pipeline` | — | — (GROUP BY stage with count + sum) |
| `contact_timeline` | `contact_id` | `limit` |
| `company_contacts` | `company_id` | `limit` |
| `deal_summary` | `deal_id` | — |

`execute()` validates: unknown operation → error; unknown params → error; missing required → error. Every value is bound as a parameter (`.where(Deal.stage == stage)`), never string-interpolated. `MAX_ROWS = 100` caps results.

So "how do SQL queries work?" → **they don't, in the dangerous sense.** The LLM picks a named operation + validated params; SQLAlchemy builds safe, parameterized SQL.

---

## 9. How File Operations Work

`tools/filesystem.py`. All operations are **confined to `AGENT_WORKSPACE_ROOT`**:

- `workspace_root()` → `Path(settings.AGENT_WORKSPACE_ROOT).resolve()`.
- `resolve_workspace_path(path)` → resolves the requested path and **raises `WorkspaceError` if it escapes the workspace root** (path-traversal protection).
- `read_text_file`, `write_text_file`, `list_workspace` (glob), `grep_workspace`.

`grep_workspace` uses `subprocess.run(["grep", "-r", "-I", "--", pattern, search_dir], timeout=30)` — but `search_dir` is always the resolved workspace root (or a validated subpath), so the grep cannot escape.

`write_file` is `approval_required` — it pauses for human approval before writing.

---

## 10. How Code Execution Works

**Arbitrary code execution is disabled.** In Phase 0, the `bash` and `execute_python` tools were **removed** from the canonical registry. There is no `subprocess` call to an arbitrary shell, no `eval`, no `exec` of model-provided code.

The only `subprocess` usage is the sandboxed `grep` described in §9. The `create_chart` and `generate_pdf` tools were also removed.

If you need the agent to compute (e.g., "analyze these deals"), the intended pattern is:
1. `query_crm` to fetch the data (read-only, safe).
2. The LLM reasons over the data and writes the analysis in its text response, or
3. `write_file` (approval-gated) to persist a report.

This is a deliberate security trade-off: no code execution means no `rm -rf`, no reverse shells, no arbitrary network calls from the sandbox.

---

## 11. How Web Access Works (SSRF-safe)

`tools/web_fetch.py` → `safe_fetch(url)`:

- Rejects non-`http`/`https` schemes.
- Rejects `localhost` / `*.localhost`.
- Rejects private / loopback / link-local / multicast IPs (via `ipaddress`), and non-global literal IPs.
- DNS-resolves the hostname and re-checks the resolved IP (anti-DNS-rebinding).
- Uses `httpx.AsyncClient` with a timeout; returns status + body.

So the agent can fetch public URLs but cannot reach internal services (`127.0.0.1`, `10.x`, `192.168.x`, `169.254.169.254` metadata endpoint, etc.).

---

## 12. How Subagents Work

**Data model** (`models.py`, migration `4b2a91c7d0e3`):
- `AgentRun.parent_run_id` — FK to `agentRun.id`, nullable, indexed.
- `AgentRun.child_run_ids` — JSON array (denormalized for easy listing).

**`SubagentService` (`subagents.py`)**:
- `spawn(session, *, parent_run_id, agent_id, input, initiated_by_id)`:
  - Resolves the child `AgentDefinition` (must exist and be `LIVE`, else `SubagentError`).
  - Creates a child `AgentRun` (`trigger_type="SUBAGENT"`, `parent_run_id` set, `version_id` = agent's `current_version_id`).
  - Creates a durable `AgentTask` the worker can claim.
  - Appends the child id to the parent's `child_run_ids`.
  - Does **not** execute the child — the caller runs it via the engine.
- `list_children(run_id)`, `get_parent(run_id)`.

**Engine integration** (`langgraph_engine.py`):
- `AgentState.depth` tracks nesting (0 = top-level).
- `tools_node` builds a `ToolContext` with `run_id`, `depth`, and a per-run `subagent_executor` closure that calls `_execute_subagent(..., depth=current_depth + 1)`.
- `_execute_subagent` spawns via `SubagentService`, then runs the child to completion via `start_run(child.id, …, depth=depth)`.
- `start_run` accepts `depth` and seeds it into the graph state.

The `spawn_subagent` tool handler checks `ctx.depth >= MAX_SUBAGENT_DEPTH` (3) and refuses beyond that.

---

## 13. The Durable Worker

`worker.py` → `AgentWorker`:
- `claim_next_task()` — `SELECT … FOR UPDATE SKIP LOCKED` (atomic claim; multiple workers can poll safely). Orders by `priority`, `due_at`, `created_at`.
- **Lease**: sets `leased_until = now + 300s` and increments `attempts`.
- `recover_stale_leases()` — stale leases (past `leased_until`) reset to `PENDING`, or `FAILED` after `MAX_ATTEMPTS = 3`.
- `process_task()` — routes by `payload`: if `payload.run_id` → `engine.start_run(...)`; else → `BridgeTaskExecutor`.
- `run_loop(poll_interval)` — poll → claim → process → settle.

This makes runs **durable**: a crashed worker's task is re-claimed by another worker (or the same one after lease expiry), and the LangGraph checkpointer lets the run resume from its last checkpoint.

---

## 14. LLM Adapter

`llm.py` → `LLMService`:
- **Providers**: Ollama (local, `OLLAMA_BASE_URL`/`OLLAMA_MODEL`) and GroQ (cloud, `GROQ_API_KEY`/`GROQ_MODEL`).
- `_resolve_provider(model)` → `(provider, resolved_model)`.
- **Native function calling**: `_extract_tool_calls` reads provider tool-call objects into `ToolCall(id, name, arguments)` dataclasses. **Never** scrapes JSON out of response text.
- **Fallback**: if Ollama errors and a GroQ key is set, retries on GroQ.
- **Token/cost accounting**: Ollama → `prompt_eval_count`/`eval_count`; GroQ → `usage.prompt_tokens`/`completion_tokens`; `_estimate_cost` for GroQ.
- **Logging**: `_log_call` persists every call to `LLMCallLog` (agent_id, run_id, provider, model, prompt, response, tokens, cost_usd, success, error).

---

## 15. Classification with Laya

Laya's classification endpoint is a good fit for bounded decisions that do not
need an LLM's open-ended generation. The API accepts a state object and a set
of typed questions, then returns an answer and probabilities for each choice.
In this architecture, Laya should be a **decision signal**, not an authority:
the backend still validates inputs, applies policy, checks permissions, and
executes only allow-listed actions.

### Recommended decision boundary

```
request / CRM state
        │
        ▼
deterministic features and policy checks
        │
        ├── known/high-confidence case ──▶ deterministic result
        │
        └── ambiguous case ──▶ Laya classification
                                  │
                                  ▼
                         threshold + schema validation
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
              permitted action             LLM or human fallback
```

The Laya call should be isolated behind a small adapter. Keep
`LAYA_API_KEY` server-side, set a short timeout, call `raise_for_status()`,
and validate the response before using it. Do not pass raw model output
directly to a tool or CRM write.

The implemented adapter is `app/agent/laya.py`. On the first `agent` node
execution, `LangGraphEngine` classifies the current user message when
`LAYA_API_KEY` is configured, stores the bounded result in checkpointed graph
state, and supplies it to the LLM as advisory context. It does not replace
the LLM's final response or the tool registry. If Laya is unavailable, the
default `LAYA_FALLBACK="llm"` path records the fallback reason in the
advisory context and continues through the existing LLM flow.

### Lead qualification and scoring

Use structured CRM fields such as company size, industry, role, budget,
engagement, and historical conversions to calculate a deterministic baseline
score. Use Laya only for ambiguous or unstructured signals, for example a
free-text qualification note. Return:

- a normalized score with a documented range;
- a qualification category such as `high`, `medium`, or `low`;
- reason codes that can be stored and audited;
- the model probabilities and a confidence decision.

This replaces repeated LLM calls that score the same structured lead. For
larger labeled datasets, LightGBM or XGBoost is a better eventual scoring
model; a rules-based score is the simplest initial implementation.

### Agent routing

Route known requests with deterministic rules using intent, CRM state, and
task requirements. For ambiguous requests, ask Laya to choose only from a
bounded set:

```json
{
  "intent": {
    "type": "choice",
    "instructions": "Which agent should handle this request?",
    "criteria": {
      "research": "needs company or contact research",
      "qualification": "needs lead scoring or qualification",
      "outreach": "needs an email or other prospect communication",
      "meeting": "needs meeting scheduling or preparation",
      "follow_up": "needs follow-up on an existing interaction"
    }
  }
}
```

The selected value must be checked against the registered agent IDs and the
user's authorization before dispatch. A low-probability or conflicting result
should go to the general agent or human review rather than silently choosing
an agent.

### Tool selection

Tool selection is appropriate only for a bounded registry, for example
`search_company`, `get_lead`, `update_lead`, `draft_email`, and
`schedule_meeting`. The classifier may rank permitted tools, but it must not
invent tool names or arguments. The existing tool registry remains the final
gate:

1. validate the selected tool against the allow-list;
2. validate arguments against its schema;
3. check tenant/user authorization;
4. apply the existing risk tier and approval policy;
5. execute through `registry.execute(...)`.

This removes repeated LLM calls whose only purpose is deciding which known
tool to invoke while preserving the existing approval and exactly-once
execution behavior.

### Escalation and LLM fallback

Use explicit policy rules and confidence thresholds to classify a request as:

| Outcome | Typical condition | Next step |
|---------|-------------------|-----------|
| `direct` | deterministic rule matched and required data is present | perform the safe handler |
| `specialist` | a known specialist intent was selected confidently | dispatch the bounded agent |
| `llm` | the request needs open-ended reasoning or generation | invoke the LLM |
| `human` | low confidence, policy conflict, or sensitive action | create an approval/review task |

Thresholds should be configured and measured on representative examples, not
chosen ad hoc per request. Record the classifier name/version, input feature
set, selected outcome, probabilities, threshold, and fallback reason in
telemetry. Never use a success-shaped default when Laya is unavailable:
surface the error and follow the configured fallback policy.

### Minimal adapter shape

```python
import os
from typing import Any

import requests


class LayaClassificationError(RuntimeError):
    pass


def classify(state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("LAYA_API_KEY")
    if not api_key:
        raise LayaClassificationError("LAYA_API_KEY is not configured")

    try:
        response = requests.post(
            "https://api.laya.studio/v1/systemone",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"state": state, "questions": questions},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise LayaClassificationError("Laya classification failed") from exc

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise LayaClassificationError("Laya returned an invalid answers payload")
    return answers
```

The production adapter should use the repository's HTTP client and settings
conventions, add response-schema validation, redact sensitive fields from
telemetry, and apply a bounded retry policy only where retries are safe.

---

## 16. Telemetry (OpenTelemetry)

`telemetry/otel.py`:
- `init_telemetry(provider=None, processor=None)` — a **module-local** `TracerProvider` (not the process-global one, which is set-once and breaks per-test in-memory exporters). Best-effort also calls `trace.set_tracer_provider` so `FastAPIInstrumentor` picks it up in production.
- `get_tracer(name)`, `reset_telemetry()`.
- **Exporter selection**: OTLP if `OTEL_EXPORTER_OTLP_ENDPOINT` set; console if `OTEL_CONSOLE_EXPORTER=true`; otherwise spans are created and dropped (no background thread — avoids the "I/O operation on closed file" shutdown error in tests).

**Instrumented spans** (manual):
| Span | Location | Key attributes |
|------|----------|----------------|
| `llm.chat` | `agent/llm.py` | `llm.provider`, `llm.model`, `llm.tools`, `llm.input_tokens`, `llm.output_tokens`, `llm.cost_usd`; ERROR on failure |
| `tool.execute` | `agent/tools/registry.py` | `tool.name`, `tool.risk`, `tool.success`; ERROR on unknown/failure |
| `run.transition` | `agent/run_lifecycle.py` | `run.id`, `run.from`, `run.to`; ERROR on invalid transition |
| HTTP requests | `main.py` | `FastAPIInstrumentor.instrument_app(app)` (production only) |

The frontend **TelemetryPage** fetches `/api/telemetry/` and renders spans (LLM calls, tool executions, run transitions) with token counts, costs, and status. The **UnifiedChatPage** shows an inline telemetry panel after each run.

---

## 17. Technical Q&A

**Q: How many agents are there?**
Four surfaces (Unified, Root, Runner, Builder) plus subagents. Only Unified runs the full LangGraph engine.

**Q: Is the graph bidirectional?**
No. It is a **directed** graph. The only cycle is `agent → tools → agent`, bounded by `MAX_ITERATIONS = 15`. There is no path from `tools` back to `START` or from `END` to anywhere.

**Q: How does the agent decide what to do?**
The LLM sees the system prompt + conversation history + all 15 tool schemas and returns either a text answer or native tool calls. The graph routes to the `tools` node iff tool calls exist.

**Q: How are SQL queries executed?**
The LLM cannot run SQL. It calls `query_crm` with a named, allow-listed operation and validated params; SQLAlchemy builds parameterized SQL. Unknown operations/params are rejected.

**Q: Can the agent execute code (bash/python)?**
No. `bash` and `execute_python` were removed in Phase 0. The only subprocess is sandboxed `grep` inside the workspace. This is intentional (security).

**Q: How does the agent write files?**
Via `write_file`, which is `approval_required` — the graph pauses for human approval, then writes inside `AGENT_WORKSPACE_ROOT` (path-traversal-protected).

**Q: How does web access work safely?**
`web_fetch` rejects non-http(s), localhost, private/loopback/link-local IPs, and re-checks DNS-resolved IPs (SSRF-safe).

**Q: How does human-in-the-loop work?**
`approval_required` tools call `interrupt(...)` in the `tools` node (Phase 1). The run becomes `WAITING_FOR_APPROVAL`, an `AgentApproval` row is created, and the frontend polls for approvals. On decide, the engine resumes with `Command(resume=...)` and Phase 2 executes the tool exactly once.

**Q: Why is the tools node two-phase?**
Because a node's state updates are discarded on interrupt. Gating all approvals *before* executing guarantees each tool runs exactly once across pause/resume.

**Q: How do subagents work?**
The `spawn_subagent` tool calls an engine-injected executor that creates a child `AgentRun` (with `parent_run_id`/`child_run_ids` linkage) and runs it via `start_run` at `depth+1`. Depth is capped at 3.

**Q: Where is state stored?**
In PostgreSQL via `AsyncPostgresSaver` — the same instance as the CRM data (deliberate constraint: no separate DB for LangGraph). The run's `graph_thread_id` is the checkpoint thread id.

**Q: How are runs made durable?**
The worker claims `agentTask` rows with `FOR UPDATE SKIP LOCKED`, leases them, and recovers stale leases. Combined with the checkpointer, a crashed worker's run resumes from its last checkpoint.

**Q: How is cost tracked?**
Every LLM call is logged to `LLMCallLog` with input/output tokens and cost. `AgentRun` also stores `input_tokens`, `output_tokens`, `cost_usd`. Spans carry `llm.input_tokens`/`llm.output_tokens`/`llm.cost_usd`.

**Q: How is authorization enforced?**
All agent endpoints require `get_current_user` (HS256 JWT or dev-mode explicit email). Approvals additionally require the approver to be the run initiator or an org owner/admin.

**Q: How is the LLM abstracted?**
`LLMService` normalizes Ollama and GroQ behind one `chat()` interface with native tool calling and automatic Ollama→GroQ fallback.

**Q: What happens on an error?**
A tool error becomes `{success:false, error:...}` (a tool must not kill the run). An LLM error sets `state.error`, which routes to `END` and the run settles to `FAILED`.

**Q: How does conversation continuity work?**
The frontend sends `task_id` (the thread id). The engine checks `graph.aget_state`; if state exists it continues the thread, otherwise it seeds a new one with the system prompt. `conversation_history` is also passed and seeded.

---

## 18. Future Scope

1. **Fan-out / map-reduce** — LangGraph `Send` to run a tool across many inputs in parallel (currently subagents are sequential spawn-and-wait).
2. **Streaming** — token-by-token SSE/WebSocket streaming instead of waiting for the full run.
3. **Subagent orchestration** — supervisor/hierarchical teams, parallel specialists with result aggregation.
4. **Richer telemetry UI** — per-run trace waterfall (span timing), cost attribution per agent/version, `GET /runs/{id}/children` admin endpoint.
5. **Approval policies** — batch approvals, argument-based policies, time-boxed auto-approval.
6. **Persistent memory** — long-term agent memory across runs (history is currently per-request).
7. **Eval harness** — replay recorded runs against the checkpointer for regression testing.
8. **Ops** — modernize `start_all.sh` (currently bare `python3` + sqlite3 seeding) to use the venv + PostgreSQL.

---

*One-sentence mental model:* The unified agent is a two-node LangGraph loop (LLM ⇄ tools) checkpointed to Postgres, where dangerous tools pause via `interrupt()` for human approval, and the agent can recursively spawn child runs as subagents — all wrapped in a durable, observable, state-machine-driven execution engine.
