import hashlib
import hmac
import secrets
from typing import Optional


def generate_research_key(agent_id: str, secret: str) -> str:
    payload = f"{agent_id}:{secrets.token_hex(16)}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_research_key(key: str, agent_id: str, secret: str) -> bool:
    try:
        payload, sig = key.rsplit(":", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected) and payload.startswith(f"{agent_id}:")
    except (ValueError, AttributeError):
        return False