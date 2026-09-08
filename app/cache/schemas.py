from pydantic import BaseModel
from typing import Optional, Dict, Any

class CacheCreate(BaseModel):
    pass

class CacheUpdate(BaseModel):
    pass

class CacheResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
