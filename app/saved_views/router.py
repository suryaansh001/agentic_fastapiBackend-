from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser, require_permission
from app.saved_views.service import SavedViewsService
from app.saved_views.schemas import SavedViewCreate, SavedViewUpdate

router = APIRouter()
service = SavedViewsService()

@router.get("/")
async def list_views(entity: str = "", current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await service.list(entity=entity, user_id=current_user.id)}

@router.get("/{id}")
async def get_view(id: str, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return await service.get_by_id(id)

@router.post("/")
async def create_view(data: SavedViewCreate, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.create({**data.model_dump(), "owner_id": current_user.id})

@router.put("/{id}")
async def update_view(id: str, data: SavedViewUpdate, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.update(id, data.model_dump(exclude_unset=True))

@router.delete("/{id}")
async def delete_view(id: str, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.remove(id)
