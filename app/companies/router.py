from fastapi import APIRouter, Depends, Query
from app.dependencies.auth import get_current_user, CurrentUser, require_role
from app.companies.service import CompaniesService
from app.companies.schemas import CompanyCreate, CompanyUpdate, CompanyResponse
from app.utils.pagination import ListInput, build_list_response
from app.crm.bulk import bulk_create_companies

router = APIRouter()
service = CompaniesService()

@router.get("/")
async def list_companies(
    q: str = "", sort: str = "", dir: str = "asc",
    page: int = 1, page_size: int = 25, filters: dict = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    input = ListInput(q=q, sort=sort, dir=dir, page=page, page_size=page_size, filters=filters or {})
    result = await service.list(input)
    return build_list_response(result["rows"], result["total"], result["facet_counts"])

@router.post("/")
async def create_company(data: CompanyCreate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.create(data.model_dump())

@router.get("/{id}")
async def get_company(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_by_id(id)

@router.put("/{id}")
async def update_company(id: str, data: CompanyUpdate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.update(id, data.model_dump())

@router.delete("/{id}")
async def delete_company(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.remove(id)

@router.post("/import")
async def import_companies(data: dict, current_user: CurrentUser = Depends(get_current_user)):
    return await bulk_create_companies(data["rows"])

@router.get("/domain/{domain}")
async def get_by_domain(domain: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_by_domain(domain)
