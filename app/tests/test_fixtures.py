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
from app.agent.router import router as agent_router
from app.agent.internal_router import router as internal_agent_router
from app.agent.agents.root.router import router as root_agent_router
from app.agent.agents.builder.router import router as builder_agent_router
from app.agent.agents.runner.router import router as runner_agent_router
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database.models import User, Company, Contact, Deal

DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine_test = create_async_engine(DATABASE_URL, echo=False)
async_session_factory_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

def create_test_app():
    from fastapi import FastAPI
    from app.agent.router import router as agent_router
    from app.agent.internal_router import router as internal_agent_router
    from app.agent.agents.root.router import router as root_agent_router
    from app.agent.agents.builder.router import router as builder_agent_router
    from app.agent.agents.runner.router import router as runner_agent_router
    app = FastAPI(title="Agentic CRM API", version="0.1.0")
    for router in [agent_router, internal_agent_router, root_agent_router, builder_agent_router, runner_agent_router]:
        app.include_router(router)
    return app

def auth_headers():
    return {"Authorization": "Bearer test-token"}

@pytest.fixture
async def seed_data():
    async with async_session_factory_test() as session:
        user = User(id="user_1", name="Test User", email="test@example.com", role="owner")
        company = Company(id="company_1", name="Acme Corp", domain="acme.com", website="https://acme.com")
        contact = Contact(id="contact_1", first_name="John", last_name="Doe", email="john@acme.com", company_id="company_1")
        deal = Deal(id="deal_1", name="Enterprise Deal", company_id="company_1", owner_id="user_1", stage="DEMO_BOOKED", amount=50000.0)
        session.add_all([user, company, contact, deal])
        await session.commit()
        await session.refresh(user)
        await session.refresh(company)
        await session.refresh(contact)
        await session.refresh(deal)
        return {
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
            "company": {"id": company.id, "name": company.name, "domain": company.domain},
            "contact": {"id": contact.id, "first_name": contact.first_name, "last_name": contact.last_name, "email": contact.email},
            "deal": {"id": deal.id, "name": deal.name, "stage": deal.stage, "amount": deal.amount},
        }