from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser, require_role, require_permission
from app.fields.service import FieldsService
from app.fields.schemas import FieldDefinitionCreate, FieldDefinitionUpdate, FieldValueSet

router = APIRouter()
service = FieldsService()

@router.get("/")
async def list_fields(
    entity: str = "", page: int = 1, page_size: int = 100,
    current_user: CurrentUser = Depends(require_permission("crm.read"))
):
    return await service.list(entity, page, page_size)

@router.post("/")
async def create_field(data: FieldDefinitionCreate, current_user: CurrentUser = Depends(require_role("owner", "admin", "manager"))):
    return await service.create(data.model_dump())

@router.put("/{id}")
async def update_field(id: str, data: FieldDefinitionUpdate, current_user: CurrentUser = Depends(require_role("owner", "admin", "manager"))):
    return await service.update(id, data.model_dump())

@router.delete("/{id}")
async def delete_field(id: str, current_user: CurrentUser = Depends(require_role("owner", "admin", "manager"))):
    return await service.remove(id)

@router.get("/values/{entity}/{record_id}")
async def list_values(entity: str, record_id: str, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"rows": await service.list_values(entity, record_id)}

@router.post("/values")
async def set_value(data: FieldValueSet, current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.set_value(data.entity, data.record_id, data.field_id, data.value)
