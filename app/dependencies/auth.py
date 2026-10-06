from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, AsyncGenerator

from sqlalchemy import select

from app.database.models import Member, User
from app.database.session import async_session_factory
from app.config.settings import settings

security = HTTPBearer(auto_error=False)

# Roles in ascending privilege order. RBAC decisions are made against
# these roles, never against a hardcoded "owner".
ROLE_HIERARCHY = {"readonly": 0, "rep": 1, "manager": 2, "owner": 3, "admin": 3}


class CurrentUser:
    def __init__(self, user: Optional[User] = None, role: str = "member", id: str = "", email: str = "", name: str = ""):
        if user is not None:
            self.id = user.id
            self.email = user.email
            self.name = user.name
        else:
            self.id = id
            self.email = email
            self.name = name
        self.role = role

    @property
    def role_level(self) -> int:
        return ROLE_HIERARCHY.get(self.role, -1)


async def get_db() -> AsyncGenerator:
    async with async_session_factory() as session:
        yield session


async def authenticate_token(token: str, db) -> Optional[User]:
    """Verify a bearer token and return the corresponding user.

    Tokens are HMAC-signed (HS256) with SECRET_KEY and carry the user
    id in the subject claim. An invalid, expired, or unsigned token
    yields None - authentication fails closed.
    """
    if not token:
        return None
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _primary_role(user_id: str, db) -> str:
    result = await db.execute(
        select(Member.role).where(Member.user_id == user_id).limit(1)
    )
    row = result.scalar_one_or_none()
    return row or "member"


async def _dev_user_by_email(email: str, db) -> Optional[CurrentUser]:
    """Development-only sign-in convenience.

    ALLOWED_SIGN_IN is a comma-separated list of explicit emails that
    may act without a bearer token when AUTH_DEV_MODE is enabled.
    "*" is never accepted. The resulting user receives the role from
    their Member record, not a blanket owner role.
    """
    if not settings.AUTH_DEV_MODE:
        return None
    allowed = [e.strip().lower() for e in (settings.ALLOWED_SIGN_IN or "").split(",") if e.strip()]
    if not allowed or email.lower() not in allowed:
        return None
    result = await db.execute(select(User).where(User.email.ilike(email)))
    user = result.scalar_one_or_none()
    if not user:
        return None
    role = await _primary_role(user.id, db)
    return CurrentUser(user=user, role=role)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db=Depends(get_db)
) -> CurrentUser:
    if credentials:
        user = await authenticate_token(credentials.credentials, db)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        role = await _primary_role(user.id, db)
        return CurrentUser(user=user, role=role)

    # No bearer token. The only remaining path is the dev-mode email
    # allow-list via an explicit header, active only when AUTH_DEV_MODE
    # is enabled. Production builds never enable it.
    dev_email = request.headers.get("x-dev-user-email")
    if dev_email:
        user = await _dev_user_by_email(dev_email, db)
        if user:
            return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def require_role(*allowed_roles: str):
    def checker(user: CurrentUser = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return checker


def assert_can_mutate(user: CurrentUser, record_owner_id: str, allowed_roles: list[str]):
    if user.role in ("owner", "manager", "admin"):
        return
    if user.role == "rep" and user.id == record_owner_id:
        return
    if user.role == "readonly":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only access")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot mutate this record")


def setup_dependencies(app):
    pass
