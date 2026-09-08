from typing import Optional, Dict
from app.database.models import Deal, DealStage
from app.crm.activity_stamp import stamp_stage_change

class DealsService:
    async def list(self, input: Dict) -> Dict:
        return {"rows": [], "total": 0, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Deal]:
        return None

    async def create(self, data: dict) -> Deal:
        return Deal(id="", **data)

    async def update(self, id: str, data: dict) -> Deal:
        return Deal(id=id, **data)

    async def set_stage(self, id: str, stage: str) -> Deal:
        return Deal(id=id, stage=stage)

    async def remove(self, id: str):
        pass

deals_service = DealsService()
