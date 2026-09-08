from pydantic import BaseModel
from typing import Optional, Dict, Any

class BackfillCreate(BaseModel):
    pass

class BackfillUpdate(BaseModel):
    pass

class BackfillResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
