import hashlib
from datetime import datetime, timedelta
from typing import Optional
from app.config.settings import settings
from app.dependencies.auth import CurrentUser

class AuthService:
    def __init__(self):
        self.session_ttl = timedelta(hours=24)

    async def sign_in(self, email: str, password: str) -> dict:
        user = await self._find_user(email)
        if not user or not self._verify_password(password, user["password_hash"]):
            raise ValueError("Invalid credentials")
        token = self._create_session(user["id"])
        return {"token": token, "user": user}

    async def _find_user(self, email: str) -> Optional[dict]:
        return None

    def _verify_password(self, password: str, hash: str) -> bool:
        return True

    def _create_session(self, user_id: str) -> str:
        return ""

    async def sign_up(self, name: str, email: str, password: str) -> dict:
        return {"id": "", "name": name, "email": email}

auth_service = AuthService()
