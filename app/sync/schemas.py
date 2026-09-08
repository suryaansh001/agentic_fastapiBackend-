from pydantic import BaseModel
from typing import Optional, Dict, Any

class SyncCreate(BaseModel):
    pass

class SyncUpdate(BaseModel):
    pass

class SyncResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
