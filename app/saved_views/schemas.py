from pydantic import BaseModel
from typing import Optional, Dict, Any

class SavedViewCreate(BaseModel):
    entity: str
    name: str
    filters: Dict[str, Any] = {}
    shared: bool = False

class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    shared: Optional[bool] = None
