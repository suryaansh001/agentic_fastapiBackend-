"""Laya classification adapter used by the agent execution graph.

Laya answers *typed* questions in a single forward pass. We use it to
route a request before spending any LLM tokens: one POST asks for the
execution mode, the specialized route, the CRM query operation and the
chart type. The engine then takes a deterministic fast-path where it
can, and only calls the LLM to summarize (or when Laya is unavailable /
unsure).
"""
from dataclasses import dataclass, field
import time
from typing import Any, Optional

import httpx

from app.agent.routing import (
    CHART_TYPES,
    MODES,
    QUERY_OPERATIONS,
    ROUTES,
)
from app.config.settings import settings
from app.telemetry.otel import get_tracer


class LayaClassificationError(RuntimeError):
    """Raised when Laya cannot return a valid classification."""


@dataclass
class ClassificationResult:
    choice: str
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    provider: str = "laya"
    mode: Optional[str] = None
    operation: Optional[str] = None
    chart_type: Optional[str] = None
    route: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LeadClassification:
    score: float
    status: str
    qualifies: float
    confidence: float
    provider: str = "laya"


_MODE_CRITERIA = {
    "answer": "Answer from general knowledge or reasoning, no data access needed",
    "crm_query": "Read CRM data (deals, contacts, companies, pipeline) and report it",
    "code": "Run code or compute/transform data (analysis, aggregation)",
    "action": "Write to the CRM or send something; needs human approval",
}

_OPERATION_CRITERIA = {
    "list_companies": "List companies",
    "list_leads": "List leads (companies that are leads/MQL/SQL) with lead status",
    "list_deals": "List deals, optionally filtered by stage/owner/company",
    "search_contacts": "Search contacts by name or text",
    "search_companies": "Search companies by name or text",
    "deal_pipeline": "Deals grouped by stage with counts and totals",
    "contact_timeline": "Activities for one contact",
    "company_contacts": "Contacts belonging to one company",
    "deal_summary": "Summary for one deal",
    "list_emails": "Recent email activities with subject and body, for analysis or scoring",
}

_CHART_CRITERIA = {
    "bar": "Bar chart",
    "line": "Line chart over time",
    "scatter": "Scatter plot",
    "pie": "Pie chart",
    "area": "Area chart",
    "donut": "Donut chart",
}


