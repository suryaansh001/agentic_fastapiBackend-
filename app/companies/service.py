from typing import Optional, Dict, Any
from app.database.models import Company
from app.database.session import async_session_factory
from sqlalchemy import select, func
from app.companies.domain import normalize_domain
from app.crm.activity_stamp import stamp_last_activity

class CompaniesService:
    async def list(self, input: Dict) -> Dict:
        return {"rows": [], "total": 0, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Company]:
        return None

    async def create(self, data: dict) -> Company:
        return Company(id="", **data)

    async def update(self, id: str, data: dict) -> Company:
        return Company(id=id, **data)

    async def remove(self, id: str):
        pass

    async def get_by_domain(self, domain: str) -> Optional[Company]:
        return None

companies_service = CompaniesService()
