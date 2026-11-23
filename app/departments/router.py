from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.departments.service import DepartmentsService
from app.rbac import accessible_departments

router = APIRouter()
service = DepartmentsService()

@router.get("/")
async def list_departments(current_user: CurrentUser = Depends(require_permission("dashboard.read"))):
    rows = await service.list()
    allowed = {d["key"] for d in accessible_departments(current_user)}
    return {"items": [row for row in rows if row["key"] in allowed or current_user.role == "admin"]}

@router.get("/{department_key}/members")
async def list_members(department_key: str, current_user: CurrentUser = Depends(require_permission("dashboard.read"))):
    if current_user.role != "admin" and department_key not in {d["key"] for d in accessible_departments(current_user)}:
        raise HTTPException(status_code=403, detail="Department access denied")
    return {"items": await service.members(department_key)}
