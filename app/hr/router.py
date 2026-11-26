from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.hr.service import hr_service

router = APIRouter()

@router.get("/employees")
async def list_employees(skip: int = 0, limit: int = 100, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await hr_service.list_employees(skip, limit)}

@router.post("/employees")
async def create_employee(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await hr_service.create_employee(data)

@router.put("/employees/{id}")
async def update_employee(id: str, data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await hr_service.update_employee(id, data)

@router.get("/attendance")
async def list_attendance(skip: int = 0, limit: int = 100, user_id: str = "", current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await hr_service.list_attendance(skip, limit, user_id)}

@router.post("/attendance")
async def upsert_attendance(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await hr_service.upsert_attendance(data)

@router.get("/leave")
async def list_leave(skip: int = 0, limit: int = 100, user_id: str = "", current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await hr_service.list_leave(skip, limit, user_id)}

@router.post("/leave")
async def create_leave(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await hr_service.create_leave(data)

@router.put("/leave/{id}/status")
async def update_leave_status(id: str, status: str, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await hr_service.update_leave_status(id, status)

@router.post("/payroll/simulate")
async def simulate_payroll(data: dict, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return await hr_service.simulate_payroll(data)
