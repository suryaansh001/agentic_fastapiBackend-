from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.contacts.service import ContactsService
from app.contacts.schemas import ContactCreate, ContactUpdate, ContactResponse
from app.utils.pagination import ListInput, build_list_response

router = APIRouter()
service = ContactsService()

@router.get("/")
async def list_contacts(
    q: str = "", sort: str = "", dir: str = "asc",
    page: int = 1, page_size: int = 25, filters: dict = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    input = ListInput(q=q, sort=sort, dir=dir, page=page, page_size=page_size, filters=filters or {})
    result = await service.list(input)
    return build_list_response(result["rows"], result["total"], result["facet_counts"])

@router.post("/")
async def create_contact(data: ContactCreate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.create(data.model_dump())

@router.get("/{id}")
async def get_contact(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_by_id(id)

@router.put("/{id}")
async def update_contact(id: str, data: ContactUpdate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.update(id, data.model_dump())

@router.delete("/{id}")
async def delete_contact(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.remove(id)
