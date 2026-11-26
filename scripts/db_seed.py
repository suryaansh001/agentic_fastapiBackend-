#!/usr/bin/env python3
"""Seed a coherent development dataset into the CRM database."""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.database.models import (
    Activity,
    ActivityType,
    AgentDefinition,
    AgentDefinitionStatus,
    AgentVersion,
    AgentVersionStatus,
    Asset,
    Attendance,
    Company,
    Contact,
    Deal,
    DealContact,
    Campaign,
    CampaignEvent,
    CampaignRecipient,
    DealStage,
    Department,
    DepartmentMember,
    EmailMessage,
    EmailTemplate,
    EmailThread,
    EnrichmentStatus,
    Expense,
    ForecastCategory,
    Invoice,
    LeadStatus,
    LeaveRequest,
    LifecycleStage,
    Member,
    Organization,
    RecordSource,
    SupportTicket,
    User,
    WorkRequest,
)
from app.database.session import Base, async_session_factory, engine
from app.auth.service import AuthService


ADMIN_ID = "seed-admin-user"
ORG_ID = "seed-agentic-crm"
COMPANY_ID = "seed-northstar-analytics"
CONTACT_ID = "seed-maya-patel"
DEAL_ID = "seed-northstar-expansion"


async def ensure_agent(
    session, admin_id, agent_id, name, description, tools, instructions
):
    """Create a LIVE agent definition + deployed version if missing.

    The definition is inserted first with ``current_version_id=None``
    so the circular FK (definition -> version -> definition) is broken.
    """
    existing = await session.get(AgentDefinition, agent_id)
    if existing is not None:
        return
    definition = AgentDefinition(
        id=agent_id,
        name=name,
        description=description,
        status=AgentDefinitionStatus.LIVE,
        created_by_id=admin_id,
        current_version_id=None,
    )
    session.add(definition)
    await session.flush()
    version = AgentVersion(
        id=f"{agent_id}-v1",
        agent_id=agent_id,
        number=1,
        status=AgentVersionStatus.DEPLOYED,
        manifest={"tools": tools} if tools else {},
        instructions=instructions,
        created_by_id=admin_id,
    )
    session.add(version)
    await session.flush()
    definition.current_version_id = version.id
    await session.flush()


async def ensure_agents(session, admin_id):
    from app.agent.routing import (
        ROUTES,
        ROUTE_INSTRUCTIONS,
        ROUTE_TOOLS,
        agent_id_for_route,
    )

    await ensure_agent(
        session,
        admin_id,
        "unified",
        "Unified chat agent",
        "Default unified chat agent.",
        None,
        "Answer the user directly, using tools only when CRM data is required.",
    )
    for route in ROUTES:
        await ensure_agent(
            session,
            admin_id,
            agent_id_for_route(route),
            f"{route.replace('_', ' ').title()} agent",
            ROUTE_INSTRUCTIONS.get(route, ""),
            ROUTE_TOOLS.get(route),
            ROUTE_INSTRUCTIONS.get(route, ""),
        )
    await session.commit()


DEMO_DEPARTMENT_USERS = {
    "sales": ("Jordan Lee", "sales@agentic-crm.local", "manager", "Sales Manager"),
    "marketing": ("Priya Shah", "marketing@agentic-crm.local", "manager", "Marketing Manager"),
    "support": ("Noah Kim", "support@agentic-crm.local", "manager", "Support Manager"),
    "hr": ("Ava Brown", "hr@agentic-crm.local", "manager", "HR Manager"),
    "finance": ("Ethan Davis", "finance@agentic-crm.local", "manager", "Finance Manager"),
    "operations": ("Mia Wilson", "operations@agentic-crm.local", "manager", "Operations Manager"),
}


async def ensure_departments(session, admin_id):
    from app.rbac import DEPARTMENTS

    for key, meta in DEPARTMENTS.items():
        department = await session.scalar(select(Department).where(Department.key == key))
        if department is None:
            department = Department(key=key, name=meta["name"], description=meta["description"])
            session.add(department)
            await session.flush()
        if key == "executive":
            membership = await session.scalar(
                select(DepartmentMember).where(
                    DepartmentMember.department_id == department.id,
                    DepartmentMember.user_id == admin_id,
                )
            )
            if membership is None:
                session.add(DepartmentMember(department_id=department.id, user_id=admin_id, role="manager", job_title="Administrator"))

    for key, (name, email, role, title) in DEMO_DEPARTMENT_USERS.items():
        department = await session.scalar(select(Department).where(Department.key == key))
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                id=f"seed-{key}-user",
                name=name,
                email=email,
                password_hash=AuthService.hash_password("password123"),
                email_verified=True,
            )
            session.add(user)
            await session.flush()
        membership = await session.scalar(
            select(DepartmentMember).where(
                DepartmentMember.department_id == department.id,
                DepartmentMember.user_id == user.id,
            )
        )
        if membership is None:
            session.add(DepartmentMember(department_id=department.id, user_id=user.id, role=role, job_title=title))
    await session.commit()



async def ensure_email_messages(session, admin_id):
    threads = (await session.execute(select(EmailThread))).scalars().all()
    for thread in threads:
        existing = await session.scalar(select(EmailMessage).where(EmailMessage.thread_id == thread.id).limit(1))
        if existing is not None:
            continue
        contact = await session.get(Contact, thread.contact_id) if thread.contact_id else None
        first_name = contact.first_name if contact else "there"
        email = contact.email if contact else None
        now = datetime.utcnow()
        session.add_all([
            EmailMessage(
                thread_id=thread.id,
                contact_id=thread.contact_id,
                company_id=thread.company_id,
                direction="inbound",
                from_email=email,
                to_email="admin@agentic-crm.local",
                subject=thread.subject or "Conversation",
                body=f"Hi Alex,\n\nThanks for the note. We are reviewing priorities for next quarter and would like to understand how this could fit.\n\nBest,\n{first_name}",
                status="received",
                sent_at=now - timedelta(days=4),
                created_by_id=admin_id,
            ),
            EmailMessage(
                thread_id=thread.id,
                contact_id=thread.contact_id,
                company_id=thread.company_id,
                direction="outbound",
                from_email="admin@agentic-crm.local",
                to_email=email,
                subject=f"Re: {thread.subject or 'Conversation'}",
                body=f"Hi {first_name},\n\nHappy to walk through a short demo and tailor it to your priorities. Would Tuesday or Thursday work?\n\nBest,\nAlex",
                status="sent",
                sent_at=now - timedelta(days=3),
                created_by_id=admin_id,
            ),
        ])
    await session.commit()



