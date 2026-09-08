from pydantic import BaseModel
from typing import Optional, Dict, Any

class SettingsCreate(BaseModel):
    pass

class SettingsUpdate(BaseModel):
    pass

class SettingsResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
