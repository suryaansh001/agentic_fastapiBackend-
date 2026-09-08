from pydantic import BaseModel
from typing import Optional, Dict, Any

class ConversationsCreate(BaseModel):
    pass

class ConversationsUpdate(BaseModel):
    pass

class ConversationsResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
