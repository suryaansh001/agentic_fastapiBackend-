from pydantic import BaseModel, EmailStr
from typing import Optional, Dict

class ContactCreate(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    company_id: Optional[str] = None
    custom_fields: Optional[Dict] = None

class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    custom_fields: Optional[Dict] = None

class ContactResponse(BaseModel):
    id: str
    first_name: str
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    title: Optional[str]
    company_id: Optional[str]
    lifecycle_stage: Optional[str]
    lead_status: Optional[str]
    custom_fields: Optional[Dict]
