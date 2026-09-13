from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AgentDefinitionStatus(str, Enum):
    DRAFT = "DRAFT"
    DEPLOYING = "DEPLOYING"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class AgentVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    READY = "READY"
    DEPLOYED = "DEPLOYED"
    REJECTED = "REJECTED"


class AgentRunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentActionStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentTriggerType(str, Enum):
    MANUAL = "MANUAL"
    SCHEDULE = "SCHEDULE"
    EVENT = "EVENT"
    WEBHOOK = "WEBHOOK"


# Input schemas
class AgentUpdateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class AgentReviseInput(BaseModel):
    agent_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    actions: Optional[list[str]] = None
    channel: Optional[dict] = None
    resources: Optional[list[dict]] = None
    client_request_id: str


class AgentDeployInput(BaseModel):
    agent_id: str
    version_id: str
    client_request_id: str


class AgentRunNowInput(BaseModel):
    agent_id: str
    client_request_id: str


class AgentRetryRunInput(BaseModel):
    agent_id: str
    run_id: str
    client_request_id: str


class AgentCancelRunInput(BaseModel):
    agent_id: str
    run_id: str


class AgentPauseInput(BaseModel):
    agent_id: str


class AgentArchiveInput(BaseModel):
    agent_id: str


# Output schemas
class AgentUserSummary(BaseModel):
    id: str
    name: str
    image: Optional[str] = None


class AgentVersionRef(BaseModel):
    id: str
    number: int


class AgentListItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    created_by: AgentUserSummary
    current_version: Optional[AgentVersionRef] = None
    triggers: list[dict] = []
    run_count: int = 0


class AgentDetail(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    created_by_id: str
    created_by: AgentUserSummary
    can_manage: bool
    created_at: str
    updated_at: str
    current_version: Optional[dict] = None
    review_version: Optional[dict] = None
    triggers: list[dict] = []
    run_count: int = 0
    capabilities: dict = {}


class AgentRunSummary(BaseModel):
    id: str
    status: str
    trigger_type: Optional[str] = None
    summary: Optional[str] = None
    model_id: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_events: int = 0
    events_truncated: bool = False
    can_cancel: bool = False


class AgentTaskInput(BaseModel):
    agent_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    deal_id: Optional[str] = None
    kind: str
    reason: str
    priority: int = 0
    budget: int = 2
    payload: Optional[dict] = None
    due_at: Optional[datetime] = None


class AgentTaskResponse(BaseModel):
    id: str
    kind: str
    status: str
    priority: int
    created_at: str