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
os.environ["ALLOWED_SIGN_IN"] = "*"
os.environ["CRON_SECRET"] = "test-cron-secret-key"
os.environ["DEBUG"] = "true"
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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine as sync_engine
from app.database.session import Base, engine, async_session_factory
from app.agent.router import router as agent_router
from app.agent.internal_router import router as internal_agent_router
from app.agent.agents.root.router import router as root_agent_router
from app.agent.agents.builder.router import router as builder_agent_router
from app.agent.agents.runner.router import router as runner_agent_router

def create_app():
    app = FastAPI(title="Agentic CRM API", version="0.1.0")
    app.include_router(agent_router)
    app.include_router(internal_agent_router, prefix="")
    app.include_router(root_agent_router)
    app.include_router(builder_agent_router)
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
    engine_sync = sync_engine("sqlite+aiosqlite:///./test.db", echo=False)
    Base.metadata.create_all(engine_sync)
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