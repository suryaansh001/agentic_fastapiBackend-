import hashlib
import secrets
from datetime import datetime
from sqlalchemy import select
from app.database.models import ApiKey
from app.database.session import async_session_factory


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class ApiKeysService:
    async def list(self, user_id: str = ""):
        async with async_session_factory() as session:
            stmt = select(ApiKey).where(ApiKey.revoked_at.is_(None))
            if user_id:
                stmt = stmt.where(ApiKey.user_id == user_id)
            result = await session.execute(stmt.order_by(ApiKey.created_at.desc()))
            return [
                {"id": row.id, "name": row.name, "prefix": row.prefix, "created_at": row.created_at, "last_used_at": row.last_used_at}
                for row in result.scalars().all()
            ]

    async def create(self, data: dict, user_id: str = ""):
        raw = f"sk-{secrets.token_urlsafe(24)}"
        async with async_session_factory() as session:
            row = ApiKey(
                name=data.get("name") or "API key",
                prefix=raw[:12],
                key_hash=_hash(raw),
                user_id=user_id or None,
                department=data.get("department"),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {"id": row.id, "name": row.name, "prefix": row.prefix, "key": raw, "raw_key": raw, "created_at": row.created_at}

    async def remove(self, id: str):
        async with async_session_factory() as session:
            row = await session.get(ApiKey, id)
            if row:
                row.revoked_at = datetime.utcnow()
                await session.commit()
            return {"deleted": True}


api_keys_service = ApiKeysService()
