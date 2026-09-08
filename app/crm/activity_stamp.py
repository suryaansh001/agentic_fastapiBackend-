from datetime import datetime
from typing import Optional
from sqlalchemy import func
from app.database.session import async_session_factory
from app.database.models import Activity, Company, Deal, Contact

class ActivityStampService:
    async def stamp_last_activity(self, company_id: Optional[str] = None, contact_id: Optional[str] = None, deal_id: Optional[str] = None):
        now = datetime.utcnow()
        if company_id:
            await self._update(Company, company_id, now)
        if contact_id:
            await self._update(Contact, contact_id, now)
        if deal_id:
            await self._update(Deal, deal_id, now)

    async def _update(self, model, id: str, now: datetime):
        pass

    async def recompute_after_delete(self, target_type: str, ids: list):
        pass

activity_stamp = ActivityStampService()
