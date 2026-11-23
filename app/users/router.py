from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission, require_role
from app.users.service import UsersService

router = APIRouter()
service = UsersService()

@router.get("/")
async def list_users(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await service.list()}

@router.get("/{id}")
async def get_user(id: str, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return await service.get(id)

@router.post("/")
async def create_user(data: dict, current_user: CurrentUser = Depends(require_role("owner", "admin", "manager"))):
    try:
        return await service.create(data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.put("/{id}")
async def update_user(id: str, data: dict, current_user: CurrentUser = Depends(require_role("owner", "admin", "manager"))):
    return await service.update(id, data)

@router.delete("/{id}")
async def delete_user(id: str, current_user: CurrentUser = Depends(require_role("owner", "admin"))):
    return await service.remove(id)
