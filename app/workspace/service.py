from sqlalchemy import select
from app.database.models import Organization
from app.database.session import async_session_factory


class WorkspaceService:
    async def get(self) -> dict:
        async with async_session_factory() as session:
            org = await session.scalar(select(Organization).limit(1))
            if org is None:
                return {"name": "Agentic CRM", "subdomain": "agentic-crm", "website": "", "allow_signup": True, "require_email_verification": False}
            meta = org.meta_data or {}
            return {
                "id": org.id,
                "name": org.name,
                "subdomain": org.slug,
                "website": org.website,
                "logo": org.logo,
                "allow_signup": meta.get("allow_signup", True),
                "require_email_verification": meta.get("require_email_verification", False),
            }

    async def update(self, data: dict) -> dict:
        async with async_session_factory() as session:
            org = await session.scalar(select(Organization).limit(1))
            if org is None:
                org = Organization(name=data.get("name") or "Agentic CRM", slug=data.get("subdomain") or "agentic-crm")
                session.add(org)
            org.name = data.get("name") or org.name
            org.slug = data.get("subdomain") or org.slug
            org.website = data.get("website") or org.website
            org.meta_data = {
                **(org.meta_data or {}),
                "allow_signup": bool(data.get("allow_signup", True)),
                "require_email_verification": bool(data.get("require_email_verification", False)),
            }
            await session.commit()
            return await self.get()


workspace_service = WorkspaceService()
