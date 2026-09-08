from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.workspace.service import WorkspaceService
from app.workspace.schemas import WorkspaceUpdate, WorkspaceResponse

router = APIRouter()
service = WorkspaceService()

@router.get("/")
async def get_workspace(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get()

@router.put("/")
async def update_workspace(data: WorkspaceUpdate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.update(data.model_dump())

@router.get("/profile")
async def get_workspace_profile(current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_profile()
