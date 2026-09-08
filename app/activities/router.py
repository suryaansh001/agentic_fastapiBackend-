from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.activities.service import ActivitiesService
from app.activities.schemas import ActivityCreate, ActivityResponse
from app.utils.pagination import ListInput, build_list_response

router = APIRouter()
service = ActivitiesService()

@router.get("/")
async def list_activities(
    q: str = "", sort: str = "", dir: str = "asc",
    page: int = 1, page_size: int = 25, filters: dict = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    input = ListInput(q=q, sort=sort, dir=dir, page=page, page_size=page_size, filters=filters or {})
    result = await service.list(input)
    return build_list_response(result["rows"], result["total"], result["facet_counts"])

@router.post("/")
async def create_activity(data: ActivityCreate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.create(data.model_dump())

@router.get("/{id}")
async def get_activity(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.get_by_id(id)

@router.put("/{id}")
async def update_activity(id: str, data: ActivityCreate, current_user: CurrentUser = Depends(get_current_user)):
    return await service.update(id, data.model_dump())

@router.delete("/{id}")
async def delete_activity(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await service.remove(id)
