from typing import Optional, Dict, Any, List
from app.database.models import Company, Contact, Deal, Activity, FieldValue
from app.database.session import async_session_factory
from sqlalchemy import select, func, and_
from app.companies.domain import normalize_domain
from app.crm.activity_stamp import stamp_last_activity

class CompaniesService:
    async def list(self, input: Dict) -> Dict:
        async with async_session_factory() as session:
            stmt = select(Company)
            total_stmt = select(func.count(Company.id))
            rows_result = await session.execute(stmt)
            total_result = await session.execute(total_stmt)
            rows = rows_result.scalars().all()
            total = total_result.scalar()
            return {"rows": [r for r in rows], "total": total, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Company]:
        async with async_session_factory() as session:
            result = await session.execute(select(Company).where(Company.id == id))
            return result.scalar_one_or_none()

    async def create(self, data: dict) -> Company:
        async with async_session_factory() as session:
            company = Company(**data)
            session.add(company)
            await session.commit()
            await session.refresh(company)
            return company

    async def update(self, id: str, data: dict) -> Optional[Company]:
        async with async_session_factory() as session:
            result = await session.execute(select(Company).where(Company.id == id))
            company = result.scalar_one_or_none()
            if company:
                for key, value in data.items():
                    setattr(company, key, value)
                await session.commit()
                await session.refresh(company)
            return company

    async def remove(self, id: str):
        async with async_session_factory() as session:
            result = await session.execute(select(Company).where(Company.id == id))
            company = result.scalar_one_or_none()
            if company:
                await session.delete(company)
                await session.commit()

    async def get_by_domain(self, domain: str) -> Optional[Company]:
        async with async_session_factory() as session:
            result = await session.execute(select(Company).where(Company.domain == domain))
            return result.scalar_one_or_none()

companies_service = CompaniesService()