from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.workspace.service import WorkspaceService

router = APIRouter()
service = WorkspaceService()

@router.get("/")
async def get_workspace(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return await service.get()

@router.put("/")
async def update_workspace(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.update(data)

@router.get("/profile")
async def get_profile(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"profile": await service.get()}
