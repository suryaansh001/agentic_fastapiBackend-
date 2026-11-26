from datetime import datetime, timedelta
from sqlalchemy import func, select
from app.database.models import (
    Activity,
    ActivityType,
    Asset,
    Attendance,
    Campaign,
    CampaignRecipient,
    Company,
    Contact,
    Deal,
    DealStage,
    Department,
    DepartmentMember,
    Expense,
    Invoice,
    LeaveRequest,
    LifecycleStage,
    SupportTicket,
    User,
    WorkRequest,
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
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        department = await session.scalar(select(Department).where(Department.key == "hr"))
        headcount = 0
        if department:
            headcount = await _count(session, select(func.count(func.distinct(DepartmentMember.user_id))).where(DepartmentMember.department_id == department.id))
        present_today = await _count(session, select(func.count(Attendance.id)).where(Attendance.date >= today, Attendance.status == "present"))
        pending_leave = await _count(session, select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "requested"))
        on_leave = await _count(session, select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "approved", LeaveRequest.start_date <= datetime.utcnow(), LeaveRequest.end_date >= datetime.utcnow()))
        attendance_rows = (await session.execute(select(Attendance.status, func.count(Attendance.id)).where(Attendance.date >= today - timedelta(days=7)).group_by(Attendance.status))).all()
        leave_rows = (await session.execute(select(LeaveRequest.type, func.count(LeaveRequest.id)).group_by(LeaveRequest.type))).all()
        recent_leave = (await session.execute(select(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(6))).scalars().all()
        recent_attendance = (await session.execute(select(Attendance).order_by(Attendance.date.desc()).limit(6))).scalars().all()
        alerts = []
        if pending_leave:
            alerts.append({"kind": "warning", "title": "Leave approvals", "body": f"{pending_leave} leave request(s) waiting for review."})
        return {
            "department": "hr",
            "kpis": [
                {"label": "Headcount", "value": headcount, "format": "number", "sub": "HR department"},
                {"label": "Present today", "value": present_today, "format": "number", "sub": "Attendance records"},
                {"label": "Pending leave", "value": pending_leave, "format": "number", "sub": "Awaiting approval"},
                {"label": "On leave", "value": on_leave, "format": "number", "sub": "Approved today"},
                {"label": "Attendance rate", "value": round((present_today / headcount) * 100, 1) if headcount else 0, "format": "percent", "sub": "Today"},
            ],
            "charts": [
                {"title": "Attendance (7 days)", "type": "bar", "data": [{"label": status.title(), "value": count} for status, count in attendance_rows]},
                {"title": "Leave by type", "type": "bar", "data": [{"label": type_.title(), "value": count} for type_, count in leave_rows]},
            ],
            "tables": [
                {"title": "Recent leave requests", "columns": ["type", "start_date", "end_date", "status"], "rows": [{"id": r.id, "type": r.type, "start_date": _iso(r.start_date), "end_date": _iso(r.end_date), "status": r.status} for r in recent_leave]},
                {"title": "Recent attendance", "columns": ["date", "hours", "status"], "rows": [{"id": r.id, "date": _iso(r.date), "hours": r.hours, "status": r.status} for r in recent_attendance]},
            ],
            "alerts": alerts or [{"kind": "info", "title": "HR module", "body": "Employee records, attendance, leave and payroll simulation are live."}],
        }

    async def _finance(self, session):
        invoice_total = await _sum(session, select(func.sum(Invoice.amount)))
        invoice_count = await _count(session, select(func.count(Invoice.id)))
        open_invoices = await _count(session, select(func.count(Invoice.id)).where(Invoice.status == "open"))
        expense_total = await _sum(session, select(func.sum(Expense.amount)))
        expense_count = await _count(session, select(func.count(Expense.id)))
        invoice_rows = (await session.execute(select(Invoice.status, func.count(Invoice.id), func.sum(Invoice.amount)).group_by(Invoice.status))).all()
        expense_rows = (await session.execute(select(Expense.category, func.count(Expense.id), func.sum(Expense.amount)).group_by(Expense.category))).all()
        recent_invoices = (await session.execute(select(Invoice).order_by(Invoice.created_at.desc()).limit(6))).scalars().all()
        recent_expenses = (await session.execute(select(Expense).order_by(Expense.created_at.desc()).limit(6))).scalars().all()
        return {
            "department": "finance",
            "kpis": [
                {"label": "Invoiced", "value": invoice_total, "format": "currency", "sub": f"{invoice_count} invoices"},
                {"label": "Open invoices", "value": open_invoices, "format": "number", "sub": "Awaiting payment"},
                {"label": "Expenses", "value": expense_total, "format": "currency", "sub": f"{expense_count} entries"},
                {"label": "Net", "value": invoice_total - expense_total, "format": "currency", "sub": "Invoiced minus expenses"},
            ],
            "charts": [
                {"title": "Invoices by status", "type": "bar", "data": [{"label": status.title(), "value": float(amount or 0), "count": count} for status, count, amount in invoice_rows]},
                {"title": "Expenses by category", "type": "bar", "data": [{"label": (category or "Uncategorized").title(), "value": float(amount or 0), "count": count} for category, count, amount in expense_rows]},
            ],
            "tables": [
                {"title": "Recent invoices", "columns": ["number", "amount", "status"], "rows": [{"id": r.id, "number": r.number, "amount": r.amount, "status": r.status} for r in recent_invoices]},
                {"title": "Recent expenses", "columns": ["category", "amount", "status"], "rows": [{"id": r.id, "category": r.category, "amount": r.amount, "status": r.status} for r in recent_expenses]},
            ],
            "alerts": [{"kind": "info", "title": "Finance module", "body": "Invoices and expenses are live. Create entries from the Finance page."}],
        }

    async def _support(self, session):
        total = await _count(session, select(func.count(SupportTicket.id)))
        open_tickets = await _count(session, select(func.count(SupportTicket.id)).where(SupportTicket.status == "open"))
        high_priority = await _count(session, select(func.count(SupportTicket.id)).where(SupportTicket.priority.in_(["high", "urgent"]), SupportTicket.status != "closed"))
        resolved = await _count(session, select(func.count(SupportTicket.id)).where(SupportTicket.status.in_(["resolved", "closed"])))
        status_rows = (await session.execute(select(SupportTicket.status, func.count(SupportTicket.id)).group_by(SupportTicket.status))).all()
        priority_rows = (await session.execute(select(SupportTicket.priority, func.count(SupportTicket.id)).group_by(SupportTicket.priority))).all()
        recent = (await session.execute(select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(6))).scalars().all()
        return {
            "department": "support",
            "kpis": [
                {"label": "Open tickets", "value": open_tickets, "format": "number", "sub": f"{total} total"},
                {"label": "High priority", "value": high_priority, "format": "number", "sub": "Needs attention"},
                {"label": "Resolved", "value": resolved, "format": "number", "sub": "Resolved or closed"},
                {"label": "Resolution rate", "value": round((resolved / total) * 100, 1) if total else 0, "format": "percent", "sub": "Of all tickets"},
            ],
            "charts": [
                {"title": "Tickets by status", "type": "bar", "data": [{"label": status.title(), "value": count} for status, count in status_rows]},
                {"title": "Tickets by priority", "type": "bar", "data": [{"label": priority.title(), "value": count} for priority, count in priority_rows]},
            ],
            "tables": [
                {"title": "Recent tickets", "columns": ["subject", "status", "priority"], "rows": [{"id": r.id, "subject": r.subject, "status": r.status, "priority": r.priority} for r in recent]},
            ],
            "alerts": [{"kind": "warning", "title": "Support queue", "body": f"{high_priority} high-priority ticket(s) still open."}] if high_priority else [{"kind": "info", "title": "Support desk", "body": "No high-priority tickets waiting."}],
        }

    async def _operations(self, session):
        tasks = await _count(session, select(func.count(Activity.id)).where(Activity.type == ActivityType.TASK))
        assets = await _count(session, select(func.count(Asset.id)))
        active_assets = await _count(session, select(func.count(Asset.id)).where(Asset.status == "active"))
        requests = await _count(session, select(func.count(WorkRequest.id)))
        open_requests = await _count(session, select(func.count(WorkRequest.id)).where(WorkRequest.status == "open"))
        asset_rows = (await session.execute(select(Asset.status, func.count(Asset.id)).group_by(Asset.status))).all()
        request_rows = (await session.execute(select(WorkRequest.status, func.count(WorkRequest.id)).group_by(WorkRequest.status))).all()
        recent_assets = (await session.execute(select(Asset).order_by(Asset.created_at.desc()).limit(6))).scalars().all()
        recent_requests = (await session.execute(select(WorkRequest).order_by(WorkRequest.created_at.desc()).limit(6))).scalars().all()
        return {
            "department": "operations",
            "kpis": [
                {"label": "Open tasks", "value": tasks, "format": "number", "sub": "Activity tasks"},
                {"label": "Assets", "value": assets, "format": "number", "sub": f"{active_assets} active"},
                {"label": "Open requests", "value": open_requests, "format": "number", "sub": f"{requests} total"},
                {"label": "Asset uptime", "value": round((active_assets / assets) * 100, 1) if assets else 0, "format": "percent", "sub": "Active assets"},
            ],
            "charts": [
                {"title": "Assets by status", "type": "bar", "data": [{"label": status.title(), "value": count} for status, count in asset_rows]},
                {"title": "Requests by status", "type": "bar", "data": [{"label": status.title(), "value": count} for status, count in request_rows]},
            ],
            "tables": [
                {"title": "Recent assets", "columns": ["name", "type", "status"], "rows": [{"id": r.id, "name": r.name, "type": r.type, "status": r.status} for r in recent_assets]},
                {"title": "Recent requests", "columns": ["title", "status"], "rows": [{"id": r.id, "title": r.title, "status": r.status} for r in recent_requests]},
            ],
            "alerts": [{"kind": "info", "title": "Operations module", "body": "Tasks, assets and requests are live."}],
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
                {"label": "Revenue", "value": next((k["value"] for k in finance["kpis"] if k["label"] == "Invoiced"), 0), "format": "currency", "sub": "Invoiced"},
                {"label": "Pipeline", "value": next((k["value"] for k in sales["kpis"] if k["label"] == "Pipeline value"), 0), "format": "currency", "sub": "Open deals"},
                {"label": "Headcount", "value": next((k["value"] for k in hr["kpis"] if k["label"] == "Headcount"), 0), "format": "number", "sub": "HR"},
                {"label": "Open tickets", "value": next((k["value"] for k in support["kpis"] if k["label"] == "Open tickets"), 0), "format": "number", "sub": "Support"},
                {"label": "Open requests", "value": next((k["value"] for k in operations["kpis"] if k["label"] == "Open requests"), 0), "format": "number", "sub": "Operations"},
            ],
            "charts": sales["charts"] + marketing["charts"] + support["charts"],
            "tables": sales["tables"] + marketing["tables"] + support["tables"] + operations["tables"],
            "alerts": [
                {"kind": "info", "title": "Executive view", "body": "Cross-department metrics are live across sales, marketing, HR, finance, support and operations."},
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
