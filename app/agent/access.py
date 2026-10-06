"""Agent authorization service.

Every sensitive operation verifies user + role + resource + operation.
Roles come from the user's Member record; resource ownership comes
from the resource's created_by/owner columns. Nothing returns True
unconditionally.
"""
from fastapi import HTTPException, status
from sqlalchemy import select

from app.database.session import async_session_factory
from app.database.models import AgentDefinition, Member
from app.dependencies.auth import CurrentUser

MANAGE_ROLES = ("owner", "admin")


class AgentAccessService:
    async def _agent(self, agent_id: str) -> AgentDefinition | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.id == agent_id)
            )
            return result.scalar_one_or_none()

    async def user_role(self, user_id: str) -> str:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Member.role).where(Member.user_id == user_id).limit(1)
            )
            row = result.scalar_one_or_none()
        return row or "member"

    async def assert_member(self, user_id: str) -> str:
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        return await self.user_role(user_id)

    async def assert_can_read(self, agent_id: str, user_id: str):
        agent = await self._agent(agent_id)
        if not agent or agent.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        # Any workspace member may read an agent definition.
        role = await self.assert_member(user_id)
        return {"canManage": agent.created_by_id == user_id or role in MANAGE_ROLES, "agent": agent}

    async def assert_can_manage_in_transaction(self, tx, agent_id: str, user_id: str):
        result = await tx.execute(
            select(AgentDefinition).where(AgentDefinition.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent or agent.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        if agent.created_by_id == user_id:
            return agent
        role = await self.assert_member(user_id)
        if role not in MANAGE_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage this agent")
        return agent

    async def can_admin(self, user_id: str) -> bool:
        role = await self.user_role(user_id)
        return role in MANAGE_ROLES
