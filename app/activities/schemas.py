from pydantic import BaseModel
from typing import Optional, Dict

class ActivityCreate(BaseModel):
    type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None
    deal_id: Optional[str] = None
    occurred_at: Optional[str] = None
    due_at: Optional[str] = None

class ActivityResponse(BaseModel):
    id: str
    type: str
    subject: Optional[str]
    body: Optional[str]
    company_id: Optional[str]
    contact_id: Optional[str]
    deal_id: Optional[str]
    created_by_id: str
