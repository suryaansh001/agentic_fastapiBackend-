from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.currency.service import CurrencyService

router = APIRouter()
service = CurrencyService()

@router.get("/")
async def list_currency(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await service.list()}

@router.post("/")
async def create_currency(data: dict, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.create(data)

@router.delete("/{id}")
async def delete_currency(id: str, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.remove(id)
