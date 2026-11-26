from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.operations.service import operations_service
router = APIRouter()
@router.get("/tasks")
async def list_tasks(current_user: CurrentUser = Depends(require_permission("crm.read"))): return {"items": await operations_service.tasks()}
@router.get("/assets")
async def list_assets(current_user: CurrentUser = Depends(require_permission("crm.read"))): return {"items": await operations_service.assets()}
@router.get("/requests")
async def list_requests(current_user: CurrentUser = Depends(require_permission("crm.read"))): return {"items": await operations_service.requests()}

@router.post("/assets")
async def create_asset(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await operations_service.create_asset(data)

@router.put("/assets/{id}/status")
async def update_asset_status(id: str, status: str, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await operations_service.update_asset_status(id, status)

@router.post("/requests")
async def create_request(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await operations_service.create_request(data)

@router.put("/requests/{id}/status")
async def update_request_status(id: str, status: str, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await operations_service.update_request_status(id, status)