async def ensure_campaigns(session, admin_id):
    existing = await session.get(Campaign, "seed-campaign-q4")
    if existing is not None:
        return
    now = datetime.utcnow()
    campaign = Campaign(
        id="seed-campaign-q4",
        name="Q4 revenue operations nurture",
        department="marketing",
        owner_id=admin_id,
        status="sent",
        type="email",
        subject="A faster way to forecast revenue",
        body="Hi {{first_name}},\n\nTeams like yours use Agentic CRM to turn fragmented pipeline data into a reliable weekly forecast.\n\nWorth a short conversation?\n\nBest,\nAlex",
        segment_filter={"lifecycle_stage": "LEAD", "limit": 6},
        sent_at=now - timedelta(days=5),
    )
    session.add(campaign)
    await session.flush()

    contacts = (await session.execute(select(Contact).where(Contact.email.is_not(None)).limit(6))).scalars().all()
    outcomes = [
        ("opened", "clicked", "replied"),
        ("opened", None, None),
        ("opened", "clicked", None),
        (None, None, None),
        ("opened", None, "replied"),
        ("opened", "clicked", "replied"),
    ]
    for contact, (opened, clicked, replied) in zip(contacts, outcomes):
        sent_at = now - timedelta(days=5)
        recipient = CampaignRecipient(
            campaign_id=campaign.id,
            contact_id=contact.id,
            company_id=contact.company_id,
            email=contact.email,
            status="sent",
            sent_at=sent_at,
            opened_at=sent_at + timedelta(hours=3) if opened else None,
            clicked_at=sent_at + timedelta(hours=5) if clicked else None,
            replied_at=sent_at + timedelta(days=1) if replied else None,
        )
        session.add(recipient)
        await session.flush()
        session.add(CampaignEvent(campaign_id=campaign.id, recipient_id=recipient.id, event_type="sent", meta={"seeded": True}))
        if opened:
            session.add(CampaignEvent(campaign_id=campaign.id, recipient_id=recipient.id, event_type="open", meta={"seeded": True}))
        if clicked:
            session.add(CampaignEvent(campaign_id=campaign.id, recipient_id=recipient.id, event_type="click", meta={"seeded": True}))
        if replied:
            session.add(CampaignEvent(campaign_id=campaign.id, recipient_id=recipient.id, event_type="reply", meta={"seeded": True}))

    template = await session.scalar(select(EmailTemplate).where(EmailTemplate.name == "Discovery follow-up"))
    if template is None:
        session.add(EmailTemplate(
            name="Discovery follow-up",
            department="sales",
            subject="Next steps after our conversation",
            body="Hi {{first_name}},\n\nThanks for the conversation. I have attached the summary and suggested next steps.\n\nBest,\nAlex",
            created_by_id=admin_id,
        ))
    await session.commit()



