from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.support.service import support_service
router = APIRouter()
@router.get("/")
async def list_support(skip: int = 0, limit: int = 100, status: str = "", current_user: CurrentUser = Depends(require_permission("crm.read"))): return {"items": await support_service.list(skip, limit, status)}
@router.post("/")
async def create_support(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await support_service.create(data)
@router.put("/{id}/status")
async def update_support(id: str, status: str, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await support_service.update_status(id, status)
