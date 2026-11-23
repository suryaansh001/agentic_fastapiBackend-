from typing import Optional, Dict, List
from sqlalchemy import select, func
from app.database.models import FieldDefinition, FieldValue
from app.database.session import async_session_factory


class FieldsService:
    async def list(self, entity: str, page: int = 1, page_size: int = 25) -> Dict:
        async with async_session_factory() as session:
            stmt = select(FieldDefinition).where(FieldDefinition.archived_at.is_(None))
            if entity:
                stmt = stmt.where(FieldDefinition.entity == entity)
            total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
            result = await session.execute(
                stmt.order_by(FieldDefinition.position, FieldDefinition.created_at)
                .offset(max(0, page - 1) * page_size)
                .limit(page_size)
            )
            rows = result.scalars().all()
            return {"rows": rows, "total": total or 0}

    async def get_by_id(self, id: str) -> Optional[FieldDefinition]:
        async with async_session_factory() as session:
            return await session.get(FieldDefinition, id)

    async def create(self, data: dict) -> FieldDefinition:
        async with async_session_factory() as session:
            field = FieldDefinition(**data)
            session.add(field)
            await session.commit()
            await session.refresh(field)
            return field

    async def update(self, id: str, data: dict) -> Optional[FieldDefinition]:
        async with async_session_factory() as session:
            field = await session.get(FieldDefinition, id)
            if field:
                for key, value in data.items():
                    if value is not None:
                        setattr(field, key, value)
                await session.commit()
                await session.refresh(field)
            return field

    async def remove(self, id: str):
        async with async_session_factory() as session:
            field = await session.get(FieldDefinition, id)
            if field:
                field.archived_at = func.now()
                await session.commit()

    async def list_values(self, entity: str, record_id: str) -> List[dict]:
        async with async_session_factory() as session:
            column = {
                "company": FieldValue.company_id,
                "contact": FieldValue.contact_id,
                "deal": FieldValue.deal_id,
            }.get(entity)
            if column is None:
                return []
            result = await session.execute(
                select(FieldValue, FieldDefinition)
                .join(FieldDefinition, FieldDefinition.id == FieldValue.field_id)
                .where(column == record_id)
            )
            return [
                {
                    "field_id": field.id,
                    "key": definition.key,
                    "label": definition.label,
                    "type": definition.type,
                    "value": value.text or value.number or value.date or value.bool or value.option_id,
                }
                for value, definition in result.all()
            ]

    async def set_value(self, entity: str, record_id: str, field_id: str, value) -> dict:
        async with async_session_factory() as session:
            field = await session.get(FieldDefinition, field_id)
            if field is None:
                raise ValueError("Field not found")
            column = {
                "company": FieldValue.company_id,
                "contact": FieldValue.contact_id,
                "deal": FieldValue.deal_id,
            }.get(entity)
            if column is None:
                raise ValueError("Unsupported entity")
            result = await session.execute(select(FieldValue).where(FieldValue.field_id == field_id, column == record_id))
            row = result.scalar_one_or_none()
            if row is None:
                row = FieldValue(field_id=field_id, **{column.key: record_id})
                session.add(row)
            for attr in ("text", "number", "date", "bool"):
                setattr(row, attr, None)
            if field.type in ("number", "currency"):
                row.number = float(value) if value is not None else None
            elif field.type in ("date", "datetime"):
                from datetime import datetime
                row.date = datetime.fromisoformat(value) if isinstance(value, str) else value
            elif field.type in ("bool", "boolean"):
                row.bool = bool(value)
            else:
                row.text = str(value) if value is not None else None
            await session.commit()
            return {"field_id": field_id, "value": value}


fields_service = FieldsService()