DEMO_COMPANIES = [
    {
        "id": "seed-brightwave-health",
        "name": "Brightwave Health",
        "domain": "brightwave.example",
        "website": "https://brightwave.example",
        "description": "Regional healthcare network modernizing patient intake and claims workflows.",
        "industry": "Healthcare",
        "sub_industry": "Provider Operations",
        "city": "Boston",
        "state_code": "MA",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-617-555-0102",
        "email": "info@brightwave.example",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.NEW,
        "employee_band": "201-500",
        "last_activity_days": 4,
    },
    {
        "id": "seed-cedarline-logistics",
        "name": "Cedarline Logistics",
        "domain": "cedarline.example",
        "website": "https://cedarline.example",
        "description": "Freight and last-mile logistics operator across the US Midwest.",
        "industry": "Logistics",
        "sub_industry": "Freight",
        "city": "Chicago",
        "state_code": "IL",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-312-555-0143",
        "email": "contact@cedarline.example",
        "lifecycle_stage": LifecycleStage.MARKETING_QUALIFIED_LEAD,
        "lead_status": LeadStatus.IN_PROGRESS,
        "employee_band": "501-1000",
        "last_activity_days": 6,
    },
    {
        "id": "seed-quantumforge",
        "name": "QuantumForge Manufacturing",
        "domain": "quantumforge.example",
        "website": "https://quantumforge.example",
        "description": "Precision components manufacturer serving automotive and aerospace OEMs.",
        "industry": "Manufacturing",
        "sub_industry": "Precision Components",
        "city": "Detroit",
        "state_code": "MI",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-313-555-0177",
        "email": "sales@quantumforge.example",
        "lifecycle_stage": LifecycleStage.SALES_QUALIFIED_LEAD,
        "lead_status": LeadStatus.CONNECTED,
        "employee_band": "1001-5000",
        "last_activity_days": 2,
    },
    {
        "id": "seed-lumen-financial",
        "name": "Lumen Financial",
        "domain": "lumenfinancial.example",
        "website": "https://lumenfinancial.example",
        "description": "Mid-market lending and treasury services provider.",
        "industry": "Financial Services",
        "sub_industry": "Lending",
        "city": "New York",
        "state_code": "NY",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-212-555-0198",
        "email": "partners@lumenfinancial.example",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.ATTEMPTED_TO_CONTACT,
        "employee_band": "201-500",
        "last_activity_days": 12,
    },
    {
        "id": "seed-greenfield-agrotech",
        "name": "Greenfield Agrotech",
        "domain": "greenfieldagro.example",
        "website": "https://greenfieldagro.example",
        "description": "Agritech cooperative deploying field sensors and yield forecasting.",
        "industry": "Agriculture",
        "sub_industry": "Agritech",
        "city": "Des Moines",
        "state_code": "IA",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-515-555-0121",
        "email": "hello@greenfieldagro.example",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.NEW,
        "employee_band": "51-200",
        "last_activity_days": 8,
    },
    {
        "id": "seed-orbital-systems",
        "name": "Orbital Systems",
        "domain": "orbitalsystems.example",
        "website": "https://orbitalsystems.example",
        "description": "Satellite mission operations and ground-segment software.",
        "industry": "Aerospace",
        "sub_industry": "Space Systems",
        "city": "Denver",
        "state_code": "CO",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-303-555-0164",
        "email": "missions@orbitalsystems.example",
        "lifecycle_stage": LifecycleStage.OPPORTUNITY,
        "lead_status": LeadStatus.OPEN_DEAL,
        "employee_band": "51-200",
        "last_activity_days": 2,
    },
    {
        "id": "seed-pulse-media",
        "name": "Pulse Media Group",
        "domain": "pulsemedia.example",
        "website": "https://pulsemedia.example",
        "description": "Digital media network monetizing video and newsletter audiences.",
        "industry": "Media",
        "sub_industry": "Digital Publishing",
        "city": "Los Angeles",
        "state_code": "CA",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-213-555-0155",
        "email": "ads@pulsemedia.example",
        "lifecycle_stage": LifecycleStage.MARKETING_QUALIFIED_LEAD,
        "lead_status": LeadStatus.OPEN,
        "employee_band": "11-50",
        "last_activity_days": 5,
    },
    {
        "id": "seed-tessellate-ai",
        "name": "Tessellate AI",
        "domain": "tessellate.example",
        "website": "https://tessellate.example",
        "description": "Early-stage AI infrastructure startup building vector data pipelines.",
        "industry": "Software",
        "sub_industry": "AI Infrastructure",
        "city": "San Francisco",
        "state_code": "CA",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-415-555-0188",
        "email": "founders@tessellate.example",
        "lifecycle_stage": LifecycleStage.SALES_QUALIFIED_LEAD,
        "lead_status": LeadStatus.CONNECTED,
        "employee_band": "11-50",
        "last_activity_days": 1,
    },
    {
        "id": "seed-harborview-retail",
        "name": "Harborview Retail",
        "domain": "harborview.example",
        "website": "https://harborview.example",
        "description": "Regional retail chain with 120 stores across the Pacific Northwest.",
        "industry": "Retail",
        "sub_industry": "Specialty Retail",
        "city": "Seattle",
        "state_code": "WA",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-206-555-0139",
        "email": "ops@harborview.example",
        "lifecycle_stage": LifecycleStage.CUSTOMER,
        "lead_status": LeadStatus.OPEN_DEAL,
        "employee_band": "501-1000",
        "last_activity_days": 3,
    },
    {
        "id": "seed-ironclad-security",
        "name": "Ironclad Security",
        "domain": "ironcladsecurity.example",
        "website": "https://ironcladsecurity.example",
        "description": "Managed detection and response provider for mid-market enterprises.",
        "industry": "Cybersecurity",
        "sub_industry": "Managed Security",
        "city": "Austin",
        "state_code": "TX",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-512-555-0173",
        "email": "sales@ironcladsecurity.example",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.NEW,
        "employee_band": "51-200",
        "last_activity_days": 7,
    },
    {
        "id": "seed-verde-energy",
        "name": "Verde Energy",
        "domain": "verdeenergy.example",
        "website": "https://verdeenergy.example",
        "description": "Renewable energy operator managing utility-scale solar and storage.",
        "industry": "Energy",
        "sub_industry": "Renewables",
        "city": "Houston",
        "state_code": "TX",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-713-555-0126",
        "email": "procurement@verdeenergy.example",
        "lifecycle_stage": LifecycleStage.OPPORTUNITY,
        "lead_status": LeadStatus.OPEN_DEAL,
        "employee_band": "1001-5000",
        "last_activity_days": 1,
    },
    {
        "id": "seed-atlas-education",
        "name": "Atlas Education",
        "domain": "atlasedu.example",
        "website": "https://atlasedu.example",
        "description": "Online tutoring marketplace for K-12 and test preparation.",
        "industry": "Education",
        "sub_industry": "EdTech",
        "city": "Remote",
        "state_code": None,
        "country": "United States",
        "country_code": "US",
        "phone": "+1-800-555-0111",
        "email": "team@atlasedu.example",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.UNQUALIFIED,
        "employee_band": "11-50",
        "last_activity_days": 21,
    },
    {
        "id": "seed-copperleaf-hospitality",
        "name": "Copperleaf Hospitality",
        "domain": "copperleaf.example",
        "website": "https://copperleaf.example",
        "description": "Boutique hotel group expanding into destination properties.",
        "industry": "Hospitality",
        "sub_industry": "Hotels",
        "city": "Miami",
        "state_code": "FL",
        "country": "United States",
        "country_code": "US",
        "phone": "+1-305-555-0190",
        "email": "growth@copperleaf.example",
        "lifecycle_stage": LifecycleStage.MARKETING_QUALIFIED_LEAD,
        "lead_status": LeadStatus.IN_PROGRESS,
        "employee_band": "201-500",
        "last_activity_days": 5,
    },
]

