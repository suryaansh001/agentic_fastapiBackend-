from pydantic import BaseModel
from typing import Optional, Dict, Any

class MicrosoftCreate(BaseModel):
    pass

class MicrosoftUpdate(BaseModel):
    pass

class MicrosoftResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
