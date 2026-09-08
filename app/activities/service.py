from typing import Optional, Dict
from app.database.models import Activity

class ActivitiesService:
    async def list(self, input: Dict) -> Dict:
        return {"rows": [], "total": 0, "facet_counts": {}}

    async def get_by_id(self, id: str) -> Optional[Activity]:
        return None

    async def create(self, data: dict) -> Activity:
        return Activity(id="", **data)

    async def update(self, id: str, data: dict) -> Activity:
        return Activity(id=id, **data)

    async def remove(self, id: str):
        pass

activities_service = ActivitiesService()
