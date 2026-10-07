#!/usr/bin/env python3
"""Seed a coherent development dataset into the CRM database."""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.database.models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    DealContact,
    DealStage,
    EnrichmentStatus,
    ForecastCategory,
    LeadStatus,
    LifecycleStage,
    Member,
    Organization,
    RecordSource,
    User,
)
from app.database.session import async_session_factory, engine
from app.auth.service import AuthService


ADMIN_ID = "seed-admin-user"
ORG_ID = "seed-agentic-crm"
COMPANY_ID = "seed-northstar-analytics"
CONTACT_ID = "seed-maya-patel"
DEAL_ID = "seed-northstar-expansion"

async def seed():
    async with async_session_factory() as session:
        existing = await session.scalar(select(User).where(User.email == "admin@agentic-crm.local"))
        if existing:
            if not existing.password_hash:
                existing.password_hash = AuthService.hash_password("password123")
                await session.commit()
            print("seed_status=already_present")
            print(f"admin_email={existing.email}")
            print("admin_password=password123")
            return

        admin = User(
            id=ADMIN_ID,
            name="Alex Morgan",
            email="admin@agentic-crm.local",
            password_hash=AuthService.hash_password("password123"),
            email_verified=True,
        )
        organization = Organization(
            id=ORG_ID,
            name="Agentic CRM Demo",
            slug="agentic-crm-demo",
            website="https://agentic-crm.local",
            meta_data={"seeded": True, "purpose": "development demo"},
        )
        member = Member(
            id="seed-admin-membership",
            organization_id=ORG_ID,
            user_id=ADMIN_ID,
            role="admin",
        )
        company = Company(
            id=COMPANY_ID,
            name="Northstar Analytics",
            domain="northstaranalytics.example",
            website="https://northstaranalytics.example",
            description="B2B analytics platform helping operations teams turn fragmented data into reliable forecasts.",
            industry="Software",
            sub_industry="Business Intelligence",
            city="Austin",
            state_code="TX",
            country="United States",
            country_code="US",
            phone="+1-512-555-0148",
            email="hello@northstaranalytics.example",
            owner_id=ADMIN_ID,
            lifecycle_stage=LifecycleStage.OPPORTUNITY,
            lead_status=LeadStatus.OPEN_DEAL,
            record_source=RecordSource.MANUAL,
            enrichment_status=EnrichmentStatus.COMPLETE,
            enriched_at=datetime.utcnow(),
            custom_fields={"employee_band": "51-200", "priority_account": True},
        )
        contact = Contact(
            id=CONTACT_ID,
            first_name="Maya",
            last_name="Patel",
            email="maya.patel@northstaranalytics.example",
            phone="+1-512-555-0182",
            title="VP of Revenue Operations",
            seniority="VP",
            function="Revenue Operations",
            company_id=COMPANY_ID,
            owner_id=ADMIN_ID,
            lifecycle_stage=LifecycleStage.SALES_QUALIFIED_LEAD,
            lead_status=LeadStatus.CONNECTED,
            buying_role="Decision maker",
            record_source=RecordSource.MANUAL,
            enrichment_status=EnrichmentStatus.COMPLETE,
            enriched_at=datetime.utcnow(),
            custom_fields={"preferred_contact_method": "email"},
        )
        session.add_all([admin, organization, member, company, contact])
        await session.flush()

        company.primary_contact_id = CONTACT_ID
        deal = Deal(
            id=DEAL_ID,
            name="Northstar Analytics annual platform rollout",
            company_id=COMPANY_ID,
            owner_id=ADMIN_ID,
            stage=DealStage.DEMO_BOOKED,
            forecast_category=ForecastCategory.BEST_CASE,
            amount=72000.0,
            currency="USD",
            expected_close_date=datetime.utcnow() + timedelta(days=45),
            record_source=RecordSource.MANUAL,
            description="Initial rollout for revenue operations and finance teams, with expansion potential after the first two quarters.",
            custom_fields={"plan": "Enterprise", "implementation_quarter": "Q4"},
        )
        deal_contact = DealContact(
            deal_id=DEAL_ID,
            contact_id=CONTACT_ID,
            role="Economic buyer",
            is_primary_contact=True,
            label="Primary decision maker",
        )
        activity = Activity(
            id="seed-northstar-demo",
            type=ActivityType.MEETING,
            subject="Northstar Analytics discovery demo",
            body="Reviewed forecasting workflow, CRM data quality gaps, and rollout requirements with Maya Patel.",
            occurred_at=datetime.utcnow() - timedelta(days=2),
            company_id=COMPANY_ID,
            contact_id=CONTACT_ID,
            deal_id=DEAL_ID,
            created_by_id=ADMIN_ID,
        )
        session.add_all([deal, deal_contact, activity])
        await session.commit()
        print("seed_status=created")
        print("admin_email=admin@agentic-crm.local")
        print("admin_password=password123")
        print("admin_role=admin")
        print("company=Northstar Analytics")
        print("contact=maya.patel@northstaranalytics.example")
        print("deal_amount=72000 USD")
    await engine.dispose()

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed())
