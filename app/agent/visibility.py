from dataclasses import dataclass, fields, replace
from types import SimpleNamespace

TEAM_AGENT_STATUSES = ["DRAFT", "DEPLOYING", "LIVE", "PAUSED"]

AGENT_DEFINITION_STATUSES = ["DRAFT", "DEPLOYING", "LIVE", "PAUSED", "ARCHIVED", "DELETED"]
AGENT_VERSION_STATUSES = ["DRAFT", "VALIDATING", "READY", "DEPLOYED", "REJECTED"]
AGENT_RUN_STATUSES = ["QUEUED", "RUNNING", "WAITING_FOR_APPROVAL", "SUCCEEDED", "FAILED", "CANCELLED"]
AGENT_ACTION_STATUSES = ["PLANNED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
AGENT_TRIGGER_TYPES = ["MANUAL", "SCHEDULE", "EVENT", "WEBHOOK"]

CANCELLABLE_RUN_STATUSES = ["QUEUED", "RUNNING", "WAITING_FOR_APPROVAL"]
AGENT_DISPATCH_POKE_TIMEOUT_MS = 5000
AGENT_DISPATCH_REDELIVER_WITHIN_MS = 60000
AGENT_DISPATCH_REDELIVER_BATCH = 50
AGENT_DISPATCH_FIELD_BACKFILL_CONCURRENCY = 5

@dataclass(slots=True)
class DispatchSweep:
    timeoutMs: int = 300000
    staleQueueMs: int = 300000

@dataclass(slots=True)
class DispatchTask:
    leaseMs: int = 600000

@dataclass(slots=True)
class DispatchFieldBackfill:
    concurrency: int = 5

@dataclass(slots=True)
class DispatchCancel:
    errorCode: str = "AGENT_DISPATCH_CANCELLED"
    message: str = "Cancelled by dispatch"
    redeliverWithinMs: int = 60000
    redeliverBatch: int = 50
    timeoutMs: int = 5000

@dataclass(slots=True)
class AGENT_DISPATCH:
    sweep: DispatchSweep = None
    task: DispatchTask = None
    fieldBackfill: DispatchFieldBackfill = None
    cancel: DispatchCancel = None

    def __post_init__(self):
        if self.sweep is None:
            self.sweep = DispatchSweep()
        if self.task is None:
            self.task = DispatchTask()
        if self.fieldBackfill is None:
            self.fieldBackfill = DispatchFieldBackfill()
        if self.cancel is None:
            self.cancel = DispatchCancel()

dispatch_config = AGENT_DISPATCH()