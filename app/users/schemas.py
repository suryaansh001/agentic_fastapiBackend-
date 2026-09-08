from pydantic import BaseModel
from typing import Optional, Dict, Any

class UsersCreate(BaseModel):
    pass

class UsersUpdate(BaseModel):
    pass

class UsersResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
