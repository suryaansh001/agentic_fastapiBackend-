from fastapi import HTTPException, status
from app.database.session import async_session_factory
from app.database.models import AgentDefinition, AgentVersion, AgentRun, AgentTask
from app.agent.bridge import bridge
from app.agent.trigger import AgentTriggerService
from app.agent.visibility import CANCELLABLE_RUN_STATUSES, AGENT_DISPATCH
from sqlalchemy import select
from sqlalchemy.orm import noload
from typing import Optional
from datetime import datetime, timedelta
import uuid


class AgentService:
    def __init__(self):
        self.trigger = AgentTriggerService()

    async def list(self, user_id: str) -> list[dict]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition)
                .where(AgentDefinition.status.in_(["DRAFT", "DEPLOYING", "LIVE", "PAUSED"]))
                .order_by(AgentDefinition.updated_at.desc())
                .options(noload(AgentDefinition.created_by), noload(AgentDefinition.current_version), noload(AgentDefinition.versions), noload(AgentDefinition.triggers), noload(AgentDefinition.runs))
            )
            agents = result.scalars().all()
            return [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "status": a.status,
                    "createdAt": a.created_at.isoformat() if a.created_at else "",
                    "updatedAt": a.updated_at.isoformat() if a.updated_at else "",
                    "createdBy": {"id": a.created_by_id, "name": "", "image": None},
                    "currentVersion": None,
                    "triggers": [],
                    "runCount": 0,
                }
                for a in agents
            ]

    async def by_id(self, agent_id: str, user_id: str) -> Optional[dict]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == agent_id)
            )
            agent = result.scalar_one_or_none()
        if not agent or agent.status == "DELETED":
            return None
        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status,
            "createdById": agent.created_by_id,
            "createdBy": {"id": agent.created_by_id, "name": "", "image": None},
            "canManage": agent.created_by_id == user_id,
            "createdAt": agent.created_at.isoformat() if agent.created_at else "",
            "updatedAt": agent.updated_at.isoformat() if agent.updated_at else "",
            "currentVersion": None,
            "triggers": [],
            "runCount": 0,
            "capabilities": {"readable": True, "problem": None, "actions": [], "dataScope": None, "channel": None},
        }

    async def update(self, agent_id: str, data: dict, user_id: str) -> dict:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == agent_id)
            )
            agent = result.scalar_one_or_none()
        if not agent or agent.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if agent.created_by_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage this agent")
        update_data = {}
        if "name" in data:
            update_data["name"] = data["name"]
        if "description" in data:
            update_data["description"] = data["description"]
        async with async_session_factory() as session:
            await session.execute(
                update(AgentDefinition).where(AgentDefinition.id == agent_id).values(**update_data)
            )
            await session.commit()
        return {"id": agent_id, "name": data.get("name", agent.name), "description": data.get("description", agent.description), "status": agent.status}

    async def deploy(self, agent_id: str, version_id: str, user_id: str) -> dict:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == agent_id)
            )
            agent = result.scalar_one_or_none()
        if not agent or agent.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if agent.created_by_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage this agent")
        return {"id": agent_id, "versionId": version_id, "status": "LIVE"}

    async def pause(self, agent_id: str, user_id: str) -> dict:
        return {"id": agent_id, "name": "", "status": "PAUSED"}

    async def resume(self, agent_id: str, user_id: str) -> dict:
        return {"id": agent_id, "name": "", "status": "LIVE"}

    async def archive(self, agent_id: str, user_id: str) -> dict:
        return {"id": agent_id, "name": "", "status": "ARCHIVED"}

    async def restore(self, agent_id: str, user_id: str) -> dict:
        return {"id": agent_id, "name": "", "status": "PAUSED"}

    async def remove(self, agent_id: str, user_id: str) -> dict:
        return {"id": agent_id, "name": "", "status": "DELETED", "disabledTriggers": 0, "cancelledRuns": 0}

    async def run_now(self, input_data: dict, user_id: str) -> dict:
        agent_id = input_data["agent_id"]
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == agent_id)
            )
            agent = result.scalar_one_or_none()
        if not agent or agent.status != "LIVE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent is not live")
        run_id = str(uuid.uuid4())
        async with async_session_factory() as session:
            session.add(AgentRun(
                id=run_id,
                agent_id=agent_id,
                version_id=agent.current_version_id or "",
                trigger_type="MANUAL",
                initiated_by_id=user_id,
                status="QUEUED",
            ))
            await session.commit()
        self.trigger.deployed_agent_run_queued()
        return {"id": run_id}

    async def retry_run(self, agent_id: str, run_id: str, user_id: str) -> dict:
        return {"id": str(uuid.uuid4())}

    async def cancel_run(self, agent_id: str, run_id: str, user_id: str) -> dict:
        return {"id": run_id, "status": "CANCELLED", "cancelled": True}

    async def files(self, agent_id: str, user_id: str) -> dict:
        return {"versionId": None, "files": []}

    async def save_file(self, input_data: dict, user_id: str) -> dict:
        return {"saved": True, "versionId": None}

    async def revise(self, input_data: dict, user_id: str) -> dict:
        return {"versionId": str(uuid.uuid4())}