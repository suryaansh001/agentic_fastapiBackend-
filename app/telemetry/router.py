from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.telemetry.otel import get_spans

router = APIRouter()

@router.get("/")
async def list_items(current_user: CurrentUser = Depends(get_current_user)):
    return {"spans": get_spans()}

@router.get("/{id}")
async def get_item(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": id}

@router.post("/")
async def create_item(data: dict, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": "new", **data}

@router.put("/{id}")
async def update_item(id: str, data: dict, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": id, **data}

@router.delete("/{id}")
async def delete_item(id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"deleted": True}
