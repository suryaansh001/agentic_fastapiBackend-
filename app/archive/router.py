from fastapi import APIRouter, Depends
from app.dependencies.auth import CurrentUser, require_permission
from app.archive.service import ArchiveService

router = APIRouter()
service = ArchiveService()

@router.get("/")
async def list_archive(current_user: CurrentUser = Depends(require_permission("crm.read"))):
    return {"items": await service.list()}

@router.put("/{id}")
async def restore_archive(id: str, entity_type: str = "", current_user: CurrentUser = Depends(require_permission("crm.write"))):
    return await service.restore(id, entity_type)