DEMO_CONTACTS = [
    {
        "id": "seed-contact-brightwave-coo",
        "first_name": "Elena",
        "last_name": "Ruiz",
        "email": "elena.ruiz@brightwave.example",
        "phone": "+1-617-555-0110",
        "title": "Chief Operating Officer",
        "seniority": "C-Suite",
        "function": "Operations",
        "company_id": "seed-brightwave-health",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.NEW,
        "buying_role": "Decision maker",
        "last_activity_days": 4,
    },
    {
        "id": "seed-contact-cedarline-vpops",
        "first_name": "Marcus",
        "last_name": "Bell",
        "email": "marcus.bell@cedarline.example",
        "title": "VP of Operations",
        "seniority": "VP",
        "function": "Operations",
        "company_id": "seed-cedarline-logistics",
        "lifecycle_stage": LifecycleStage.MARKETING_QUALIFIED_LEAD,
        "lead_status": LeadStatus.IN_PROGRESS,
        "buying_role": "Champion",
        "last_activity_days": 6,
    },
    {
        "id": "seed-contact-quantumforge-cfo",
        "first_name": "Priya",
        "last_name": "Nair",
        "email": "priya.nair@quantumforge.example",
        "title": "Chief Financial Officer",
        "seniority": "C-Suite",
        "function": "Finance",
        "company_id": "seed-quantumforge",
        "lifecycle_stage": LifecycleStage.SALES_QUALIFIED_LEAD,
        "lead_status": LeadStatus.CONNECTED,
        "buying_role": "Economic buyer",
        "last_activity_days": 2,
    },
    {
        "id": "seed-contact-lumen-headops",
        "first_name": "Daniel",
        "last_name": "Okafor",
        "email": "daniel.okafor@lumenfinancial.example",
        "title": "Head of Operations",
        "seniority": "Director",
        "function": "Operations",
        "company_id": "seed-lumen-financial",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.ATTEMPTED_TO_CONTACT,
        "buying_role": "Influencer",
        "last_activity_days": 12,
    },
    {
        "id": "seed-contact-greenfield-founder",
        "first_name": "Hannah",
        "last_name": "Wells",
        "email": "hannah.wells@greenfieldagro.example",
        "title": "Founder & CEO",
        "seniority": "C-Suite",
        "function": "Executive",
        "company_id": "seed-greenfield-agrotech",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.NEW,
        "buying_role": "Decision maker",
        "last_activity_days": 8,
    },
    {
        "id": "seed-contact-orbital-cto",
        "first_name": "Sam",
        "last_name": "Iyer",
        "email": "sam.iyer@orbitalsystems.example",
        "title": "Chief Technology Officer",
        "seniority": "C-Suite",
        "function": "Engineering",
        "company_id": "seed-orbital-systems",
        "lifecycle_stage": LifecycleStage.OPPORTUNITY,
        "lead_status": LeadStatus.OPEN_DEAL,
        "buying_role": "Technical evaluator",
        "last_activity_days": 2,
    },
    {
        "id": "seed-contact-orbital-procurement",
        "first_name": "Nadia",
        "last_name": "Foster",
        "email": "nadia.foster@orbitalsystems.example",
        "title": "Director of Procurement",
        "seniority": "Director",
        "function": "Procurement",
        "company_id": "seed-orbital-systems",
        "lifecycle_stage": LifecycleStage.OPPORTUNITY,
        "lead_status": LeadStatus.OPEN_DEAL,
        "buying_role": "Economic buyer",
        "last_activity_days": 3,
    },
    {
        "id": "seed-contact-pulse-headrev",
        "first_name": "Oliver",
        "last_name": "Grant",
        "email": "oliver.grant@pulsemedia.example",
        "title": "Head of Revenue",
        "seniority": "VP",
        "function": "Revenue",
        "company_id": "seed-pulse-media",
        "lifecycle_stage": LifecycleStage.MARKETING_QUALIFIED_LEAD,
        "lead_status": LeadStatus.OPEN,
        "buying_role": "Champion",
        "last_activity_days": 5,
    },
    {
        "id": "seed-contact-tessellate-founder",
        "first_name": "Ava",
        "last_name": "Chen",
        "email": "ava.chen@tessellate.example",
        "title": "Co-founder & CEO",
        "seniority": "C-Suite",
        "function": "Executive",
        "company_id": "seed-tessellate-ai",
        "lifecycle_stage": LifecycleStage.SALES_QUALIFIED_LEAD,
        "lead_status": LeadStatus.CONNECTED,
        "buying_role": "Decision maker",
        "last_activity_days": 1,
    },
    {
        "id": "seed-contact-tessellate-eng",
        "first_name": "Noah",
        "last_name": "Park",
        "email": "noah.park@tessellate.example",
        "title": "Head of Platform Engineering",
        "seniority": "Director",
        "function": "Engineering",
        "company_id": "seed-tessellate-ai",
        "lifecycle_stage": LifecycleStage.SALES_QUALIFIED_LEAD,
        "lead_status": LeadStatus.CONNECTED,
        "buying_role": "Technical evaluator",
        "last_activity_days": 2,
    },
    {
        "id": "seed-contact-harborview-coo",
        "first_name": "Grace",
        "last_name": "Lopez",
        "email": "grace.lopez@harborview.example",
        "title": "Chief Operating Officer",
        "seniority": "C-Suite",
        "function": "Operations",
        "company_id": "seed-harborview-retail",
        "lifecycle_stage": LifecycleStage.CUSTOMER,
        "lead_status": LeadStatus.OPEN_DEAL,
        "buying_role": "Executive sponsor",
        "last_activity_days": 3,
    },
    {
        "id": "seed-contact-ironclad-cio",
        "first_name": "Victor",
        "last_name": "Hughes",
        "email": "victor.hughes@ironcladsecurity.example",
        "title": "Chief Information Officer",
        "seniority": "C-Suite",
        "function": "IT",
        "company_id": "seed-ironclad-security",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.NEW,
        "buying_role": "Decision maker",
        "last_activity_days": 7,
    },
    {
        "id": "seed-contact-verde-coo",
        "first_name": "Isabel",
        "last_name": "Moreno",
        "email": "isabel.moreno@verdeenergy.example",
        "title": "Chief Operating Officer",
        "seniority": "C-Suite",
        "function": "Operations",
        "company_id": "seed-verde-energy",
        "lifecycle_stage": LifecycleStage.OPPORTUNITY,
        "lead_status": LeadStatus.OPEN_DEAL,
        "buying_role": "Economic buyer",
        "last_activity_days": 1,
    },
    {
        "id": "seed-contact-verde-procurement",
        "first_name": "Liam",
        "last_name": "Brooks",
        "email": "liam.brooks@verdeenergy.example",
        "title": "Procurement Manager",
        "seniority": "Manager",
        "function": "Procurement",
        "company_id": "seed-verde-energy",
        "lifecycle_stage": LifecycleStage.OPPORTUNITY,
        "lead_status": LeadStatus.OPEN_DEAL,
        "buying_role": "Gatekeeper",
        "last_activity_days": 4,
    },
    {
        "id": "seed-contact-atlas-founder",
        "first_name": "Zoe",
        "last_name": "Kim",
        "email": "zoe.kim@atlasedu.example",
        "title": "Founder",
        "seniority": "C-Suite",
        "function": "Executive",
        "company_id": "seed-atlas-education",
        "lifecycle_stage": LifecycleStage.LEAD,
        "lead_status": LeadStatus.UNQUALIFIED,
        "buying_role": "Decision maker",
        "last_activity_days": 21,
    },
    {
        "id": "seed-contact-copperleaf-gm",
        "first_name": "Rafael",
        "last_name": "Santos",
        "email": "rafael.santos@copperleaf.example",
        "title": "General Manager",
        "seniority": "VP",
        "function": "Operations",
        "company_id": "seed-copperleaf-hospitality",
        "lifecycle_stage": LifecycleStage.MARKETING_QUALIFIED_LEAD,
        "lead_status": LeadStatus.IN_PROGRESS,
        "buying_role": "Champion",
        "last_activity_days": 5,
    },
]

