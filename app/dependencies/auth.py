from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.config.settings import settings
from app.database.models import User

security = HTTPBearer()

class CurrentUser:
    def __init__(self, user: User, role: str):
        self.id = user.id
        self.email = user.email
        self.name = user.name
        self.role = role

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db)
) -> CurrentUser:
    token = credentials.credentials
    user = await authenticate_token(token, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return CurrentUser(user=user, role=user.role)

async def get_db():
    from app.database.session import async_session_factory
    async with async_session_factory() as session:
        yield session

def require_role(*allowed_roles: str):
    def checker(user: CurrentUser = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return checker

def assert_can_mutate(user: CurrentUser, record_owner_id: str, allowed_roles: list[str]):
    if user.role in ("owner", "manager"):
        return
    if user.role == "rep" and user.id == record_owner_id:
        return
    if user.role == "readonly":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only access")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot mutate this record")
