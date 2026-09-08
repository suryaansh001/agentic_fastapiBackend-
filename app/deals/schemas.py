from pydantic import BaseModel
from typing import Optional, Dict

class DealCreate(BaseModel):
    name: str
    company_id: str
    amount: Optional[float] = None
    currency: str = "USD"
    expected_close_date: Optional[str] = None
    custom_fields: Optional[Dict] = None

class DealUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    expected_close_date: Optional[str] = None
    custom_fields: Optional[Dict] = None

class DealResponse(BaseModel):
    id: str
    name: str
    stage: str
    amount: Optional[float]
    currency: str
    forecast_category: Optional[str]
    company_id: str
    owner_id: str
    stage_changed_at: Optional[str]