DEMO_PRIMARY_CONTACTS = {
    "seed-brightwave-health": "seed-contact-brightwave-coo",
    "seed-cedarline-logistics": "seed-contact-cedarline-vpops",
    "seed-quantumforge": "seed-contact-quantumforge-cfo",
    "seed-lumen-financial": "seed-contact-lumen-headops",
    "seed-greenfield-agrotech": "seed-contact-greenfield-founder",
    "seed-orbital-systems": "seed-contact-orbital-cto",
    "seed-pulse-media": "seed-contact-pulse-headrev",
    "seed-tessellate-ai": "seed-contact-tessellate-founder",
    "seed-harborview-retail": "seed-contact-harborview-coo",
    "seed-ironclad-security": "seed-contact-ironclad-cio",
    "seed-verde-energy": "seed-contact-verde-coo",
    "seed-atlas-education": "seed-contact-atlas-founder",
    "seed-copperleaf-hospitality": "seed-contact-copperleaf-gm",
}

DEMO_DEALS = [
    {
        "id": "seed-deal-orbital-rollout",
        "name": "Orbital Systems mission operations rollout",
        "company_id": "seed-orbital-systems",
        "contact_id": "seed-contact-orbital-cto",
        "stage": DealStage.QUALIFIED_TO_BUY,
        "forecast_category": ForecastCategory.PIPELINE,
        "amount": 98000.0,
        "expected_close_days": 60,
        "description": "Ground-segment analytics rollout for two mission programs.",
        "last_activity_days": 2,
    },
    {
        "id": "seed-deal-verde-storage",
        "name": "Verde Energy storage portfolio analytics",
        "company_id": "seed-verde-energy",
        "contact_id": "seed-contact-verde-coo",
        "stage": DealStage.DECISION_MAKER_BOUGHT_IN,
        "forecast_category": ForecastCategory.COMMIT,
        "amount": 240000.0,
        "expected_close_days": 30,
        "description": "Enterprise agreement for storage performance forecasting.",
        "last_activity_days": 1,
    },
    {
        "id": "seed-deal-tessellate-platform",
        "name": "Tessellate AI platform pilot",
        "company_id": "seed-tessellate-ai",
        "contact_id": "seed-contact-tessellate-founder",
        "stage": DealStage.DEMO_BOOKED,
        "forecast_category": ForecastCategory.PIPELINE,
        "amount": 42000.0,
        "expected_close_days": 45,
        "description": "Six-week pilot with option to expand to the platform team.",
        "last_activity_days": 1,
    },
    {
        "id": "seed-deal-harborview-renewal",
        "name": "Harborview Retail annual renewal",
        "company_id": "seed-harborview-retail",
        "contact_id": "seed-contact-harborview-coo",
        "stage": DealStage.CONTRACT_SENT,
        "forecast_category": ForecastCategory.COMMIT,
        "amount": 130000.0,
        "expected_close_days": 14,
        "description": "Renewal plus two new store cohorts.",
        "last_activity_days": 3,
    },
    {
        "id": "seed-deal-cedarline-visibility",
        "name": "Cedarline shipment visibility",
        "company_id": "seed-cedarline-logistics",
        "contact_id": "seed-contact-cedarline-vpops",
        "stage": DealStage.QUALIFIED_TO_BUY,
        "forecast_category": ForecastCategory.BEST_CASE,
        "amount": 65000.0,
        "expected_close_days": 70,
        "description": "Real-time shipment visibility for Midwest lanes.",
        "last_activity_days": 6,
    },
    {
        "id": "seed-deal-quantumforge-quality",
        "name": "QuantumForge quality analytics",
        "company_id": "seed-quantumforge",
        "contact_id": "seed-contact-quantumforge-cfo",
        "stage": DealStage.DEMO_BOOKED,
        "forecast_category": ForecastCategory.PIPELINE,
        "amount": 88000.0,
        "expected_close_days": 55,
        "description": "Defect prediction across three production lines.",
        "last_activity_days": 2,
    },
    {
        "id": "seed-deal-pulse-monetization",
        "name": "Pulse Media audience monetization",
        "company_id": "seed-pulse-media",
        "contact_id": "seed-contact-pulse-headrev",
        "stage": DealStage.QUALIFIED_TO_BUY,
        "forecast_category": ForecastCategory.BEST_CASE,
        "amount": 28000.0,
        "expected_close_days": 40,
        "description": "Audience segmentation for newsletter sponsorship pricing.",
        "last_activity_days": 5,
    },
    {
        "id": "seed-deal-copperleaf-expansion",
        "name": "Copperleaf destination property expansion",
        "company_id": "seed-copperleaf-hospitality",
        "contact_id": "seed-contact-copperleaf-gm",
        "stage": DealStage.DEMO_BOOKED,
        "forecast_category": ForecastCategory.PIPELINE,
        "amount": 54000.0,
        "expected_close_days": 50,
        "description": "Revenue management rollout for two new properties.",
        "last_activity_days": 5,
    },
    {
        "id": "seed-deal-lumen-treasury",
        "name": "Lumen treasury automation",
        "company_id": "seed-lumen-financial",
        "contact_id": "seed-contact-lumen-headops",
        "stage": DealStage.CLOSED_LOST,
        "forecast_category": ForecastCategory.OMITTED,
        "amount": 120000.0,
        "expected_close_days": -20,
        "description": "Lost to an incumbent treasury vendor on price.",
        "last_activity_days": 12,
    },
    {
        "id": "seed-deal-greenfield-yield",
        "name": "Greenfield yield forecasting",
        "company_id": "seed-greenfield-agrotech",
        "contact_id": "seed-contact-greenfield-founder",
        "stage": DealStage.CLOSED_WON,
        "forecast_category": ForecastCategory.CLOSED,
        "amount": 36000.0,
        "expected_close_days": -10,
        "description": "Closed annual subscription for yield forecasting.",
        "last_activity_days": 8,
    },
    {
        "id": "seed-deal-atlas-tutoring",
        "name": "Atlas tutoring marketplace analytics",
        "company_id": "seed-atlas-education",
        "contact_id": "seed-contact-atlas-founder",
        "stage": DealStage.CLOSED_LOST,
        "forecast_category": ForecastCategory.OMITTED,
        "amount": 18000.0,
        "expected_close_days": -30,
        "description": "No budget this fiscal year; revisit next year.",
        "last_activity_days": 21,
    },
]

