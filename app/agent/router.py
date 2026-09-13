from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional
from app.dependencies.auth import get_current_user, CurrentUser
from app.database.session import async_session_factory
from app.database.models import AgentDefinition, AgentVersion, AgentRun, AgentTask
from sqlalchemy import select, func, desc
from app.agent.services import AgentService
from app.agent.schemas import *
from app.agent.trigger import AgentTriggerService

router = APIRouter(prefix="/api/agents", tags=["agents"])


def get_agent_service():
    return AgentService()


@router.get("/", response_model=list[AgentListItem])
async def list_agents(
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentDefinition)
            .where(AgentDefinition.status.in_(["DRAFT", "DEPLOYING", "LIVE", "PAUSED"]))
            .order_by(desc(AgentDefinition.updated_at))
            .offset(offset)
            .limit(limit)
        )
        agents = result.scalars().all()
        return [
            AgentListItem(
                id=a.id,
                name=a.name,
                description=a.description,
                status=a.status,
                created_at=a.created_at.isoformat() if a.created_at else "",
                updated_at=a.updated_at.isoformat() if a.updated_at else "",
                created_by=AgentUserSummary(id=a.created_by_id, name="", image=None),
                run_count=0,
            )
            for a in agents
        ]


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = AgentService()
    result = await svc.by_id(agent_id, current_user.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return result


@router.post("/{agent_id}/run", response_model=dict)
async def run_agent(
    agent_id: str,
    body: AgentRunNowInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = AgentService()
    result = await svc.run_now(body, current_user.id)
    return result


@router.post("/{agent_id}/runs/{run_id}/cancel", response_model=dict)
async def cancel_run(
    agent_id: str,
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = AgentService()
    result = await svc.cancel_run(agent_id, run_id, current_user.id)
    return result


@router.get("/{agent_id}/history", response_model=list[dict])
async def agent_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id)
            .order_by(desc(AgentRun.created_at))
            .limit(limit)
        )
        runs = result.scalars().all()
        return [
            {
                "id": r.id,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "summary": r.summary,
                "model_id": r.model_id,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
                "error_code": r.error_code,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]


@router.get("/{agent_id}/tasks", response_model=list[dict])
async def agent_tasks(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentTask)
            .where(AgentTask.agent_id == agent_id)
            .order_by(desc(AgentTask.created_at))
        )
        tasks = result.scalars().all()
        return [
            {
                "id": t.id,
                "kind": t.kind,
                "status": t.status,
                "priority": t.priority,
                "reason": t.reason,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            }
            for t in tasks
        ]


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": agent_id, "status": "PAUSED"}


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": agent_id, "status": "LIVE"}


@router.post("/{agent_id}/archive")
async def archive_agent(agent_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": agent_id, "status": "ARCHIVED"}


@router.post("/{agent_id}/restore")
async def restore_agent(agent_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": agent_id, "status": "PAUSED"}


@router.delete("/{agent_id}")
async def remove_agent(agent_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return {"id": agent_id, "status": "DELETED", "disabledTriggers": 0, "cancelledRuns": 0}


@router.post("/{agent_id}/dispatch")
async def dispatch_agent(agent_id: str, current_user: CurrentUser = Depends(get_current_user)):
    trigger = AgentTriggerService()
    trigger.poke()
    return {"status": "dispatched"}