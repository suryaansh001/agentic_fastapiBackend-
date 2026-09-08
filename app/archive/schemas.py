from pydantic import BaseModel
from typing import Optional, Dict, Any

class ArchiveCreate(BaseModel):
    pass

class ArchiveUpdate(BaseModel):
    pass

class ArchiveResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
