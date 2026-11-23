import json
from app.agent.llm import get_llm_service
from app.dashboard.service import dashboard_service


class AnalyticsService:
    async def overview(self, department: str) -> dict:
        return await dashboard_service.get(department)

    async def analyze(self, data: dict) -> dict:
        department = data.get("department") or "executive"
        question = data.get("question") or "Summarize performance, risks, and recommended next actions."
        dashboard = await dashboard_service.get(department)
        payload = {
            "department": department,
            "kpis": dashboard.get("kpis", []),
            "charts": dashboard.get("charts", []),
            "alerts": dashboard.get("alerts", []),
        }
        prompt = f"""You are a CRM data analyst. Use only the data below. Answer the user's question with concise, decision-ready insight.

Department: {department}
Question: {question}

Data:
{json.dumps(payload, default=str)[:12000]}

Return plain text with: 1) headline, 2) 3-5 bullet insights, 3) recommended actions."""
        llm = get_llm_service()
        response = await llm.chat(
            [
                {"role": "system", "content": "You are a careful business analyst. Do not invent metrics that are not present. If data is missing, say so."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=900,
            temperature=0.3,
        )
        content = (response.content or "").strip()
        if not content:
            content = self._fallback(department, dashboard)
        return {
            "department": department,
            "question": question,
            "analysis": content,
            "provider": response.provider,
            "error": response.error,
            "kpis": dashboard.get("kpis", []),
        }

    def _fallback(self, department: str, dashboard: dict) -> str:
        kpis = dashboard.get("kpis", [])
        lines = [f"{department.title()} snapshot"]
        for kpi in kpis[:6]:
            lines.append(f"- {kpi.get('label')}: {kpi.get('value')} ({kpi.get('sub', '')})")
        lines.append("Recommended action: review the highest-value KPI and assign an owner this week.")
        return "\n".join(lines)


analytics_service = AnalyticsService()
