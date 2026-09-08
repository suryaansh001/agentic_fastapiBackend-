from pydantic import BaseModel
from typing import Optional, Dict, Any

class SearchCreate(BaseModel):
    pass

class SearchUpdate(BaseModel):
    pass

class SearchResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
