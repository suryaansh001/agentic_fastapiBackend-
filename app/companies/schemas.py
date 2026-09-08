from pydantic import BaseModel, Field
from typing import Optional, Dict

class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    custom_fields: Optional[Dict] = None

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    custom_fields: Optional[Dict] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    domain: Optional[str]
    industry: Optional[str]
    lifecycle_stage: Optional[str]
    custom_fields: Optional[Dict]
    created_at: Optional[str]
