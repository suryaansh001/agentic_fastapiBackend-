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
from jose import jwt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database.models import User, Member, Company, Contact, Deal

DATABASE_URL = "sqlite+aiosqlite:///./test.db"
SECRET_KEY = "test-secret-key"
TEST_USER_ID = "user_1"

engine_test = create_async_engine(DATABASE_URL, echo=False)
async_session_factory_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


def create_test_app():
    from app.agent.router import router as agent_router
    from app.agent.internal_router import router as internal_agent_router
    from app.agent.agents.root.router import router as root_agent_router
    from app.agent.agents.runner.router import router as runner_agent_router
    app = FastAPI(title="Agentic CRM API", version="0.1.0")
    for router in [agent_router, internal_agent_router, root_agent_router, runner_agent_router]:
        app.include_router(router)
    return app


def mint_token(user_id: str = TEST_USER_ID) -> str:
    """Mint a valid HS256 token for tests, mirroring authenticate_token."""
    return jwt.encode({"sub": user_id}, SECRET_KEY, algorithm="HS256")


def auth_headers(user_id: str = TEST_USER_ID) -> dict:
    return {"Authorization": f"Bearer {mint_token(user_id)}"}


def dev_headers(email: str = "test@example.com") -> dict:
    """Dev-mode headers (no bearer token); only works when AUTH_DEV_MODE is on."""
    return {"X-Dev-User-Email": email}


@pytest.fixture
async def seed_data():
    """Idempotent seed: baseline rows are already inserted by the
    conftest setup_db fixture; this only inserts when missing."""
    async with async_session_factory_test() as session:
        if await session.get(User, TEST_USER_ID) is None:
            user = User(id=TEST_USER_ID, name="Test User", email="test@example.com")
            member = Member(id="member_1", organization_id="org_1", user_id=TEST_USER_ID, role="owner")
            company = Company(id="company_1", name="Acme Corp", domain="acme.com", website="https://acme.com")
            contact = Contact(id="contact_1", first_name="John", last_name="Doe", email="john@acme.com", company_id="company_1")
            deal = Deal(id="deal_1", name="Enterprise Deal", company_id="company_1", owner_id=TEST_USER_ID, stage="DEMO_BOOKED", amount=50000.0)
            session.add_all([user, member, company, contact, deal])
            await session.commit()
        return {
            "user": {"id": TEST_USER_ID, "name": "Test User", "email": "test@example.com"},
            "company": {"id": "company_1", "name": "Acme Corp", "domain": "acme.com"},
            "contact": {"id": "contact_1", "first_name": "John", "last_name": "Doe", "email": "john@acme.com"},
            "deal": {"id": "deal_1", "name": "Enterprise Deal", "stage": "DEMO_BOOKED", "amount": 50000.0},
        }
