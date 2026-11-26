from datetime import datetime
from sqlalchemy import func, select
from app.database.models import Attendance, Department, DepartmentMember, LeaveRequest, Member, User
from app.database.session import async_session_factory
from app.auth.service import AuthService


def _parse_dt(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


class HRService:
    async def list_employees(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            rows = (await session.execute(
                select(User).order_by(User.name).offset(skip).limit(limit)
            )).scalars().all()
            result = []
            for user in rows:
                member = await session.scalar(
                    select(Member).where(Member.user_id == user.id).limit(1)
                )
                dept_member = await session.scalar(
                    select(DepartmentMember).where(
                        DepartmentMember.user_id == user.id
                    ).limit(1)
                )
                department = await session.get(Department, dept_member.department_id) if dept_member else None
                result.append({
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": member.role if member else "member",
                    "department": department.name if department else None,
                    "department_key": department.key if department else None,
                    "department_role": dept_member.role if dept_member else None,
                    "title": dept_member.job_title if dept_member else "",
                })
            return result

    async def create_employee(self, data: dict):
        async with async_session_factory() as session:
            user = User(
                name=data.get("name") or data["email"].split("@")[0],
                email=data["email"].lower(),
                password_hash=AuthService.hash_password(data.get("password") or "password123"),
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            organization_id = await session.scalar(select(func.min(Member.organization_id)))
            if organization_id is None:
                from app.database.models import Organization
                organization = Organization(name="Agentic CRM", slug="agentic-crm")
                session.add(organization)
                await session.flush()
                organization_id = organization.id
            session.add(Member(organization_id=organization_id, user_id=user.id, role=data.get("role") or "member"))
            department_key = data.get("department_key") or data.get("department")
            if department_key:
                department = await session.scalar(select(Department).where(Department.key == department_key))
                if department:
                    session.add(DepartmentMember(
                        department_id=department.id,
                        user_id=user.id,
                        role=data.get("department_role") or "member",
                        job_title=data.get("title") or "",
                    ))
            await session.commit()
            return {"id": user.id, "name": user.name, "email": user.email, "role": data.get("role") or "member"}

    async def update_employee(self, id: str, data: dict):
        async with async_session_factory() as session:
            user = await session.get(User, id)
            if not user:
                return None
            if data.get("name"):
                user.name = data["name"]
            if data.get("password"):
                user.password_hash = AuthService.hash_password(data["password"])
            member = await session.scalar(select(Member).where(Member.user_id == id).limit(1))
            if member and data.get("role"):
                member.role = data["role"]
            dept_member = await session.scalar(select(DepartmentMember).where(DepartmentMember.user_id == id).limit(1))
            department_key = data.get("department_key") or data.get("department")
            if department_key:
                department = await session.scalar(select(Department).where(Department.key == department_key))
                if department:
                    if dept_member:
                        dept_member.department_id = department.id
                    else:
                        dept_member = DepartmentMember(department_id=department.id, user_id=id, role="member", job_title="")
                        session.add(dept_member)
            if dept_member and data.get("department_role"):
                dept_member.role = data["department_role"]
            if dept_member and "title" in data:
                dept_member.job_title = data["title"] or ""
            await session.commit()
            return {"id": user.id, "name": user.name, "email": user.email, "role": member.role if member else "member"}

    async def list_attendance(self, skip: int = 0, limit: int = 100, user_id: str = ""):
        async with async_session_factory() as session:
            stmt = select(Attendance)
            if user_id:
                stmt = stmt.where(Attendance.user_id == user_id)
            rows = (await session.execute(stmt.order_by(Attendance.date.desc()).offset(skip).limit(limit))).scalars().all()
            return [
                {"id": r.id, "user_id": r.user_id, "date": r.date, "hours": r.hours, "status": r.status}
                for r in rows
            ]

    async def upsert_attendance(self, data: dict):
        async with async_session_factory() as session:
            date_value = _parse_dt(data["date"])
            existing = await session.scalar(
                select(Attendance).where(
                    Attendance.user_id == data["user_id"],
                    Attendance.date == date_value,
                ).limit(1)
            )
            if existing:
                existing.hours = data.get("hours", existing.hours)
                existing.status = data.get("status", existing.status)
            else:
                session.add(Attendance(
                    user_id=data["user_id"],
                    date=date_value,
                    hours=float(data.get("hours", 8.0) or 8.0),
                    status=data.get("status", "present"),
                ))
            await session.commit()
            return {"ok": True}

    async def list_leave(self, skip: int = 0, limit: int = 100, user_id: str = ""):
        async with async_session_factory() as session:
            stmt = select(LeaveRequest)
            if user_id:
                stmt = stmt.where(LeaveRequest.user_id == user_id)
            rows = (await session.execute(stmt.order_by(LeaveRequest.start_date.desc()).offset(skip).limit(limit))).scalars().all()
            return [
                {"id": r.id, "user_id": r.user_id, "type": r.type, "start_date": r.start_date,
                 "end_date": r.end_date, "days": r.days, "status": r.status, "reason": r.reason}
                for r in rows
            ]

    async def create_leave(self, data: dict):
        async with async_session_factory() as session:
            start_date = _parse_dt(data["start_date"])
            end_date = _parse_dt(data.get("end_date")) or start_date
            row = LeaveRequest(
                user_id=data["user_id"],
                type=data.get("type", "vacation"),
                start_date=start_date,
                end_date=end_date,
                days=int(data.get("days", 1) or 1),
                reason=data.get("reason"),
            )
            session.add(row)
            await session.commit()
            return {"id": row.id, "status": row.status}

    async def update_leave_status(self, id: str, status: str):
        async with async_session_factory() as session:
            row = await session.get(LeaveRequest, id)
            if row:
                row.status = status
                await session.commit()
            return {"id": id, "status": status}

    async def simulate_payroll(self, data: dict):
        salary = float(data.get("base_salary", 0) or 0)
        tax_rate = float(data.get("tax_rate", 0.2) or 0.2)
        deductions = float(data.get("deductions", 0) or 0)
        days = float(data.get("worked_days", 22) or 22)
        daily_rate = salary / 22 if salary else 0
        gross = daily_rate * days
        tax = gross * tax_rate
        net = gross - tax - deductions
        return {
            "gross": round(gross, 2),
            "tax": round(tax, 2),
            "deductions": round(deductions, 2),
            "net": round(net, 2),
            "mode": "simulation",
        }


hr_service = HRService()
