from typing import Optional, Dict, List
from app.database.models import FieldDefinition

class FieldsService:
    async def list(self, entity: str, page: int = 1, page_size: int = 25) -> Dict:
        return {"rows": [], "total": 0}

    async def get_by_id(self, id: str) -> Optional[FieldDefinition]:
        return None

    async def create(self, data: dict) -> FieldDefinition:
        return FieldDefinition(id="", **data)

    async def update(self, id: str, data: dict) -> FieldDefinition:
        return FieldDefinition(id=id, **data)

    async def remove(self, id: str):
        pass

    def build_form_schema(self, entity: str) -> Dict:
        return {}

    def build_columns(self, entity: str) -> List:
        return []

fields_service = FieldsService()
