from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser, require_role
from app.fields.service import FieldsService
from app.fields.schemas import FieldDefinitionCreate, FieldDefinitionUpdate, FieldDefinitionResponse
from app.utils.pagination import ListInput, build_list_response

router = APIRouter()
service = FieldsService()

@router.get("/")
async def list_fields(
    entity: str = "", page: int = 1, page_size: int = 25,
    current_user: CurrentUser = Depends(get_current_user)
):
    return await service.list(entity, page, page_size)

@router.post("/")
async def create_field(data: FieldDefinitionCreate, current_user: CurrentUser = Depends(require_role("owner", "manager"))):
    return await service.create(data.model_dump())

@router.put("/{id}")
async def update_field(id: str, data: FieldDefinitionUpdate, current_user: CurrentUser = Depends(require_role("owner", "manager"))):
    return await service.update(id, data.model_dump())

@router.delete("/{id}")
async def delete_field(id: str, current_user: CurrentUser = Depends(require_role("owner", "manager"))):
    return await service.remove(id)
