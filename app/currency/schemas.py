from pydantic import BaseModel
from typing import Optional, Dict, Any

class CurrencyCreate(BaseModel):
    pass

class CurrencyUpdate(BaseModel):
    pass

class CurrencyResponse(BaseModel):
    id: str
    class Config:
        from_attributes = True
