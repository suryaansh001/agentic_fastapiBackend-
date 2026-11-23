from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser, require_permission
from app.search.service import SearchService

router = APIRouter()
service = SearchService()

@router.get("/")
async def search(q: str = "", limit: int = 10, current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return await service.search(q, limit)
