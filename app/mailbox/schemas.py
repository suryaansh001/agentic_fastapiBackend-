from pydantic import BaseModel
from typing import Optional, Dict, Any

class MailboxCreate(BaseModel):
    pass

class MailboxUpdate(BaseModel):
    pass

class MailboxResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
