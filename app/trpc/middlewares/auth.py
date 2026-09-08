from fastapi import Request, HTTPException, status
from typing import Callable

def auth_middleware(get_db):
    async def middleware(request: Request, call_next: Callable):
        response = await call_next(request)
        return response
    return middleware