DEMO_ACTIVITIES = [
    {
        "id": "seed-act-northstar-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Forecasting rollout next steps",
        "body": (
            "Hi Alex, thanks for the demo. Our COO is interested in the "
            "forecasting workflow, but we need security review and a clear "
            "implementation timeline before we can commit budget. Can you send "
            "the SOC 2 report and a two-quarter rollout plan?"
        ),
        "days_ago": 2,
        "company_id": COMPANY_ID,
        "contact_id": CONTACT_ID,
        "deal_id": DEAL_ID,
    },
    {
        "id": "seed-act-brightwave-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Reducing claims processing time",
        "body": (
            "Hi Alex, we are evaluating vendors to cut claims processing time "
            "by 30%. We have budget approved for this quarter and the COO is "
            "the decision maker. The main concern is integration with our "
            "existing Epic instance. Can you support HL7 feeds?"
        ),
        "days_ago": 4,
        "company_id": "seed-brightwave-health",
        "contact_id": "seed-contact-brightwave-coo",
        "deal_id": None,
    },
    {
        "id": "seed-act-cedarline-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Shipment visibility pilot",
        "body": (
            "Thanks for the follow-up. Our VP of Ops likes the pilot scope, but "
            "procurement needs three competitive quotes before we can move "
            "forward. Timeline is early next quarter."
        ),
        "days_ago": 6,
        "company_id": "seed-cedarline-logistics",
        "contact_id": "seed-contact-cedarline-vpops",
        "deal_id": "seed-deal-cedarline-visibility",
    },
    {
        "id": "seed-act-quantumforge-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Defect prediction demo",
        "body": (
            "The demo was well received. Finance has approved the budget and we "
            "want to start with three production lines. Please confirm the "
            "implementation cost and the data residency options."
        ),
        "days_ago": 2,
        "company_id": "seed-quantumforge",
        "contact_id": "seed-contact-quantumforge-cfo",
        "deal_id": "seed-deal-quantumforge-quality",
    },
    {
        "id": "seed-act-lumen-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Treasury automation",
        "body": (
            "We have decided to stay with our incumbent vendor for now. Price "
            "was the deciding factor. Please check back in nine months when the "
            "contract is up for renewal."
        ),
        "days_ago": 12,
        "company_id": "seed-lumen-financial",
        "contact_id": "seed-contact-lumen-headops",
        "deal_id": "seed-deal-lumen-treasury",
    },
    {
        "id": "seed-act-greenfield-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Yield forecasting subscription",
        "body": (
            "We are ready to sign the annual subscription. Please send the "
            "order form and invoice. Our board wants to see results by harvest "
            "season."
        ),
        "days_ago": 8,
        "company_id": "seed-greenfield-agrotech",
        "contact_id": "seed-contact-greenfield-founder",
        "deal_id": "seed-deal-greenfield-yield",
    },
    {
        "id": "seed-act-orbital-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Mission operations analytics",
        "body": (
            "Our CTO and procurement lead are aligned on the two-mission "
            "rollout. We need the final security questionnaire and a firm "
            "delivery date before contract signature."
        ),
        "days_ago": 2,
        "company_id": "seed-orbital-systems",
        "contact_id": "seed-contact-orbital-cto",
        "deal_id": "seed-deal-orbital-rollout",
    },
    {
        "id": "seed-act-pulse-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Audience segmentation",
        "body": (
            "Interesting approach. We would need to prove incremental ad revenue "
            "in a pilot before committing. Our data team is small, so "
            "implementation effort matters."
        ),
        "days_ago": 5,
        "company_id": "seed-pulse-media",
        "contact_id": "seed-contact-pulse-headrev",
        "deal_id": "seed-deal-pulse-monetization",
    },
    {
        "id": "seed-act-tessellate-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Platform pilot",
        "body": (
            "We raised our seed round and are moving fast. The pilot looks "
            "great; can we start next week? Our CTO wants to validate latency "
            "and cost per million vectors."
        ),
        "days_ago": 1,
        "company_id": "seed-tessellate-ai",
        "contact_id": "seed-contact-tessellate-founder",
        "deal_id": "seed-deal-tessellate-platform",
    },
    {
        "id": "seed-act-harborview-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Annual renewal",
        "body": (
            "Legal is reviewing the renewal. We want to add two store cohorts "
            "and need the updated pricing by Friday. Overall we are happy with "
            "the platform."
        ),
        "days_ago": 3,
        "company_id": "seed-harborview-retail",
        "contact_id": "seed-contact-harborview-coo",
        "deal_id": "seed-deal-harborview-renewal",
    },
    {
        "id": "seed-act-ironclad-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: MDR partnership",
        "body": (
            "We are exploring partnerships for our MDR offering. Not ready to "
            "buy yet, but interested in a technical overview and co-selling "
            "model."
        ),
        "days_ago": 7,
        "company_id": "seed-ironclad-security",
        "contact_id": "seed-contact-ironclad-cio",
        "deal_id": None,
    },
    {
        "id": "seed-act-verde-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Storage portfolio analytics",
        "body": (
            "The executive team approved the business case. Procurement needs "
            "the final MSA and a delivery schedule for the first two sites. "
            "Target signature is end of month."
        ),
        "days_ago": 1,
        "company_id": "seed-verde-energy",
        "contact_id": "seed-contact-verde-coo",
        "deal_id": "seed-deal-verde-storage",
    },
    {
        "id": "seed-act-atlas-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Marketplace analytics",
        "body": (
            "Thanks for the proposal. We do not have budget this fiscal year "
            "and our team is too small to implement right now. Please follow up "
            "next year."
        ),
        "days_ago": 21,
        "company_id": "seed-atlas-education",
        "contact_id": "seed-contact-atlas-founder",
        "deal_id": "seed-deal-atlas-tutoring",
    },
    {
        "id": "seed-act-copperleaf-email",
        "type": ActivityType.EMAIL,
        "subject": "Re: Revenue management rollout",
        "body": (
            "We are opening two destination properties next quarter. The GM "
            "loves the revenue management demo. We need a phased rollout plan "
            "and training for the front-desk teams."
        ),
        "days_ago": 5,
        "company_id": "seed-copperleaf-hospitality",
        "contact_id": "seed-contact-copperleaf-gm",
        "deal_id": "seed-deal-copperleaf-expansion",
    },
    {
        "id": "seed-act-orbital-call",
        "type": ActivityType.CALL,
        "subject": "Technical validation call",
        "body": (
            "Reviewed data residency, SSO, and API limits with Sam and Nadia. "
            "No blockers; next step is the security questionnaire."
        ),
        "days_ago": 3,
        "company_id": "seed-orbital-systems",
        "contact_id": "seed-contact-orbital-cto",
        "deal_id": "seed-deal-orbital-rollout",
    },
    {
        "id": "seed-act-verde-meeting",
        "type": ActivityType.MEETING,
        "subject": "Executive business case review",
        "body": (
            "Presented the storage analytics business case to the COO and "
            "procurement. Approved to proceed to contracting."
        ),
        "days_ago": 4,
        "company_id": "seed-verde-energy",
        "contact_id": "seed-contact-verde-coo",
        "deal_id": "seed-deal-verde-storage",
    },
]

