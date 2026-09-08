from pydantic import BaseModel
from typing import Optional, Dict, Any

class GoogleCreate(BaseModel):
    pass

class GoogleUpdate(BaseModel):
    pass

class GoogleResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
