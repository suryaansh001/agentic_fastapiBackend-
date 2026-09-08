from fastapi import Request
import logging

logger = logging.getLogger(__name__)

def logging_middleware(request: Request, call_next: Callable):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response
