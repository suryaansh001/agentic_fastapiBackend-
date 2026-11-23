from typing import Optional
from sqlalchemy import select, func
from app.database.models import SavedView
from app.database.session import async_session_factory


class SavedViewsService:
    async def list(self, entity: str = "", user_id: str = "", skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            stmt = select(SavedView)
            if entity:
                stmt = stmt.where(SavedView.entity == entity)
            if user_id:
                stmt = stmt.where((SavedView.owner_id == user_id) | (SavedView.shared == True))  # noqa: E712
            result = await session.execute(stmt.order_by(SavedView.created_at.desc()).offset(skip).limit(limit))
            return result.scalars().all()

    async def get_by_id(self, id: str):
        async with async_session_factory() as session:
            return await session.get(SavedView, id)

    async def create(self, data: dict):
        async with async_session_factory() as session:
            view = SavedView(**data)
            session.add(view)
            await session.commit()
            await session.refresh(view)
            return view

    async def update(self, id: str, data: dict):
        async with async_session_factory() as session:
            view = await session.get(SavedView, id)
            if view:
                for key, value in data.items():
                    if value is not None:
                        setattr(view, key, value)
                await session.commit()
                await session.refresh(view)
            return view

    async def remove(self, id: str):
        async with async_session_factory() as session:
            view = await session.get(SavedView, id)
            if view:
                await session.delete(view)
                await session.commit()
            return {"deleted": True}


saved_views_service = SavedViewsService()
