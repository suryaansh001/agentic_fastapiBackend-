from pydantic import BaseModel
from typing import Optional, Dict, Any

class TelemetryCreate(BaseModel):
    pass

class TelemetryUpdate(BaseModel):
    pass

class TelemetryResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
