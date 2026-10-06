"""Agent execution engine interface.

The engine owns agent execution: it receives a run, drives the
LLM/tool loop to completion, and settles the run's terminal status.
It does NOT own authorization (FastAPI layer), billing/token
accounting (LLM adapter), or the tool registry (app/agent/tools).

Implementations must be durable: a run interrupted mid-flight is
resumable from its checkpointed state.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class AgentExecutionEngine(ABC):
    """Contract every agent execution engine implements."""

    @abstractmethod
    async def start_run(
        self,
        run_id: str,
        agent_id: str,
        version_id: str,
        input: Optional[dict] = None,
        initiated_by: Optional[str] = None,
    ) -> dict:
        """Execute a run from its initial input to a terminal state
        (or to an approval pause). Returns the execution result."""

    @abstractmethod
    async def resume_run(self, run_id: str, approval: Optional[dict] = None) -> dict:
        """Resume a run paused at an approval gate with the approver's
        decision (e.g. ``{"approved": true}``)."""

    @abstractmethod
    async def cancel_run(self, run_id: str) -> dict:
        """Cancel a run that is queued, running, or waiting approval."""

    @abstractmethod
    async def get_state(self, run_id: str) -> Optional[dict]:
        """Return the persisted execution state of a run, or None if
        the run has no checkpointed state."""
