from sqlalchemy import select, func
from app.database.models import Member, Organization, User
from app.database.session import async_session_factory
from app.auth.service import AuthService


class UsersService:
    async def list(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            result = await session.execute(select(User).order_by(User.created_at.desc()).offset(skip).limit(limit))
            users = result.scalars().all()
            rows = []
            for user in users:
                member = await session.scalar(select(Member).where(Member.user_id == user.id).limit(1))
                rows.append({
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": member.role if member else "member",
                    "email_verified": user.email_verified,
                    "created_at": user.created_at,
                })
            return rows

    async def get(self, id: str):
        async with async_session_factory() as session:
            user = await session.get(User, id)
            if not user:
                return None
            member = await session.scalar(select(Member).where(Member.user_id == user.id).limit(1))
            return {"id": user.id, "name": user.name, "email": user.email, "role": member.role if member else "member"}

    async def create(self, data: dict):
        async with async_session_factory() as session:
            existing = await session.scalar(select(User).where(User.email.ilike(data["email"])))
            if existing:
                raise ValueError("User already exists")
            user = User(
                name=data.get("name") or data["email"].split("@")[0],
                email=data["email"].lower(),
                password_hash=AuthService.hash_password(data.get("password") or "password123"),
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            organization = await session.scalar(select(Organization).limit(1))
            if organization is None:
                organization = Organization(name="Agentic CRM", slug="agentic-crm")
                session.add(organization)
                await session.flush()
            session.add(Member(organization_id=organization.id, user_id=user.id, role=data.get("role") or "member"))
            await session.commit()
            return {"id": user.id, "name": user.name, "email": user.email, "role": data.get("role") or "member"}

    async def update(self, id: str, data: dict):
        async with async_session_factory() as session:
            user = await session.get(User, id)
            if not user:
                return None
            if data.get("name"):
                user.name = data["name"]
            if data.get("email"):
                user.email = data["email"].lower()
            if data.get("password"):
                user.password_hash = AuthService.hash_password(data["password"])
            if data.get("role"):
                member = await session.scalar(select(Member).where(Member.user_id == id).limit(1))
                if member:
                    member.role = data["role"]
            await session.commit()
            return await self.get(id)

    async def remove(self, id: str):
        async with async_session_factory() as session:
            user = await session.get(User, id)
            if user:
                members = (await session.execute(select(Member).where(Member.user_id == id))).scalars().all()
                for member in members:
                    await session.delete(member)
                await session.delete(user)
                await session.commit()
            return {"deleted": True}


users_service = UsersService()
