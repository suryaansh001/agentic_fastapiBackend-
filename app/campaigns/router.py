from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import CurrentUser, require_permission
from app.campaigns.service import CampaignService

router = APIRouter()
service = CampaignService()

@router.get("/")
async def list_campaigns(skip: int = 0, limit: int = 100, status: str = "", q: str = "", current_user: CurrentUser = Depends(require_permission("campaign.read"))):
    return await service.list(skip, limit, status, q)

@router.get("/{id}")
async def get_campaign(id: str, current_user: CurrentUser = Depends(require_permission("campaign.read"))):
    row = await service.get(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row

@router.post("/")
async def create_campaign(data: dict, current_user: CurrentUser = Depends(require_permission("campaign.write"))):
    return await service.create(data, current_user.id)

@router.put("/{id}")
async def update_campaign(id: str, data: dict, current_user: CurrentUser = Depends(require_permission("campaign.write"))):
    row = await service.update(id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row

@router.delete("/{id}")
async def delete_campaign(id: str, current_user: CurrentUser = Depends(require_permission("campaign.write"))):
    return await service.remove(id)

@router.post("/{id}/recipients")
async def add_recipients(id: str, data: dict, current_user: CurrentUser = Depends(require_permission("campaign.write"))):
    row = await service.add_recipients(id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row

@router.post("/{id}/send")
async def send_campaign(id: str, current_user: CurrentUser = Depends(require_permission("campaign.send"))):
    row = await service.send(id)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row

@router.post("/{id}/events")
async def campaign_event(id: str, data: dict, current_user: CurrentUser = Depends(require_permission("campaign.write"))):
    row = await service.event(id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row
