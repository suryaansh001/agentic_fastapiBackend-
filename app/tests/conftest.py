import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["BETTER_AUTH_SECRET"] = "test-secret-key"
os.environ["DIRECT_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["BETTER_AUTH_URL"] = "http://localhost:3001"
os.environ["API_URL"] = "http://localhost:3001"
os.environ["APP_URL"] = "http://localhost:3000"
os.environ["REDIS_URL"] = ""
os.environ["BLOB_READ_WRITE_TOKEN"] = ""
os.environ["AGENT_BRIDGE_SECRET"] = "test-bridge-secret"
# Dev-mode allow-list: explicit emails only, never "*".
os.environ["ALLOWED_SIGN_IN"] = "test@example.com"
os.environ["AUTH_DEV_MODE"] = "true"
os.environ["CRON_SECRET"] = "test-cron-secret-key"
os.environ["DEBUG"] = "true"
os.environ["ENV"] = "test"
os.environ["CONTEXT_DEV_API_KEY"] = ""
os.environ["PERPLEXITY_API_KEY"] = ""
os.environ["AI_GATEWAY_API_KEY"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["MICROSOFT_CLIENT_ID"] = ""
os.environ["MICROSOFT_CLIENT_SECRET"] = ""
os.environ["MICROSOFT_TENANT_ID"] = "common"
os.environ["IS_MARKETING"] = ""
os.environ["REPORTING_CURRENCY"] = "USD"
os.environ["ARCHIVE_RETENTION_DAYS"] = "180"
os.environ["CACHE_TTL_MS"] = "60000"
os.environ["ENRICHMENT_POLL_MS"] = "30000"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"] = "llama3.1"
os.environ["GROQ_API_KEY"] = "gsk_test_key_for_testing"
os.environ["GROQ_MODEL"] = "llama-3.1-70b-versatile"
os.environ["AGENT_WORKSPACE_ROOT"] = "./agent_workspace"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine as sync_engine
from sqlalchemy.orm import Session
from app.database.session import Base, engine, async_session_factory
from app.database.models import User, Member, Company, Contact, Deal
from app.agent.router import router as agent_router
from app.agent.internal_router import router as internal_agent_router
from app.agent.agents.root.router import router as root_agent_router
from app.agent.agents.runner.router import router as runner_agent_router
# Register the seed_data fixture defined in test_fixtures
from app.tests.test_fixtures import seed_data  # noqa: F401


def _seed_sync(engine_sync) -> None:
    """Seed baseline rows so authenticated tests have a user to look up.

    Runs for every test (tables are dropped afterwards), so both sync
    TestClient tests and async tests start from the same baseline.
    """
    with Session(engine_sync) as session:
        if session.get(User, "user_1") is not None:
            return
        session.add_all([
            User(id="user_1", name="Test User", email="test@example.com"),
            Member(id="member_1", organization_id="org_1", user_id="user_1", role="owner"),
            Company(id="company_1", name="Acme Corp", domain="acme.com", website="https://acme.com"),
            Contact(id="contact_1", first_name="John", last_name="Doe", email="john@acme.com", company_id="company_1"),
            Deal(id="deal_1", name="Enterprise Deal", company_id="company_1", owner_id="user_1", stage="DEMO_BOOKED", amount=50000.0),
        ])
        session.commit()


def create_app():
    app = FastAPI(title="Agentic CRM API", version="0.1.0")
    app.include_router(agent_router)
    app.include_router(internal_agent_router, prefix="")
    app.include_router(root_agent_router)
    app.include_router(runner_agent_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app

@pytest.fixture(scope="module")
def test_app():
    app = create_app()
    yield TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    engine_sync = sync_engine("sqlite:///./test.db", echo=False)
    Base.metadata.create_all(engine_sync)
    _seed_sync(engine_sync)
    yield
    Base.metadata.drop_all(engine_sync)
    engine_sync.dispose()

@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()
        await session.close()

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}