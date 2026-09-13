from typing import Optional, Dict
from app.database.models import Deal, DealStage
from app.database.session import async_session_factory
from sqlalchemy import select, func
from app.crm.activity_stamp import stamp_stage_change

class DealsService:
    async def list(self, input: Dict) -> Dict:
        async with async_session_factory() as session:
            stmt = select(Deal)
            total_stmt = select(func.count(Deal.id))
            rows_result = await session.execute(stmt)
            total_result = await session.execute(total_stmt)
            rows = rows_result.scalars().all()
            total = total_result.scalar()
            return {"rows": [r for r in rows], "total": total, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Deal]:
        async with async_session_factory() as session:
            result = await session.execute(select(Deal).where(Deal.id == id))
            return result.scalar_one_or_none()

    async def create(self, data: dict) -> Deal:
        async with async_session_factory() as session:
            deal = Deal(**data)
            session.add(deal)
            await session.commit()
            await session.refresh(deal)
            return deal

    async def update(self, id: str, data: dict) -> Optional[Deal]:
        async with async_session_factory() as session:
            result = await session.execute(select(Deal).where(Deal.id == id))
            deal = result.scalar_one_or_none()
            if deal:
                for key, value in data.items():
                    setattr(deal, key, value)
                await session.commit()
                await session.refresh(deal)
            return deal

    async def set_stage(self, id: str, stage: str) -> Optional[Deal]:
        async with async_session_factory() as session:
            result = await session.execute(select(Deal).where(Deal.id == id))
            deal = result.scalar_one_or_none()
            if deal:
                deal.stage = stage
                await session.commit()
                await session.refresh(deal)
            return deal

    async def remove(self, id: str):
        async with async_session_factory() as session:
            result = await session.execute(select(Deal).where(Deal.id == id))
            deal = result.scalar_one_or_none()
            if deal:
                await session.delete(deal)
                await session.commit()

deals_service = DealsService()