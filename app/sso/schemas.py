from pydantic import BaseModel
from typing import Optional, Dict, Any

class SsoCreate(BaseModel):
    pass

class SsoUpdate(BaseModel):
    pass

class SsoResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
