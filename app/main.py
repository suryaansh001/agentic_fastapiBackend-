from fastapi import FastAPI
from app.config.settings import settings
from app.database.session import engine, Base
from contextlib import asynccontextmanager
from sqlalchemy import create_engine as sync_engine
from app.dependencies import setup_dependencies
from app.middlewares import setup_middlewares
from app.trpc.context import setup_trpc

@asynccontextmanager
async def lifespan(app: FastAPI):
    sync = sync_engine(settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite"), echo=False)
    Base.metadata.create_all(sync)
    yield
    sync.dispose()
    await engine.dispose()

def setup_app(app: FastAPI) -> None:
    setup_middlewares(app)
    setup_dependencies(app)
    setup_trpc(app)
    # Register routers here — each module calls app.include_router() in its __init__.py
    from app.auth.router import router as auth_router
    from app.companies.router import router as companies_router
    from app.contacts.router import router as contacts_router
    from app.deals.router import router as deals_router
    from app.activities.router import router as activities_router
    from app.fields.router import router as fields_router
    from app.workspace.router import router as workspace_router
    from app.users.router import router as users_router
    from app.settings.router import router as settings_router
    from app.saved_views.router import router as saved_views_router
    from app.dashboard.router import router as dashboard_router
    from app.cache.router import router as cache_router
    from app.archive.router import router as archive_router
    from app.currency.router import router as currency_router
    from app.api_keys.router import router as api_keys_router
    from app.search.router import router as search_router
    from app.tracking.router import router as tracking_router
    from app.telemetry.router import router as telemetry_router
    from app.slack.router import router as slack_router
    from app.sso.router import router as sso_router
    from app.sync.router import router as sync_router
    from app.mailbox.router import router as mailbox_router
    from app.google.router import router as google_router
    from app.microsoft.router import router as microsoft_router
    from app.backfill.router import router as backfill_router
    from app.conversations.router import router as conversations_router
    from app.agent.router import router as agent_router
    from app.agent.internal_router import router as internal_agent_router
    from app.agent.agents.root.router import router as root_agent_router
    from app.agent.agents.builder.router import router as builder_agent_router
    from app.agent.agents.runner.router import router as runner_agent_router
    from app.agent.llm_router import router as llm_router

    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(companies_router, prefix="/api/companies")
    app.include_router(contacts_router, prefix="/api/contacts")
    app.include_router(deals_router, prefix="/api/deals")
    app.include_router(activities_router, prefix="/api/activities")
    app.include_router(fields_router, prefix="/api/fields")
    app.include_router(workspace_router, prefix="/api/workspace")
    app.include_router(users_router, prefix="/api/users")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(saved_views_router, prefix="/api/saved-views")
    app.include_router(dashboard_router, prefix="/api/dashboard")
    app.include_router(cache_router, prefix="/api/cache")
    app.include_router(archive_router, prefix="/api/archive")
    app.include_router(currency_router, prefix="/api/currency")
    app.include_router(api_keys_router, prefix="/api/api-keys")
    app.include_router(search_router, prefix="/api/search")
    app.include_router(tracking_router, prefix="/api/tracking")
    app.include_router(telemetry_router, prefix="/api/telemetry")
    app.include_router(slack_router, prefix="/api/slack")
    app.include_router(sso_router, prefix="/api/sso")
    app.include_router(sync_router, prefix="/api/sync")
    app.include_router(mailbox_router, prefix="/api/mailbox")
    app.include_router(google_router, prefix="/api/google")
    app.include_router(microsoft_router, prefix="/api/microsoft")
    app.include_router(backfill_router, prefix="/api/backfill")
    app.include_router(conversations_router, prefix="/api/conversations")
    app.include_router(agent_router)
    app.include_router(internal_agent_router, prefix="")
    app.include_router(root_agent_router)
    app.include_router(builder_agent_router)
    app.include_router(runner_agent_router)
    app.include_router(llm_router)

def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic CRM API",
        description="CRM API with optional agentic intelligence",
        version="0.1.0",
        lifespan=lifespan,
    )
    setup_app(app)
    return app

app = create_app()

@app.get("/health")
async def health():
    return {"status": "ok"}
