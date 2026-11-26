from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.governance.service import governance_service
router = APIRouter()
@router.get("/audit")
async def list_audit(skip: int = 0, limit: int = 100, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await governance_service.audit(skip, limit)}
@router.put("/retention")
async def set_retention(data: dict, current_user: CurrentUser = Depends(require_permission("admin"))):
    return await governance_service.set_retention(data.get("days", 30))
@router.post("/users/{user_id}/departments/{department_key}/join")
async def join_department(user_id: str, department_key: str, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await governance_service.join_department(user_id, department_key)
@router.get("/snapshot")
async def executive_snapshot(current_user: CurrentUser = Depends(require_permission("dashboard.read"))):
    return await governance_service.executive_snapshot()
