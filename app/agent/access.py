from fastapi import HTTPException, status
from app.dependencies.auth import CurrentUser, require_role
from app.database.session import async_session_factory
from app.database.models import AgentDefinition
from typing import Optional


class AgentAccessService:
    async def assert_member(self, user_id: str) -> str:
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        return "owner"

    async def assert_can_read(self, agent_id: str, user_id: str):
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == agent_id)
            )
            agent = result.scalar_one_or_none()
        if not agent or agent.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return {"canManage": user_id == agent.created_by_id, "agent": agent}

    async def assert_can_manage_in_transaction(self, tx, agent_id: str, user_id: str):
        result = await tx.execute(
            select(AgentDefinition).where(AgentDefinition.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent or agent.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if agent.created_by_id != user_id:
            role = await self.assert_member(user_id)
            if role not in ("owner", "admin"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage this agent")
        return agent

    async def can_admin(self, user_id: str) -> bool:
        return True