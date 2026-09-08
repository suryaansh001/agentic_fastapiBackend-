from typing import Optional, Dict
from app.database.models import WorkspaceProfile

class WorkspaceService:
    async def get(self) -> Optional[WorkspaceProfile]:
        return None

    async def update(self, data: dict) -> WorkspaceProfile:
        return WorkspaceProfile(id="", **data)

    async def get_profile(self) -> Optional[dict]:
        return None

workspace_service = WorkspaceService()
