from pydantic import BaseModel
from typing import Optional, Dict, Any

class FieldDefinitionCreate(BaseModel):
    entity: str
    key: str
    label: str
    type: str
    required: bool = False
    show_on_table: bool = False
    show_on_filter: bool = True
    sortable: bool = False
    show_on_sheet: bool = True
    position: int = 0

class FieldDefinitionUpdate(BaseModel):
    label: Optional[str] = None
    required: Optional[bool] = None
    show_on_table: Optional[bool] = None
    show_on_filter: Optional[bool] = None
    show_on_sheet: Optional[bool] = None
    position: Optional[int] = None

class FieldValueSet(BaseModel):
    entity: str
    record_id: str
    field_id: str
    value: Any = None

class FieldDefinitionResponse(BaseModel):
    id: str
    entity: str
    key: str
    label: str
    type: str
    required: bool
    show_on_table: bool
    show_on_filter: bool
