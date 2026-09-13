from pydantic import BaseModel
from typing import Optional, Dict, Any

class ApiKeysCreate(BaseModel):
    pass

class ApiKeysUpdate(BaseModel):
    pass

class ApiKeysResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
