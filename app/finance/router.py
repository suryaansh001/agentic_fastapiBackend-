from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.finance.service import finance_service
router = APIRouter()
@router.get("/invoices")
async def list_invoices(skip: int = 0, limit: int = 100, current_user: CurrentUser = Depends(require_permission("crm.read"))): return {"items": await finance_service.invoices(skip, limit)}
@router.post("/invoices")
async def create_invoice(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await finance_service.create_invoice(data)
@router.get("/expenses")
async def list_expenses(skip: int = 0, limit: int = 100, current_user: CurrentUser = Depends(require_permission("crm.read"))): return {"items": await finance_service.expenses(skip, limit)}
@router.post("/expenses")
async def create_expense(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))): return await finance_service.create_expense(data)
