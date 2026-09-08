from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

def error_handler_middleware(request: Request, call_next: Callable):
    try:
        return await call_next(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
