from typing import Optional, Dict
from app.database.models import Contact
from app.contacts.schemas import ContactCreate

class ContactsService:
    async def list(self, input: Dict) -> Dict:
        return {"rows": [], "total": 0, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Contact]:
        return None

    async def create(self, data: dict) -> Contact:
        return Contact(id="", **data)

    async def update(self, id: str, data: dict) -> Contact:
        return Contact(id=id, **data)

    async def remove(self, id: str):
        pass

contacts_service = ContactsService()
