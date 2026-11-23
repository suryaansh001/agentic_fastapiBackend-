from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.analytics.service import AnalyticsService
from app.rbac import accessible_departments

router = APIRouter()
service = AnalyticsService()

@router.get("/{department}")
async def overview(department: str, current_user: CurrentUser = Depends(require_permission("analytics.read"))):
    allowed = {d["key"] for d in accessible_departments(current_user)}
    if current_user.role not in {"admin", "executive"} and department not in allowed:
        raise HTTPException(status_code=403, detail="Department access denied")
    return await service.overview(department)

@router.post("/analyze")
async def analyze(data: dict, current_user: CurrentUser = Depends(require_permission("analytics.read"))):
    department = data.get("department") or "executive"
    allowed = {d["key"] for d in accessible_departments(current_user)}
    if current_user.role not in {"admin", "executive"} and department not in allowed:
        raise HTTPException(status_code=403, detail="Department access denied")
    return await service.analyze(data)
