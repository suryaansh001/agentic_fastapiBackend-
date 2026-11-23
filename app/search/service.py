from sqlalchemy import or_, select
from app.database.models import Activity, Company, Contact, Deal
from app.database.session import async_session_factory


class SearchService:
    async def search(self, q: str, limit: int = 10):
        q = (q or "").strip()
        if len(q) < 2:
            return {"query": q, "companies": [], "contacts": [], "deals": [], "activities": []}
        like = f"%{q}%"
        async with async_session_factory() as session:
            companies = (await session.execute(
                select(Company).where(or_(Company.name.ilike(like), Company.domain.ilike(like), Company.industry.ilike(like))).limit(limit)
            )).scalars().all()
            contacts = (await session.execute(
                select(Contact).where(or_(Contact.first_name.ilike(like), Contact.last_name.ilike(like), Contact.email.ilike(like), Contact.title.ilike(like))).limit(limit)
            )).scalars().all()
            deals = (await session.execute(
                select(Deal).where(or_(Deal.name.ilike(like), Deal.description.ilike(like))).limit(limit)
            )).scalars().all()
            activities = (await session.execute(
                select(Activity).where(or_(Activity.subject.ilike(like), Activity.body.ilike(like))).limit(limit)
            )).scalars().all()
            return {
                "query": q,
                "companies": companies,
                "contacts": contacts,
                "deals": deals,
                "activities": activities,
                "total": len(companies) + len(contacts) + len(deals) + len(activities),
            }


search_service = SearchService()
