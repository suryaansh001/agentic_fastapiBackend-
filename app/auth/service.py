import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from sqlalchemy import select
from app.config.settings import settings
from app.database.models import User
from app.database.session import async_session_factory

PASSWORD_ITERATIONS = 600_000

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
        async with async_session_factory() as session:
            user = await session.scalar(select(User).where(User.email.ilike(email)))
            if not user:
                return None
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "password_hash": user.password_hash,
            }

    def _verify_password(self, password: str, password_hash: Optional[str]) -> bool:
        if not password_hash:
            return False
        try:
            algorithm, iterations, salt, expected = password_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                bytes.fromhex(salt),
                int(iterations),
            ).hex()
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(actual, expected)

    def _create_session(self, user_id: str) -> str:
        expires_at = datetime.utcnow() + self.session_ttl
        return jwt.encode({"sub": user_id, "exp": expires_at}, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS).hex()
        return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest}"

    async def sign_up(self, name: str, email: str, password: str) -> dict:
        return {"id": "", "name": name, "email": email}

auth_service = AuthService()
