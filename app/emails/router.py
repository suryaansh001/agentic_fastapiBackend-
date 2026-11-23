from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.emails.service import EmailService

router = APIRouter()
service = EmailService()

@router.get("/")
async def list_messages(skip: int = 0, limit: int = 100, thread_id: str = "", contact_id: str = "", current_user: CurrentUser = Depends(require_permission("email.read"))):
    return await service.list_messages(skip, limit, thread_id, contact_id)

@router.get("/threads")
async def list_threads(skip: int = 0, limit: int = 100, current_user: CurrentUser = Depends(require_permission("email.read"))):
    return await service.list_threads(skip, limit)

@router.get("/templates")
async def list_templates(current_user: CurrentUser = Depends(require_permission("email.read"))):
    return await service.list_templates()

@router.post("/templates")
async def create_template(data: dict, current_user: CurrentUser = Depends(require_permission("email.write"))):
    return await service.create_template(data, current_user.id)

@router.post("/reply")
async def generate_reply(data: dict, current_user: CurrentUser = Depends(require_permission("email.write"))):
    return await service.generate_reply(data)

@router.post("/draft")
async def create_draft(data: dict, current_user: CurrentUser = Depends(require_permission("email.write"))):
    return await service.create_draft(data, current_user.id)

@router.put("/{id}")
async def update_draft(id: str, data: dict, current_user: CurrentUser = Depends(require_permission("email.write"))):
    row = await service.update_draft(id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return row

@router.post("/send")
async def send_email(data: dict, current_user: CurrentUser = Depends(require_permission("email.send"))):
    return await service.send(data, current_user.id)