DEMO_THREADS = [
    {
        "root_message_id": "seed-thread-northstar-forecasting",
        "subject": "Re: Forecasting rollout next steps",
        "company_id": COMPANY_ID,
        "contact_id": CONTACT_ID,
        "message_count": 3,
        "first_days_ago": 9,
        "last_days_ago": 2,
    },
    {
        "root_message_id": "seed-thread-brightwave-claims",
        "subject": "Re: Reducing claims processing time",
        "company_id": "seed-brightwave-health",
        "contact_id": "seed-contact-brightwave-coo",
        "message_count": 2,
        "first_days_ago": 8,
        "last_days_ago": 4,
    },
    {
        "root_message_id": "seed-thread-cedarline-visibility",
        "subject": "Re: Shipment visibility pilot",
        "company_id": "seed-cedarline-logistics",
        "contact_id": "seed-contact-cedarline-vpops",
        "message_count": 4,
        "first_days_ago": 14,
        "last_days_ago": 6,
    },
    {
        "root_message_id": "seed-thread-quantumforge-demo",
        "subject": "Re: Defect prediction demo",
        "company_id": "seed-quantumforge",
        "contact_id": "seed-contact-quantumforge-cfo",
        "message_count": 3,
        "first_days_ago": 10,
        "last_days_ago": 2,
    },
    {
        "root_message_id": "seed-thread-lumen-treasury",
        "subject": "Re: Treasury automation",
        "company_id": "seed-lumen-financial",
        "contact_id": "seed-contact-lumen-headops",
        "message_count": 5,
        "first_days_ago": 30,
        "last_days_ago": 12,
    },
    {
        "root_message_id": "seed-thread-greenfield-yield",
        "subject": "Re: Yield forecasting subscription",
        "company_id": "seed-greenfield-agrotech",
        "contact_id": "seed-contact-greenfield-founder",
        "message_count": 2,
        "first_days_ago": 15,
        "last_days_ago": 8,
    },
    {
        "root_message_id": "seed-thread-orbital-analytics",
        "subject": "Re: Mission operations analytics",
        "company_id": "seed-orbital-systems",
        "contact_id": "seed-contact-orbital-cto",
        "message_count": 6,
        "first_days_ago": 20,
        "last_days_ago": 2,
    },
    {
        "root_message_id": "seed-thread-pulse-segmentation",
        "subject": "Re: Audience segmentation",
        "company_id": "seed-pulse-media",
        "contact_id": "seed-contact-pulse-headrev",
        "message_count": 3,
        "first_days_ago": 12,
        "last_days_ago": 5,
    },
    {
        "root_message_id": "seed-thread-tessellate-pilot",
        "subject": "Re: Platform pilot",
        "company_id": "seed-tessellate-ai",
        "contact_id": "seed-contact-tessellate-founder",
        "message_count": 2,
        "first_days_ago": 4,
        "last_days_ago": 1,
    },
    {
        "root_message_id": "seed-thread-harborview-renewal",
        "subject": "Re: Annual renewal",
        "company_id": "seed-harborview-retail",
        "contact_id": "seed-contact-harborview-coo",
        "message_count": 4,
        "first_days_ago": 10,
        "last_days_ago": 3,
    },
    {
        "root_message_id": "seed-thread-verde-storage",
        "subject": "Re: Storage portfolio analytics",
        "company_id": "seed-verde-energy",
        "contact_id": "seed-contact-verde-coo",
        "message_count": 7,
        "first_days_ago": 25,
        "last_days_ago": 1,
    },
    {
        "root_message_id": "seed-thread-atlas-marketplace",
        "subject": "Re: Marketplace analytics",
        "company_id": "seed-atlas-education",
        "contact_id": "seed-contact-atlas-founder",
        "message_count": 2,
        "first_days_ago": 40,
        "last_days_ago": 21,
    },
]


