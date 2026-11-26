from datetime import datetime
from sqlalchemy import func, select
from app.database.models import Expense, Invoice
from app.database.session import async_session_factory

class FinanceService:
    async def invoices(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Invoice).order_by(Invoice.created_at.desc()).offset(skip).limit(limit))).scalars().all()
            return [{"id": r.id, "number": r.number, "company_id": r.company_id, "amount": r.amount, "currency": r.currency, "status": r.status, "due_date": r.due_date} for r in rows]
    async def create_invoice(self, data: dict):
        async with async_session_factory() as session:
            number = f"INV-{(await session.scalar(select(func.count(Invoice.id))) or 0) + 1:04d}"
            due_date = data.get("due_date")
            if isinstance(due_date, str) and due_date:
                due_date = datetime.fromisoformat(due_date)
            row = Invoice(company_id=data["company_id"], number=number, amount=float(data.get("amount", 0)), currency=data.get("currency", "USD"), status=data.get("status", "open"), due_date=due_date)
            session.add(row); await session.commit(); return {"id": row.id, "number": row.number, "amount": row.amount}
    async def expenses(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Expense).order_by(Expense.created_at.desc()).offset(skip).limit(limit))).scalars().all()
            return [{"id": r.id, "category": r.category, "amount": r.amount, "currency": r.currency, "date": r.date, "status": r.status} for r in rows]
    async def create_expense(self, data: dict):
        async with async_session_factory() as session:
            date_value = data.get("date")
            if isinstance(date_value, str) and date_value:
                date_value = datetime.fromisoformat(date_value)
            row = Expense(user_id=data.get("user_id"), category=data.get("category"), amount=float(data.get("amount", 0)), currency=data.get("currency", "USD"), status=data.get("status", "draft"), date=date_value or datetime.utcnow())
            session.add(row); await session.commit(); return {"id": row.id, "amount": row.amount}
finance_service = FinanceService()
