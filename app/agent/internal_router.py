from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies.auth import get_current_user, CurrentUser
from app.database.session import async_session_factory
from app.database.models import AgentTask
from sqlalchemy import select, func
from typing import Optional

router = APIRouter(prefix="/internal/crm", tags=["internal"])


@router.post("/dispatch")
async def internal_dispatch(current_user: CurrentUser = Depends(get_current_user)):
    from app.agent.trigger import AgentTriggerService
    trigger = AgentTriggerService()
    trigger.poke()
    return {"status": "dispatched"}


@router.get("/dispatch-health")
async def dispatch_health(current_user: CurrentUser = Depends(get_current_user)):
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count(AgentTask.id)).where(AgentTask.finished_at.is_(None))
        )
        pending = result.scalar_one()
    return {"ok": True, "pendingTasks": pending, "status": "healthy"}


@router.post("/agent-dispatch")
async def agent_dispatch(current_user: CurrentUser = Depends(get_current_user)):
    from app.agent.trigger import AgentTriggerService
    trigger = AgentTriggerService()
    trigger.deployed_agent_run_queued()
    return {"status": "accepted"}


@router.post("/builder-dispatch")
async def builder_dispatch(current_user: CurrentUser = Depends(get_current_user)):
    from app.agent.trigger import AgentTriggerService
    trigger = AgentTriggerService()
    trigger.builder_conversation_queued()
    return {"status": "accepted"}


@router.post("/cancel-run")
async def cancel_run(body: dict, current_user: CurrentUser = Depends(get_current_user)):
    return {"status": "cancelled"}