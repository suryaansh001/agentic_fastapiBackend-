from pydantic import BaseModel
from typing import Optional, Dict, Any

class SlackCreate(BaseModel):
    pass

class SlackUpdate(BaseModel):
    pass

class SlackResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
