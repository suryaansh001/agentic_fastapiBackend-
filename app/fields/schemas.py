from pydantic import BaseModel
from typing import Optional, Dict

class FieldDefinitionCreate(BaseModel):
    entity: str
    key: str
    label: str
    type: str
    required: bool = False
    show_on_table: bool = False
    show_on_filter: bool = True
    sortable: bool = False

class FieldDefinitionUpdate(BaseModel):
    label: Optional[str] = None
    required: Optional[bool] = None
    show_on_table: Optional[bool] = None
    show_on_filter: Optional[bool] = None

class FieldDefinitionResponse(BaseModel):
    id: str
    entity: str
    key: str
    label: str
    type: str
    required: bool
    show_on_table: bool
    show_on_filter: bool