async def ensure_demo_data(session, admin_id):
    """Insert the demo CRM dataset idempotently (safe to re-run)."""
    now = datetime.utcnow()

    for spec in DEMO_COMPANIES:
        if await session.get(Company, spec["id"]) is not None:
            continue
        data = dict(spec)
        band = data.pop("employee_band", None)
        days = data.pop("last_activity_days", None)
        session.add(
            Company(
                owner_id=admin_id,
                record_source=RecordSource.IMPORT,
                enrichment_status=EnrichmentStatus.COMPLETE,
                enriched_at=now,
                last_activity_at=(
                    now - timedelta(days=days) if days is not None else None
                ),
                custom_fields={"employee_band": band} if band else {},
                **data,
            )
        )
    await session.flush()

    for spec in DEMO_CONTACTS:
        if await session.get(Contact, spec["id"]) is not None:
            continue
        data = dict(spec)
        days = data.pop("last_activity_days", None)
        session.add(
            Contact(
                owner_id=admin_id,
                record_source=RecordSource.IMPORT,
                enrichment_status=EnrichmentStatus.COMPLETE,
                enriched_at=now,
                last_activity_at=(
                    now - timedelta(days=days) if days is not None else None
                ),
                **data,
            )
        )
    await session.flush()

    for company_id, contact_id in DEMO_PRIMARY_CONTACTS.items():
        company = await session.get(Company, company_id)
        if company is not None and not company.primary_contact_id:
            company.primary_contact_id = contact_id
    await session.flush()

    for spec in DEMO_DEALS:
        if await session.get(Deal, spec["id"]) is not None:
            continue
        data = dict(spec)
        contact_id = data.pop("contact_id", None)
        days = data.pop("last_activity_days", None)
        close_days = data.pop("expected_close_days", 45)
        session.add(
            Deal(
                owner_id=admin_id,
                record_source=RecordSource.IMPORT,
                expected_close_date=now + timedelta(days=close_days),
                last_activity_at=(
                    now - timedelta(days=days) if days is not None else None
                ),
                **data,
            )
        )
        await session.flush()
        if (
            contact_id
            and await session.get(DealContact, (spec["id"], contact_id))
            is None
        ):
            session.add(
                DealContact(
                    deal_id=spec["id"],
                    contact_id=contact_id,
                    role="Economic buyer",
                    is_primary_contact=True,
                )
            )

    for spec in DEMO_ACTIVITIES:
        if await session.get(Activity, spec["id"]) is not None:
            continue
        data = dict(spec)
        days = data.pop("days_ago", 3)
        session.add(
            Activity(
                created_by_id=admin_id,
                occurred_at=now - timedelta(days=days),
                **data,
            )
        )

    for spec in DEMO_THREADS:
        existing = await session.scalar(
            select(EmailThread).where(
                EmailThread.root_message_id == spec["root_message_id"]
            )
        )
        if existing is not None:
            continue
        data = dict(spec)
        first = data.pop("first_days_ago", 10)
        last = data.pop("last_days_ago", 3)
        session.add(
            EmailThread(
                first_message_at=now - timedelta(days=first),
                last_message_at=now - timedelta(days=last),
                **data,
            )
        )

    await session.commit()


async def ensure_module_demo_data(session, admin_id):
    now = datetime.utcnow()
    company_id = await session.scalar(select(Company.id).limit(1)) or COMPANY_ID

    for spec in [
        {"id": "seed-attendance-today", "date": now.replace(hour=0, minute=0, second=0, microsecond=0), "hours": 8.0, "status": "present"},
        {"id": "seed-attendance-yesterday", "date": now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1), "hours": 8.0, "status": "remote"},
        {"id": "seed-attendance-two-days", "date": now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=2), "hours": 7.5, "status": "present"},
    ]:
        if await session.get(Attendance, spec["id"]) is None:
            session.add(Attendance(user_id=admin_id, **spec))

    for spec in [
        {"id": "seed-leave-requested", "type": "vacation", "start_date": now + timedelta(days=10), "end_date": now + timedelta(days=14), "days": 5, "status": "requested", "reason": "Family trip"},
        {"id": "seed-leave-approved", "type": "sick", "start_date": now - timedelta(days=7), "end_date": now - timedelta(days=6), "days": 2, "status": "approved", "reason": "Recovery"},
    ]:
        if await session.get(LeaveRequest, spec["id"]) is None:
            session.add(LeaveRequest(user_id=admin_id, **spec))

    for spec in [
        {"id": "seed-ticket-onboarding", "subject": "Onboarding checklist for Northstar", "description": "Customer needs help importing contacts.", "status": "open", "priority": "high"},
        {"id": "seed-ticket-billing", "subject": "Invoice copy request", "description": "Finance team requested a duplicate invoice.", "status": "pending", "priority": "medium"},
        {"id": "seed-ticket-resolved", "subject": "Login issue resolved", "description": "Password reset completed.", "status": "resolved", "priority": "low"},
    ]:
        if await session.get(SupportTicket, spec["id"]) is None:
            session.add(SupportTicket(company_id=company_id, **spec))

    for spec in [
        {"id": "seed-invoice-001", "number": "INV-0001", "amount": 72000.0, "currency": "USD", "status": "open", "due_date": now + timedelta(days=30)},
        {"id": "seed-invoice-002", "number": "INV-0002", "amount": 18500.0, "currency": "USD", "status": "paid", "due_date": now - timedelta(days=5)},
    ]:
        if await session.get(Invoice, spec["id"]) is None:
            session.add(Invoice(company_id=company_id, **spec))

    for spec in [
        {"id": "seed-expense-travel", "category": "Travel", "amount": 1240.0, "currency": "USD", "status": "approved", "date": now - timedelta(days=3)},
        {"id": "seed-expense-software", "category": "Software", "amount": 890.0, "currency": "USD", "status": "submitted", "date": now - timedelta(days=1)},
    ]:
        if await session.get(Expense, spec["id"]) is None:
            session.add(Expense(user_id=admin_id, **spec))

    for spec in [
        {"id": "seed-asset-laptop", "name": "MacBook Pro 16", "type": "Laptop", "status": "active"},
        {"id": "seed-asset-license", "name": "Analytics platform license", "type": "Software", "status": "active"},
        {"id": "seed-asset-vehicle", "name": "Field vehicle", "type": "Vehicle", "status": "maintenance"},
    ]:
        if await session.get(Asset, spec["id"]) is None:
            session.add(Asset(**spec))

    for spec in [
        {"id": "seed-request-onboarding", "title": "Set up new hire workspace", "status": "open"},
        {"id": "seed-request-audit", "title": "Quarterly asset audit", "status": "in_progress"},
    ]:
        if await session.get(WorkRequest, spec["id"]) is None:
            session.add(WorkRequest(**spec))

    await session.commit()


async def seed():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        existing = await session.scalar(select(User).where(User.email == "admin@agentic-crm.local"))
        if existing:
            if not existing.password_hash:
                existing.password_hash = AuthService.hash_password("password123")
                await session.commit()
            await ensure_departments(session, existing.id)
            await ensure_agents(session, existing.id)
            await ensure_demo_data(session, existing.id)
            await ensure_campaigns(session, existing.id)
            await ensure_email_messages(session, existing.id)
            await ensure_module_demo_data(session, existing.id)
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
        await ensure_departments(session, ADMIN_ID)
        await ensure_agents(session, ADMIN_ID)
        await ensure_demo_data(session, ADMIN_ID)
        await ensure_campaigns(session, ADMIN_ID)
        await ensure_email_messages(session, ADMIN_ID)
        await ensure_module_demo_data(session, ADMIN_ID)
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
