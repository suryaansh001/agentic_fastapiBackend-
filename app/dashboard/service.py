from datetime import datetime, timedelta
from sqlalchemy import func, select
from app.database.models import (
    Activity,
    ActivityType,
    Campaign,
    CampaignRecipient,
    Company,
    Contact,
    Deal,
    DealStage,
    DepartmentMember,
    Department,
    LifecycleStage,
    User,
)
from app.database.session import async_session_factory


def _iso(value):
    return value.isoformat() if value else None


async def _count(session, stmt):
    return int(await session.scalar(stmt) or 0)


async def _sum(session, stmt):
    return float(await session.scalar(stmt) or 0)


class DashboardService:
    async def get(self, department: str) -> dict:
        async with async_session_factory() as session:
            if department == "sales":
                return await self._sales(session)
            if department == "marketing":
                return await self._marketing(session)
            if department == "hr":
                return await self._hr(session)
            if department == "finance":
                return await self._finance(session)
            if department == "support":
                return await self._support(session)
            if department == "operations":
                return await self._operations(session)
            if department == "executive":
                return await self._executive(session)
            return {"department": department, "kpis": [], "charts": [], "tables": [], "alerts": []}

    async def _sales(self, session):
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        open_stages = [s for s in DealStage if s not in (DealStage.CLOSED_WON, DealStage.CLOSED_LOST)]
        pipeline_value = await _sum(session, select(func.sum(Deal.amount)).where(Deal.stage.in_(open_stages)))
        open_deals = await _count(session, select(func.count(Deal.id)).where(Deal.stage.in_(open_stages)))
        won = await _count(session, select(func.count(Deal.id)).where(Deal.stage == DealStage.CLOSED_WON))
        lost = await _count(session, select(func.count(Deal.id)).where(Deal.stage == DealStage.CLOSED_LOST))
        won_value = await _sum(session, select(func.sum(Deal.amount)).where(Deal.stage == DealStage.CLOSED_WON))
        leads = await _count(session, select(func.count(Company.id)).where(Company.lifecycle_stage.in_([LifecycleStage.LEAD, LifecycleStage.MARKETING_QUALIFIED_LEAD, LifecycleStage.SALES_QUALIFIED_LEAD])))
        activities = await _count(session, select(func.count(Activity.id)).where(Activity.occurred_at >= week_ago))
        stage_rows = (await session.execute(select(Deal.stage, func.count(Deal.id), func.sum(Deal.amount)).group_by(Deal.stage))).all()
        recent = (await session.execute(select(Deal).order_by(Deal.created_at.desc()).limit(5))).scalars().all()
        return {
            "department": "sales",
            "kpis": [
                {"label": "Pipeline value", "value": pipeline_value, "format": "currency", "sub": f"{open_deals} open deals"},
                {"label": "Won revenue", "value": won_value, "format": "currency", "sub": f"{won} won deals"},
                {"label": "Win rate", "value": round((won / (won + lost)) * 100, 1) if won + lost else 0, "format": "percent", "sub": f"{lost} lost"},
                {"label": "Active leads", "value": leads, "format": "number", "sub": "LEAD / MQL / SQL"},
                {"label": "Activities this week", "value": activities, "format": "number", "sub": "Calls, emails, tasks"},
            ],
            "charts": [
                {"title": "Pipeline by stage", "type": "bar", "data": [{"label": stage.value.replace("_", " ").title(), "value": float(amount or 0), "count": count} for stage, count, amount in stage_rows]},
            ],
            "tables": [
                {"title": "Recent deals", "columns": ["name", "stage", "amount"], "rows": [{"id": d.id, "name": d.name, "stage": d.stage.value if hasattr(d.stage, "value") else d.stage, "amount": d.amount} for d in recent]},
            ],
            "alerts": [{"kind": "info", "title": "Follow-up queue", "body": "Open the Leads page to review stale opportunities."}],
        }

    async def _marketing(self, session):
        now = datetime.utcnow()
        campaigns = (await session.execute(select(Campaign).order_by(Campaign.created_at.desc()).limit(50))).scalars().all()
        total_sent = await _count(session, select(func.count(CampaignRecipient.id)).where(CampaignRecipient.sent_at.is_not(None)))
        opened = await _count(session, select(func.count(CampaignRecipient.id)).where(CampaignRecipient.opened_at.is_not(None)))
        clicked = await _count(session, select(func.count(CampaignRecipient.id)).where(CampaignRecipient.clicked_at.is_not(None)))
        replied = await _count(session, select(func.count(CampaignRecipient.id)).where(CampaignRecipient.replied_at.is_not(None)))
        converted = await _count(session, select(func.count(CampaignRecipient.id)).where(CampaignRecipient.converted_at.is_not(None)))
        leads = await _count(session, select(func.count(Company.id)).where(Company.lifecycle_stage.in_([LifecycleStage.LEAD, LifecycleStage.MARKETING_QUALIFIED_LEAD])))
        return {
            "department": "marketing",
            "kpis": [
                {"label": "Campaigns", "value": len(campaigns), "format": "number", "sub": f"{sum(1 for c in campaigns if c.status == 'sent')} sent"},
                {"label": "Emails sent", "value": total_sent, "format": "number", "sub": "All campaigns"},
                {"label": "Open rate", "value": round(opened / total_sent * 100, 1) if total_sent else 0, "format": "percent", "sub": f"{opened} opens"},
                {"label": "Click rate", "value": round(clicked / total_sent * 100, 1) if total_sent else 0, "format": "percent", "sub": f"{clicked} clicks"},
                {"label": "Reply rate", "value": round(replied / total_sent * 100, 1) if total_sent else 0, "format": "percent", "sub": f"{converted} conversions"},
                {"label": "Marketing leads", "value": leads, "format": "number", "sub": "LEAD + MQL"},
            ],
            "charts": [
                {"title": "Campaign funnel", "type": "funnel", "data": [
                    {"label": "Sent", "value": total_sent},
                    {"label": "Opened", "value": opened},
                    {"label": "Clicked", "value": clicked},
                    {"label": "Replied", "value": replied},
                    {"label": "Converted", "value": converted},
                ]},
            ],
            "tables": [
                {"title": "Recent campaigns", "columns": ["name", "status", "type"], "rows": [{"id": c.id, "name": c.name, "status": c.status, "type": c.type} for c in campaigns[:6]]},
            ],
            "alerts": [{"kind": "info", "title": "Campaign engine", "body": "Create a campaign to start tracking opens, clicks and replies."}],
        }

    async def _hr(self, session):
        department = await session.scalar(select(Department).where(Department.key == "hr"))
        headcount = 0
        if department:
            headcount = await _count(session, select(func.count(DepartmentMember.id)).where(DepartmentMember.department_id == department.id))
        return {
            "department": "hr",
            "kpis": [
                {"label": "Headcount", "value": headcount, "format": "number", "sub": "HR department"},
                {"label": "Open roles", "value": 0, "format": "number", "sub": "Recruitment module next phase"},
                {"label": "Attendance today", "value": "—", "format": "text", "sub": "Phase 2"},
                {"label": "Pending leave", "value": 0, "format": "number", "sub": "Phase 2"},
            ],
            "charts": [],
            "tables": [],
            "alerts": [{"kind": "warning", "title": "HR module", "body": "Employee, attendance, leave and payroll simulation arrive in Phase 2."}],
        }

    async def _finance(self, session):
        revenue = await _sum(session, select(func.sum(Deal.amount)).where(Deal.stage == DealStage.CLOSED_WON))
        open_value = await _sum(session, select(func.sum(Deal.amount)).where(Deal.stage.notin_([DealStage.CLOSED_WON, DealStage.CLOSED_LOST])))
        return {
            "department": "finance",
            "kpis": [
                {"label": "Revenue", "value": revenue, "format": "currency", "sub": "Closed-won deals"},
                {"label": "Open pipeline", "value": open_value, "format": "currency", "sub": "Forecastable"},
                {"label": "Invoices", "value": 0, "format": "number", "sub": "Phase 3"},
                {"label": "Expenses", "value": 0, "format": "currency", "sub": "Phase 3"},
            ],
            "charts": [],
            "tables": [],
            "alerts": [{"kind": "warning", "title": "Finance module", "body": "Invoices, expenses and payments arrive in Phase 3."}],
        }

    async def _support(self, session):
        tasks = await _count(session, select(func.count(Activity.id)).where(Activity.type == ActivityType.TASK))
        return {
            "department": "support",
            "kpis": [
                {"label": "Open tickets", "value": 0, "format": "number", "sub": "Phase 3"},
                {"label": "SLA breaches", "value": 0, "format": "number", "sub": "Phase 3"},
                {"label": "Open tasks", "value": tasks, "format": "number", "sub": "From activity timeline"},
                {"label": "CSAT", "value": "—", "format": "text", "sub": "Phase 3"},
            ],
            "charts": [],
            "tables": [],
            "alerts": [{"kind": "warning", "title": "Support module", "body": "Tickets, SLA and AI triage arrive in Phase 3."}],
        }

    async def _operations(self, session):
        tasks = await _count(session, select(func.count(Activity.id)).where(Activity.type == ActivityType.TASK))
        meetings = await _count(session, select(func.count(Activity.id)).where(Activity.type == ActivityType.MEETING))
        return {
            "department": "operations",
            "kpis": [
                {"label": "Open tasks", "value": tasks, "format": "number", "sub": "Activity tasks"},
                {"label": "Meetings", "value": meetings, "format": "number", "sub": "Logged meetings"},
                {"label": "Assets", "value": 0, "format": "number", "sub": "Phase 3"},
                {"label": "Requests", "value": 0, "format": "number", "sub": "Phase 3"},
            ],
            "charts": [],
            "tables": [],
            "alerts": [{"kind": "warning", "title": "Operations module", "body": "Tasks, assets and requests arrive in Phase 3."}],
        }

    async def _executive(self, session):
        sales = await self._sales(session)
        marketing = await self._marketing(session)
        hr = await self._hr(session)
        finance = await self._finance(session)
        support = await self._support(session)
        operations = await self._operations(session)
        return {
            "department": "executive",
            "kpis": [
                {"label": "Revenue", "value": next((k["value"] for k in finance["kpis"] if k["label"] == "Revenue"), 0), "format": "currency", "sub": "Closed won"},
                {"label": "Pipeline", "value": next((k["value"] for k in sales["kpis"] if k["label"] == "Pipeline value"), 0), "format": "currency", "sub": "Open deals"},
                {"label": "Campaigns", "value": next((k["value"] for k in marketing["kpis"] if k["label"] == "Campaigns"), 0), "format": "number", "sub": "Marketing"},
                {"label": "Headcount", "value": next((k["value"] for k in hr["kpis"] if k["label"] == "Headcount"), 0), "format": "number", "sub": "HR"},
                {"label": "Open tasks", "value": next((k["value"] for k in operations["kpis"] if k["label"] == "Open tasks"), 0), "format": "number", "sub": "Operations"},
            ],
            "charts": sales["charts"] + marketing["charts"],
            "tables": sales["tables"] + marketing["tables"],
            "alerts": [
                {"kind": "info", "title": "Executive view", "body": "Cross-department metrics are live. HR, support and finance modules land in later phases."},
            ],
            "departments": {
                "sales": sales["kpis"],
                "marketing": marketing["kpis"],
                "hr": hr["kpis"],
                "finance": finance["kpis"],
                "support": support["kpis"],
                "operations": operations["kpis"],
            },
        }


dashboard_service = DashboardService()
