from fastapi import Request
from typing import Optional
from app.dependencies.auth import CurrentUser

class TrpcContext:
    def __init__(self, user: Optional[CurrentUser] = None, request: Optional[Request] = None):
        self.user = user
        self.request = request

def get_trpc_context(request: Request) -> TrpcContext:
    user = None
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        user = CurrentUser(id="", email="", name="", role="rep")
    return TrpcContext(user=user, request=request)

def setup_trpc(app):
    pass
