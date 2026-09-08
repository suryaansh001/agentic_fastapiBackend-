from pydantic import BaseModel
from typing import Optional, Dict, Any

class CrmCreate(BaseModel):
    pass

class CrmUpdate(BaseModel):
    pass

class CrmResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
