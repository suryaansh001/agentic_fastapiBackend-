from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.settings.service import SettingsService

router = APIRouter()
service = SettingsService()

@router.get("/")
async def get_settings(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return await service.get()

@router.put("/")
async def update_settings(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.update(data)
