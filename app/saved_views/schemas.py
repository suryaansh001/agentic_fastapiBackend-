from pydantic import BaseModel
from typing import Optional, Dict, Any

class SavedViewsCreate(BaseModel):
    pass

class SavedViewsUpdate(BaseModel):
    pass

class SavedViewsResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
