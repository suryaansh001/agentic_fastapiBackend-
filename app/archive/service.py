from datetime import datetime
from sqlalchemy import select
from app.database.models import Company, Contact, Deal
from app.database.session import async_session_factory


MODELS = {"company": Company, "contact": Contact, "deal": Deal}


class ArchiveService:
    async def list(self, skip: int = 0, limit: int = 100):
        async with async_session_factory() as session:
            rows = []
            for entity, model in MODELS.items():
                result = await session.execute(
                    select(model).where(model.archived_at.is_not(None)).order_by(model.archived_at.desc()).offset(skip).limit(limit)
                )
                for record in result.scalars().all():
                    rows.append({
                        "id": record.id,
                        "entity_type": entity,
                        "name": getattr(record, "name", None) or f"{getattr(record, 'first_name', '')} {getattr(record, 'last_name', '')}".strip(),
                        "archived_at": record.archived_at,
                    })
            rows.sort(key=lambda r: r["archived_at"] or datetime.min, reverse=True)
            return rows

    async def restore(self, id: str, entity_type: str = ""):
        async with async_session_factory() as session:
            models = {entity_type: MODELS[entity_type]} if entity_type in MODELS else MODELS
            for entity, model in models.items():
                record = await session.get(model, id)
                if record is not None:
                    record.archived_at = None
                    await session.commit()
                    return {"restored": True, "entity_type": entity, "id": id}
            return {"restored": False, "id": id}


archive_service = ArchiveService()
