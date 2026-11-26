from sqlalchemy import select
from app.database.models import Activity, Asset, WorkRequest
from app.database.session import async_session_factory

class OperationsService:
    async def tasks(self):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Activity).where(Activity.type == "TASK").order_by(Activity.occurred_at.desc()).limit(100))).scalars().all()
            return [{"id": r.id, "subject": r.subject, "occurred_at": r.occurred_at} for r in rows]
    async def assets(self):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Asset).order_by(Asset.created_at.desc()).limit(100))).scalars().all()
            return [{"id": r.id, "name": r.name, "type": r.type, "status": r.status} for r in rows]
    async def requests(self):
        async with async_session_factory() as session:
            rows = (await session.execute(select(WorkRequest).order_by(WorkRequest.created_at.desc()).limit(100))).scalars().all()
            return [{"id": r.id, "title": r.title, "status": r.status} for r in rows]

    async def create_asset(self, data: dict):
        async with async_session_factory() as session:
            row = Asset(name=data["name"], type=data.get("type"), status=data.get("status", "active"))
            session.add(row); await session.commit()
            return {"id": row.id, "name": row.name, "status": row.status}

    async def update_asset_status(self, id: str, status: str):
        async with async_session_factory() as session:
            row = await session.get(Asset, id)
            if row: row.status = status; await session.commit()
            return {"id": id, "status": status}

    async def create_request(self, data: dict):
        async with async_session_factory() as session:
            row = WorkRequest(title=data["title"], status=data.get("status", "open"))
            session.add(row); await session.commit()
            return {"id": row.id, "title": row.title, "status": row.status}

    async def update_request_status(self, id: str, status: str):
        async with async_session_factory() as session:
            row = await session.get(WorkRequest, id)
            if row: row.status = status; await session.commit()
            return {"id": id, "status": status}

operations_service = OperationsService()
