from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.database.session import async_session_factory
from app.database.models import AgentDefinition
from sqlalchemy import select, func
from typing import Optional

router = APIRouter()

@router.get("/internal/crm/dispatch-health")
async def dispatch_health(current_user: CurrentUser = Depends(get_current_user)):
    async with async_session_factory() as session:
        result = await session.execute(select(func.count(AgentDefinition.id)).where(AgentDefinition.status.in_(["LIVE", "PAUSED"])))
        active_count = result.scalar_one()
    return {"ok": True, "activeAgents": active_count, "status": "healthy"}