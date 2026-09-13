from typing import Optional, Dict
from app.database.models import Contact
from app.database.session import async_session_factory
from sqlalchemy import select, func

class ContactsService:
    async def list(self, input: Dict) -> Dict:
        async with async_session_factory() as session:
            stmt = select(Contact)
            total_stmt = select(func.count(Contact.id))
            rows_result = await session.execute(stmt)
            total_result = await session.execute(total_stmt)
            rows = rows_result.scalars().all()
            total = total_result.scalar()
            return {"rows": [r for r in rows], "total": total, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Contact]:
        async with async_session_factory() as session:
            result = await session.execute(select(Contact).where(Contact.id == id))
            return result.scalar_one_or_none()

    async def create(self, data: dict) -> Contact:
        async with async_session_factory() as session:
            contact = Contact(**data)
            session.add(contact)
            await session.commit()
            await session.refresh(contact)
            return contact

    async def update(self, id: str, data: dict) -> Optional[Contact]:
        async with async_session_factory() as session:
            result = await session.execute(select(Contact).where(Contact.id == id))
            contact = result.scalar_one_or_none()
            if contact:
                for key, value in data.items():
                    setattr(contact, key, value)
                await session.commit()
                await session.refresh(contact)
            return contact

    async def remove(self, id: str):
        async with async_session_factory() as session:
            result = await session.execute(select(Contact).where(Contact.id == id))
            contact = result.scalar_one_or_none()
            if contact:
                await session.delete(contact)
                await session.commit()

contacts_service = ContactsService()