class LayaClassifier:
    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.LAYA_API_KEY
        self.endpoint = endpoint or settings.LAYA_API_URL
        self.timeout = timeout or settings.LAYA_TIMEOUT_SECONDS
        self._client = client or httpx.AsyncClient(timeout=self.timeout)
        self._own_client = client is None
        self._cooldown_until = 0.0
        self._last_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # -- transport -----------------------------------------------------

    async def _post_questions(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.enabled:
            raise LayaClassificationError("LAYA_API_KEY is not configured")
        if time.monotonic() < self._cooldown_until:
            raise LayaClassificationError(
                self._last_error or "Laya is temporarily unavailable"
            )

        tracer = get_tracer("laya")
        with tracer.start_as_current_span("laya.classify") as span:
            span.set_attribute("laya.endpoint", self.endpoint)
            span.set_attribute("laya.question_count", len(questions))
            try:
                response = await self._client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"state": state, "questions": questions},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                detail = ""
                try:
                    body = exc.response.json()
                    detail = (body.get("error") or {}).get("message") or ""
                except ValueError:
                    pass
                message = f"Laya classification failed: HTTP {status}"
                if detail:
                    message += f" ({detail})"
                if status in (401, 402, 403, 429):
                    self._cooldown_until = time.monotonic() + 300.0
                    self._last_error = message
                span.set_attribute("laya.success", False)
                span.set_attribute("laya.status_code", status)
                raise LayaClassificationError(message) from exc
            except (httpx.HTTPError, ValueError) as exc:
                span.set_attribute("laya.success", False)
                raise LayaClassificationError(
                    "Laya classification failed"
                ) from exc
            span.set_attribute("laya.success", True)

        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise LayaClassificationError(
                "Laya returned an invalid answers payload"
            )
        return answers

    @staticmethod
    def _choice_answer(name: str, answer: Any) -> tuple[str, dict, float]:
        if not isinstance(answer, dict):
            raise LayaClassificationError(
                f"Laya returned an invalid answer for {name}"
            )
        choice = answer.get("choice")
        probabilities = answer.get("probabilities", {})
        if not isinstance(choice, str) or not isinstance(probabilities, dict):
            raise LayaClassificationError(
                f"Laya returned an invalid choice for {name}"
            )
        normalized = {
            key: float(value)
            for key, value in probabilities.items()
            if isinstance(key, str) and isinstance(value, (int, float))
        }
        confidence = answer.get("answer_confidence")
        if not isinstance(confidence, (int, float)):
            confidence = normalized.get(choice, 0.0)
        return choice, normalized, float(confidence)

    # -- public API ----------------------------------------------------

    async def classify(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> dict[str, ClassificationResult]:
        """Back-compat: classify a set of *choice* questions."""
        answers = await self._post_questions(state, questions)
        results: dict[str, ClassificationResult] = {}
        for name, answer in answers.items():
            choice, normalized, confidence = self._choice_answer(name, answer)
            results[name] = ClassificationResult(
                choice=choice,
                probabilities=normalized,
                confidence=confidence,
            )
        return results

    async def classify_agent_route(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ClassificationResult:
        """Classify mode + route + operation + chart type in one call."""
        answers = await self._post_questions(
            state={"message": message, "context": context or {}},
            questions={
                "route": {
                    "type": "choice",
                    "instructions": (
                        "Which bounded path should handle this CRM request?"
                    ),
                    "criteria": {
                        "research": "company or contact research",
                        "qualification": "lead scoring or qualification",
                        "outreach": "drafting prospect communication",
                        "meeting": "meeting scheduling or preparation",
                        "follow_up": "following up on an existing interaction",
                        "visualization": "creating a chart, graph, or visualization",
                        "llm": "open-ended reasoning or generation",
                        "human": "sensitive, ambiguous, or policy-controlled request",
                    },
                },
                "mode": {
                    "type": "choice",
                    "instructions": (
                        "How should the request be executed?"
                    ),
                    "criteria": _MODE_CRITERIA,
                },
                "operation": {
                    "type": "choice",
                    "instructions": (
                        "If CRM data is needed, which query operation fits?"
                    ),
                    "criteria": _OPERATION_CRITERIA,
                },
                "chart_type": {
                    "type": "choice",
                    "instructions": (
                        "If a chart is requested, which chart type fits?"
                    ),
                    "criteria": _CHART_CRITERIA,
                },
            },
        )
        if "route" not in answers:
            raise LayaClassificationError("Laya did not return a route answer")
        route, probabilities, confidence = self._choice_answer(
            "route", answers["route"]
        )

        def _optional_choice(name: str, allowed: list[str]) -> Optional[str]:
            answer = answers.get(name)
            if not isinstance(answer, dict):
                return None
            value = answer.get("choice")
            return value if value in allowed else None

        return ClassificationResult(
            choice=route,
            probabilities=probabilities,
            confidence=confidence,
            route=route if route in ROUTES else None,
            mode=_optional_choice("mode", MODES),
            operation=_optional_choice("operation", QUERY_OPERATIONS),
            chart_type=_optional_choice("chart_type", CHART_TYPES),
            details={
                name: answers[name]
                for name in ("mode", "operation", "chart_type")
                if isinstance(answers.get(name), dict)
            },
        )

    async def classify_lead(
        self,
        state: dict[str, Any],
    ) -> LeadClassification:
        """Score and qualify a lead (score + status + qualifies)."""
        answers = await self._post_questions(
            state=state,
            questions={
                "score": {
                    "type": "score",
                    "instructions": "How strong a fit is this lead?",
                    "criteria": [
                        "No fit",
                        "Weak fit",
                        "Moderate fit",
                        "Strong fit",
                    ],
                },
                "status": {
                    "type": "choice",
                    "instructions": "What lead status fits best?",
                    "criteria": {
                        "new": "Untouched lead",
                        "qualified": "Good fit, ready to work",
                        "unqualified": "Poor fit, do not pursue",
                        "contacted": "Already in contact",
                    },
                },
                "qualifies": {
                    "type": "noul",
                    "instructions": "Does this lead qualify?",
                },
            },
        )
        score_answer = answers.get("score") or {}
        status_answer = answers.get("status") or {}
        qualifies_answer = answers.get("qualifies") or {}
        if not isinstance(score_answer, dict) or not isinstance(
            status_answer, dict
        ):
            raise LayaClassificationError("Laya returned an invalid lead answer")
        score = float(score_answer.get("score", 0.0) or 0.0)
        status = status_answer.get("choice") or "new"
        qualifies = float(qualifies_answer.get("noul", 0.0) or 0.0)
        confidence = status_answer.get("answer_confidence")
        if not isinstance(confidence, (int, float)):
            confidence = float(
                (status_answer.get("probabilities") or {}).get(status, 0.0)
                or 0.0
            )
        return LeadClassification(
            score=score,
            status=status,
            qualifies=qualifies,
            confidence=float(confidence),
        )

    async def aclose(self) -> None:
        if self._own_client:
            await self._client.aclose()


_classifier: Optional[LayaClassifier] = None


def get_laya_classifier() -> LayaClassifier:
    global _classifier
    if _classifier is None:
        _classifier = LayaClassifier()
    return _classifier
