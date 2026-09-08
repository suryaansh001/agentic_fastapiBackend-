from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser, require_role
from app.deals.service import DealsService
from app.deals.schemas import DealCreate, DealUpdate, DealResponse
from app.utils.pagination import ListInput, build_list_response

router = APIRouter()
service = DealsService()

@router.get("/")
async def list_deals(
    q: str = "", sort: str = "", dir: str = "asc",
    page: int = 1, page_size: int = 25, filters: dict = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    input = ListInput(q=q, sort=sort, dir=dir, page=page, page_size=page_size, filters=filters or {})
    result = await service.list(input)
    return build_list_response(result["rows"], result["total"], result["facet_counts"])

@router.get("/board")
async def get_board_view(current_user: CurrentUser = Depends(get_current_user)):
    return {"columns": [], deals: []}

@router.post("/")
async def create_deal(data: DealCreate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.create(data.model_dump())

@router.get("/{id}")
async def get_deal(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_by_id(id)

@router.put("/{id}")
async def update_deal(id: str, data: DealUpdate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.update(id, data.model_dump())

@router.post("/{id}/set-stage")
async def set_deal_stage(id: str, stage: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.set_stage(id, stage)

@router.delete("/{id}")
async def delete_deal(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.remove(id)
