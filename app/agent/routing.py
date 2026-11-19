"""Routing constants shared by the Laya classifier and the engine.

The Laya classifier returns one of :data:`ROUTES` for each request.
Every route maps to a specialized ``AgentDefinition`` (seeded by
``scripts/db_seed.py``) and a bounded subset of tools, so a
specialized agent can only reach the tools relevant to its task.

``MODES`` describe *how* a request should be executed: a plain LLM
answer, a deterministic CRM query, generated code, or a write action
that needs human approval.
"""
from typing import Optional
import re

# Execution modes decided by Laya.
MODE_ANSWER = "answer"
MODE_CODE = "code"
MODE_QUERY = "crm_query"
MODE_ACTION = "action"
MODES = [MODE_ANSWER, MODE_CODE, MODE_QUERY, MODE_ACTION]

# Specialized routes decided by Laya.
ROUTE_RESEARCH = "research"
ROUTE_QUALIFICATION = "qualification"
ROUTE_OUTREACH = "outreach"
ROUTE_MEETING = "meeting"
ROUTE_FOLLOW_UP = "follow_up"
ROUTE_VISUALIZATION = "visualization"
ROUTE_LLM = "llm"
ROUTE_HUMAN = "human"
ROUTES = [
    ROUTE_RESEARCH,
    ROUTE_QUALIFICATION,
    ROUTE_OUTREACH,
    ROUTE_MEETING,
    ROUTE_FOLLOW_UP,
    ROUTE_VISUALIZATION,
    ROUTE_LLM,
    ROUTE_HUMAN,
]

# Allow-listed read-only CRM query operations.
QUERY_OPERATIONS = [
    "list_companies",
    "list_leads",
    "list_deals",
    "search_contacts",
    "search_companies",
    "deal_pipeline",
    "contact_timeline",
    "company_contacts",
    "deal_summary",
    "list_emails",
]

# Chart types the create_chart tool supports.
CHART_TYPES = ["bar", "line", "scatter", "pie", "area", "donut"]

# Routes handled inline by the unified agent (no delegation).
INLINE_ROUTES = {ROUTE_LLM, ROUTE_HUMAN}


def agent_id_for_route(route: str) -> str:
    """Return the seeded ``AgentDefinition.id`` for ``route``."""
    return f"route-{route}"


# Tools each specialized agent may call. ``None`` means the full
# registry (used by the inline unified routes).
ROUTE_TOOLS: dict[str, Optional[list[str]]] = {
    ROUTE_RESEARCH: [
        "web_search",
        "web_fetch",
        "query_crm",
        "read_crm_record",
        "ask_question",
    ],
    ROUTE_QUALIFICATION: [
        "query_crm",
        "read_crm_record",
        "create_crm_activity",
        "ask_question",
    ],
    ROUTE_OUTREACH: [
        "query_crm",
        "read_crm_record",
        "post_slack_message",
        "ask_question",
    ],
    ROUTE_MEETING: [
        "query_crm",
        "read_crm_record",
        "create_crm_activity",
        "ask_question",
    ],
    ROUTE_FOLLOW_UP: [
        "query_crm",
        "read_crm_record",
        "create_crm_activity",
        "ask_question",
    ],
    ROUTE_VISUALIZATION: [
        "query_crm",
        "create_chart",
        "execute_python",
        "ask_question",
    ],
    ROUTE_LLM: None,
    ROUTE_HUMAN: None,
}

# System-prompt addendum injected for each specialized agent.
ROUTE_INSTRUCTIONS: dict[str, str] = {
    ROUTE_RESEARCH: (
        "You are the research agent. Gather company and contact facts "
        "from the CRM and the web, then summarize concisely."
    ),
    ROUTE_QUALIFICATION: (
        "You are the qualification agent. Score and qualify leads "
        "using CRM data; state the score and the reasons."
    ),
    ROUTE_OUTREACH: (
        "You are the outreach agent. Draft prospect communication "
        "grounded in CRM facts; never invent details."
    ),
    ROUTE_MEETING: (
        "You are the meeting agent. Prepare agendas and log meeting "
        "outcomes using CRM data."
    ),
    ROUTE_FOLLOW_UP: (
        "You are the follow-up agent. Track outstanding interactions "
        "and propose the next step."
    ),
    ROUTE_VISUALIZATION: (
        "You are the visualization agent. Fetch CRM data, then build "
        "the requested chart. Prefer create_chart with a query."
    ),
    ROUTE_LLM: (
        "Answer the user directly, using tools only when CRM data is "
        "required."
    ),
    ROUTE_HUMAN: (
        "This request is sensitive or ambiguous. Ask for clarification "
        "before taking any action."
    ),
}


_WEB_RE = re.compile(
    r"\b(from|on)\s+(the\s+)?(web|internet)\b"
    r"|\bsearch\s+(the\s+)?(web|internet|online)\b"
    r"|\bweb\s+search\b|\bgoogle\b|\bscrape\b|\bonline\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\bemails?\b|\binbox\b", re.IGNORECASE)
_SCORE_RE = re.compile(
    r"\bscor(e|es|ed|ing)\b|\bconversion\b|\bconvert\b"
    r"|\bprioriti[sz](e|ed|ation)\b",
    re.IGNORECASE,
)
_LEAD_RE = re.compile(
    r"\bleads?\b|\bcompan(y|ies)\b|\baccounts?\b", re.IGNORECASE
)


def _web_query(message: str) -> str:
    """Turn a fetch instruction into a cleaner search query."""
    query = re.sub(
        r"\b(fetch|get|find|search|look up|pull|gather|scrape)\b",
        " ",
        message,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\b(from|on)\s+(the\s+)?(web|internet|online)\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\b(and|then)?\s*(provide|give|show|return|score|analyse|analyze).*$",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s+", " ", query).strip(" .,")
    return query if len(query.split()) >= 3 else message.strip()


def classify_intent(message: str) -> Optional[dict]:
    """Deterministic pre-router for explicit, high-value intents.

    Returns ``None`` when the message is not a clear-cut request, so the
    caller can fall through to Laya. These rules guarantee that explicit
    web-fetch and email-analysis prompts execute the right tool even
    when the classifier or the LLM is unavailable.
    """
    text = message or ""
    if _WEB_RE.search(text):
        return {
            "intent": "web_search",
            "choice": ROUTE_RESEARCH,
            "route": ROUTE_RESEARCH,
            "mode": "research",
            "confidence": 1.0,
            "provider": "rules",
            "fast_path": "web_search",
            "query": _web_query(text),
        }
    if _EMAIL_RE.search(text) and _SCORE_RE.search(text):
        return {
            "intent": "email_analysis",
            "choice": ROUTE_QUALIFICATION,
            "route": ROUTE_QUALIFICATION,
            "mode": MODE_QUERY,
            "operation": "list_emails",
            "confidence": 1.0,
            "provider": "rules",
            "fast_path": "email_analysis",
        }
    if _SCORE_RE.search(text) and _LEAD_RE.search(text):
        return {
            "intent": "lead_scoring",
            "choice": ROUTE_QUALIFICATION,
            "route": ROUTE_QUALIFICATION,
            "mode": MODE_QUERY,
            "operation": "list_leads",
            "confidence": 1.0,
            "provider": "rules",
            "fast_path": "lead_scoring",
        }
    return None
