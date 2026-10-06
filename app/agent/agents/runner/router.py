from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.dependencies.auth import get_current_user, CurrentUser
import os

router = APIRouter(prefix="/api/agents/runner", tags=["runner-agent"])

# Tool endpoints are intentionally NOT exposed here. Agent tools are invoked
# only by the AgentExecutionEngine through the canonical tool registry.
# This router only serves generated artifacts (charts, PDFs) for viewing.

ALLOWED_DIRS = ["/tmp", os.environ.get("AGENT_WORKSPACE_ROOT", "./agent_workspace")]


@router.get("/files/{file_path:path}")
def get_file(file_path: str, current_user: CurrentUser = Depends(get_current_user)):
    """Serve generated files (charts, PDFs) for viewing/downloading"""
    full_path = None
    if os.path.isabs(file_path):
        candidate = os.path.normpath(file_path)
        if os.path.exists(candidate) and os.path.isfile(candidate):
            full_path = candidate
    if not full_path:
        for base in ALLOWED_DIRS:
            candidate = os.path.join(base, file_path)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                full_path = candidate
                break
    if not full_path:
        for base in ALLOWED_DIRS:
            candidate = os.path.join(base, os.path.basename(file_path))
            if os.path.exists(candidate) and os.path.isfile(candidate):
                full_path = candidate
                break
    if not full_path:
        raise HTTPException(status_code=404, detail="File not found")
    ext = os.path.splitext(file_path)[1].lower()
    media_type = "application/pdf" if ext == ".pdf" else ("image/svg+xml" if ext == ".svg" else "image/png")
    return FileResponse(full_path, media_type=media_type, filename=os.path.basename(file_path))
