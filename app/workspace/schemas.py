from pydantic import BaseModel
from typing import Optional

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    narrative: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    website: Optional[str]
    slug: Optional[str]
