from pydantic import BaseModel
from typing import Optional, Dict, Any

class DashboardCreate(BaseModel):
    pass

class DashboardUpdate(BaseModel):
    pass

class DashboardResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
