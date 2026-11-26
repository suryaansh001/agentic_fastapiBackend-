from sqlalchemy import select
from app.database.models import SupportTicket
from app.database.session import async_session_factory

class SupportService:
    async def list(self, skip: int = 0, limit: int = 100, status: str = ""):
        async with async_session_factory() as session:
            stmt = select(SupportTicket)
            if status:
                stmt = stmt.where(SupportTicket.status == status)
            rows = (await session.execute(stmt.order_by(SupportTicket.created_at.desc()).offset(skip).limit(limit))).scalars().all()
            return [{"id": r.id, "subject": r.subject, "status": r.status, "priority": r.priority,
                     "owner_id": r.owner_id, "contact_id": r.contact_id, "created_at": r.created_at} for r in rows]

    async def create(self, data: dict):
        async with async_session_factory() as session:
            row = SupportTicket(subject=data["subject"], description=data.get("description"),
                                contact_id=data.get("contact_id"), company_id=data.get("company_id"),
                                priority=data.get("priority", "medium"), status=data.get("status", "open"))
            session.add(row); await session.commit(); return {"id": row.id, "status": row.status}

    async def update_status(self, id: str, status: str):
        async with async_session_factory() as session:
            row = await session.get(SupportTicket, id)
            if row: row.status = status; await session.commit()
            return {"id": id, "status": status}
support_service = SupportService()
