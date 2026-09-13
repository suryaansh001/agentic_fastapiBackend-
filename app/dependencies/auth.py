from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, SecurityScopes
from typing import Optional, AsyncGenerator
from app.database.models import User
from app.database.session import async_session_factory
from app.config.settings import settings

security = HTTPBearer(auto_error=False)

class CurrentUser:
    def __init__(self, user: Optional[User] = None, role: str = "owner", id: str = "", email: str = "", name: str = ""):
        if user is not None:
            self.id = user.id
            self.email = user.email
            self.name = user.name
        else:
            self.id = id
            self.email = email
            self.name = name
        self.role = role

async def get_db() -> AsyncGenerator:
    async with async_session_factory() as session:
        yield session

async def authenticate_token(token: str, db):
    return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db=Depends(get_db)
) -> CurrentUser:
    if settings.ALLOWED_SIGN_IN == "*":
        return CurrentUser(role="owner", id="user_1", email="test@example.com", name="Test")
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    user = await authenticate_token(token, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return CurrentUser(user=user, role=user.role)

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

def setup_dependencies(app):
    pass
