from pydantic import BaseModel
from typing import Optional, Dict, Any

class TrackingCreate(BaseModel):
    pass

class TrackingUpdate(BaseModel):
    pass

class TrackingResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
