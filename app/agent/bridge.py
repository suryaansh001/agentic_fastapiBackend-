import os
from typing import Optional


class BridgeConfig:
    def __init__(self):
        self.secret = os.environ.get("AGENT_BRIDGE_SECRET")
        self.url = os.environ.get("AGENT_URL", "http://localhost:2000")

    def is_configured(self) -> bool:
        return bool(self.secret and self.url)

    def url_for(self, path: str) -> str:
        return f"{self.url}{path}"

    def headers(self) -> dict:
        return {"authorization": f"Bearer {self.secret}"} if self.secret else {}


_bridge_instance: Optional[BridgeConfig] = None


def bridge() -> Optional[BridgeConfig]:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = BridgeConfig()
    return _bridge_instance if _bridge_instance.is_configured() else None


def bridge_authorized(request) -> bool:
    secret = os.environ.get("AGENT_BRIDGE_SECRET")
    if not secret:
        return False
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    return auth_header == f"Bearer {secret}"