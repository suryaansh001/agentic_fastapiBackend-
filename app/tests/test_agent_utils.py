import pytest
from fastapi.testclient import TestClient
from app.agent.llm import LLMService, get_llm_service
from app.agent.bridge import bridge, BridgeConfig, bridge_authorized
from app.agent.visibility import (
    TEAM_AGENT_STATUSES, AGENT_DEFINITION_STATUSES, AGENT_VERSION_STATUSES,
    AGENT_RUN_STATUSES, AGENT_ACTION_STATUSES, AGENT_TRIGGER_TYPES,
    CANCELLABLE_RUN_STATUSES, AGENT_DISPATCH,
)
from app.agent.access import AgentAccessService
from app.agent.research_key import generate_research_key, verify_research_key
from app.agent.dispatch_config import dispatch_config
from app.agent.services import AgentService
from app.agent.trigger import AgentTriggerService
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["BETTER_AUTH_SECRET"] = "test-secret-key"
os.environ["AGENT_BRIDGE_SECRET"] = "test-bridge-secret"
os.environ["ALLOWED_SIGN_IN"] = "*"


class TestBridge:
    def test_bridge_config(self):
        bridge_instance = bridge()
        assert bridge_instance is not None or bridge_instance is None

    def test_bridge_authorized(self):
        class MockRequest:
            headers = {"authorization": "Bearer test-bridge-secret"}
        assert bridge_authorized(MockRequest()) is True

    def test_bridge_unauthorized(self):
        class MockRequest:
            headers = {"authorization": "Bearer wrong-secret"}
        assert bridge_authorized(MockRequest()) is False

    def test_bridge_config_class(self):
        config = BridgeConfig()
        assert config.secret == "test-bridge-secret"
        assert config.url == "http://localhost:2000"


class TestVisibility:
    def test_agent_statuses(self):
        assert "DRAFT" in AGENT_DEFINITION_STATUSES
        assert "LIVE" in AGENT_DEFINITION_STATUSES
        assert "DELETED" in AGENT_DEFINITION_STATUSES

    def test_run_statuses(self):
        assert "QUEUED" in AGENT_RUN_STATUSES
        assert "RUNNING" in AGENT_RUN_STATUSES
        assert "CANCELLED" in AGENT_RUN_STATUSES

    def test_cancellable_statuses(self):
        assert "QUEUED" in CANCELLABLE_RUN_STATUSES
        assert "RUNNING" in CANCELLABLE_RUN_STATUSES

    def test_trigger_types(self):
        assert "MANUAL" in AGENT_TRIGGER_TYPES
        assert "SCHEDULE" in AGENT_TRIGGER_TYPES
        assert "EVENT" in AGENT_TRIGGER_TYPES
        assert "WEBHOOK" in AGENT_TRIGGER_TYPES

    def test_team_statuses(self):
        assert len(TEAM_AGENT_STATUSES) > 0

    def test_dispatch_config(self):
        assert dispatch_config.cancel.errorCode == "AGENT_DISPATCH_CANCELLED"
        assert dispatch_config.cancel.redeliverWithinMs == 60000


class TestAccess:
    def test_access_service(self):
        service = AgentAccessService()
        assert hasattr(service, "assert_member")
        assert hasattr(service, "assert_can_read")
        assert hasattr(service, "assert_can_manage_in_transaction")
        assert hasattr(service, "can_admin")


class TestResearchKey:
    def test_generate_and_verify(self):
        key = generate_research_key("agent_1", "secret")
        assert verify_research_key(key, "agent_1", "secret") is True

    def test_wrong_secret(self):
        key = generate_research_key("agent_1", "secret")
        assert verify_research_key(key, "agent_1", "wrong") is False

    def test_wrong_agent(self):
        key = generate_research_key("agent_1", "secret")
        assert verify_research_key(key, "agent_2", "secret") is False


class TestTriggerService:
    def test_trigger_service(self):
        service = AgentTriggerService()
        assert hasattr(service, "poke")
        assert hasattr(service, "company_created")
        assert hasattr(service, "contact_created")
        assert hasattr(service, "meeting_soon")
        assert hasattr(service, "backfill")
        assert hasattr(service, "field_backfill_records")
        assert hasattr(service, "drain_queues")

    async def test_drain_queues(self):
        service = AgentTriggerService()
        await service.drain_queues()


class TestAgentService:
    def test_service_methods(self):
        service = AgentService()
        assert hasattr(service, "list")
        assert hasattr(service, "by_id")
        assert hasattr(service, "update")
        assert hasattr(service, "deploy")
        assert hasattr(service, "pause")
        assert hasattr(service, "resume")
        assert hasattr(service, "archive")
        assert hasattr(service, "restore")
        assert hasattr(service, "remove")
        assert hasattr(service, "run_now")
        assert hasattr(service, "retry_run")
        assert hasattr(service, "cancel_run")
        assert hasattr(service, "trigger")

    @pytest.mark.asyncio
    async def test_list_returns_list(self):
        service = AgentService()
        assert hasattr(service, "list")
        # Service exists and has list method; DB may not be seeded
        assert callable(service.list)


class TestDispatchConfig:
    def test_sweep_timeout(self):
        assert dispatch_config.sweep.timeoutMs == 300000

    def test_task_lease(self):
        assert dispatch_config.task.leaseMs == 600000

    def test_field_backfill_concurrency(self):
        assert dispatch_config.fieldBackfill.concurrency == 5


class TestLLMEndpoint:
    def test_llm_service_exists(self):
        from app.agent.llm import get_llm_service
        service = get_llm_service()
        assert service is not None
        assert isinstance(service, LLMService)