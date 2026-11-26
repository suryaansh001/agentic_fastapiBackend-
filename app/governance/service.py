from datetime import datetime
from sqlalchemy import select
from app.database.models import AuditLog, Department, DepartmentMember, User
from app.database.session import async_session_factory

class GovernanceService:
    async def audit(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            rows = (await session.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))).scalars().all()
            return [{"id": r.id, "actor_id": r.actor_id, "action": r.action, "entity_type": r.entity_type,
                     "entity_id": r.entity_id, "department": r.department, "created_at": r.created_at} for r in rows]

    async def set_retention(self, days: int):
        return {"retention_days": max(1, int(days))}

    async def join_department(self, user_id: str, department_key: str):
        async with async_session_factory() as session:
            department = await session.scalar(select(Department).where(Department.key == department_key))
            if not department:
                return {"ok": False, "error": "Department not found"}
            existing = await session.scalar(select(DepartmentMember).where(
                DepartmentMember.user_id == user_id, DepartmentMember.department_id == department.id).limit(1))
            if existing:
                return {"ok": True, "already": True}
            session.add(DepartmentMember(department_id=department.id, user_id=user_id, role="member", job_title="Member"))
            await session.commit()
            return {"ok": True, "joined": department_key}

    async def executive_snapshot(self):
        from app.dashboard.service import dashboard_service
        dashboard = await dashboard_service.get("executive")
        return dashboard
governance_service = GovernanceService()
