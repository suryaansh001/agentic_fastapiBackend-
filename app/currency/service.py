from datetime import datetime
from sqlalchemy import select
from app.database.models import ExchangeRate
from app.database.session import async_session_factory


class CurrencyService:
    async def list(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            result = await session.execute(select(ExchangeRate).order_by(ExchangeRate.base_currency).offset(skip).limit(limit))
            rows = result.scalars().all()
            return [
                {
                    "id": row.id,
                    "code": row.base_currency,
                    "symbol": row.base_currency,
                    "name": row.base_currency,
                    "exchange_rate": row.rate,
                    "as_of": row.as_of,
                }
                for row in rows
            ]

    async def create(self, data: dict):
        async with async_session_factory() as session:
            row = ExchangeRate(
                base_currency=(data.get("code") or data.get("base_currency") or "USD").upper(),
                quote_currency=(data.get("quote_currency") or "USD").upper(),
                rate=float(data.get("exchange_rate") or data.get("rate") or 1),
                as_of=datetime.utcnow(),
                source="manual",
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {"id": row.id, "code": row.base_currency, "exchange_rate": row.rate}

    async def remove(self, id: str):
        async with async_session_factory() as session:
            row = await session.get(ExchangeRate, id)
            if row:
                await session.delete(row)
                await session.commit()
            return {"deleted": True}


currency_service = CurrencyService()
