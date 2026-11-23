from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.api_keys.service import ApiKeysService

router = APIRouter()
service = ApiKeysService()

@router.get("/")
async def list_keys(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await service.list(current_user.id)}

@router.post("/")
async def create_key(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.create(data, current_user.id)

@router.delete("/{id}")
async def delete_key(id: str, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.remove(id)
