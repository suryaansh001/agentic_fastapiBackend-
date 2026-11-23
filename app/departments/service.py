from sqlalchemy import select
from app.database.models import Department, DepartmentMember, User
from app.database.session import async_session_factory
from app.rbac import DEPARTMENTS


class DepartmentsService:
    async def ensure_defaults(self):
        async with async_session_factory() as session:
            for key, meta in DEPARTMENTS.items():
                existing = await session.scalar(select(Department).where(Department.key == key))
                if existing is None:
                    session.add(Department(key=key, name=meta["name"], description=meta["description"]))
            await session.commit()

    async def list(self):
        await self.ensure_defaults()
        async with async_session_factory() as session:
            result = await session.execute(select(Department).order_by(Department.name))
            return [
                {"id": row.id, "key": row.key, "name": row.name, "description": row.description}
                for row in result.scalars().all()
            ]

    async def members(self, department_key: str):
        await self.ensure_defaults()
        async with async_session_factory() as session:
            department = await session.scalar(select(Department).where(Department.key == department_key))
            if department is None:
                return []
            result = await session.execute(
                select(DepartmentMember, User)
                .join(User, User.id == DepartmentMember.user_id)
                .where(DepartmentMember.department_id == department.id)
            )
            return [
                {
                    "id": membership.id,
                    "user_id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": membership.role,
                    "job_title": membership.job_title,
                }
                for membership, user in result.all()
            ]


departments_service = DepartmentsService()
