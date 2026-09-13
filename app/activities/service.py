from typing import Optional, Dict
from app.database.models import Activity
from app.database.session import async_session_factory
from sqlalchemy import select, func

class ActivitiesService:
    async def list(self, input: Dict) -> Dict:
        async with async_session_factory() as session:
            stmt = select(Activity)
            total_stmt = select(func.count(Activity.id))
            rows_result = await session.execute(stmt)
            total_result = await session.execute(total_stmt)
            rows = rows_result.scalars().all()
            total = total_result.scalar()
            return {"rows": [r for r in rows], "total": total, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Activity]:
        async with async_session_factory() as session:
            result = await session.execute(select(Activity).where(Activity.id == id))
            return result.scalar_one_or_none()

    async def create(self, data: dict) -> Activity:
        async with async_session_factory() as session:
            activity = Activity(**data)
            session.add(activity)
            await session.commit()
            await session.refresh(activity)
            return activity

    async def update(self, id: str, data: dict) -> Optional[Activity]:
        async with async_session_factory() as session:
            result = await session.execute(select(Activity).where(Activity.id == id))
            activity = result.scalar_one_or_none()
            if activity:
                for key, value in data.items():
                    setattr(activity, key, value)
                await session.commit()
                await session.refresh(activity)
            return activity

    async def remove(self, id: str):
        async with async_session_factory() as session:
            result = await session.execute(select(Activity).where(Activity.id == id))
            activity = result.scalar_one_or_none()
            if activity:
                await session.delete(activity)
                await session.commit()

activities_service = ActivitiesService()