from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.dashboard.service import DashboardService
from app.rbac import accessible_departments

router = APIRouter()
service = DashboardService()

@router.get("/{department}")
async def get_dashboard(department: str, current_user: CurrentUser = Depends(require_permission("dashboard.read"))):
    allowed = {d["key"] for d in accessible_departments(current_user)}
    if current_user.role not in {"admin", "executive"} and department not in allowed:
        raise HTTPException(status_code=403, detail="Department access denied")
    return await service.get(department)

@router.get("/")
async def list_dashboards(current_user: CurrentUser = Depends(require_permission("dashboard.read"))):
    return {"items": accessible_departments(current_user)}
