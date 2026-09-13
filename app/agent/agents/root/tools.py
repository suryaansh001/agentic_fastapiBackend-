from typing import Optional
from typing import Any
from pydantic import BaseModel, Field
from app.database.session import async_session_factory
from app.database.models import Contact, Company, Deal
from sqlalchemy import select, func, or_
import httpx
import asyncio


class SearchCRMInput(BaseModel):
    query: str = Field(..., min_length=2)
    kinds: Optional[list[str]] = None
    limit: int = Field(10, ge=1, le=25)


class SearchCRMResult(BaseModel):
    query: str
    contacts: list[dict] = []
    companies: list[dict] = []
    deals: list[dict] = []
    total: int = 0
    note: Optional[str] = None


class ReadCRMHistoryInput(BaseModel):
    contactId: str
    threads: int = Field(5, ge=1, le=20)


class ResearchCompanyInput(BaseModel):
    companyId: str


class ResearchPersonInput(BaseModel):
    question: str
    deep: bool = False


class IdentifyContactInput(BaseModel):
    contactId: str
    fullName: str
    evidence: list[dict]
    sourceUrl: str


class ListDealsInput(BaseModel):
    status: str = "open"
    inactiveForDays: Optional[int] = None
    companyId: Optional[str] = None
    ownerId: Optional[str] = None
    limit: int = Field(50, ge=1, le=100)
    cursor: Optional[str] = None


class ScheduleRecheckInput(BaseModel):
    contactId: str
    days: int = Field(14, ge=1, le=730)
    reason: str
    budget: int = Field(4, ge=1, le=20)


class ListOutstandingWorkInput(BaseModel):
    limit: int = Field(10, ge=1, le=25)


class SetFieldValueInput(BaseModel):
    contactId: Optional[str] = None
    fieldId: str
    value: str


class RecordFactInput(BaseModel):
    contactId: str
    field: str
    value: str
    evidence: list[dict]


class WriteBriefInput(BaseModel):
    contactId: str
    narrative: str
    sections: Optional[dict] = None
    evidence: Optional[list[dict]] = None
    sourceUrl: Optional[str] = None


class WriteWorkspaceProfileInput(BaseModel):
    website: str
    narrative: str
    sections: Optional[dict] = None


class EnrichCompanyInput(BaseModel):
    companyId: str


class FetchContactPhotoInput(BaseModel):
    contactId: str


class ArchiveFieldInput(BaseModel):
    fieldId: str
    reason: str


class ManageFieldsInput(BaseModel):
    entity: str
    fields: list[dict]


class RecordJobChangeInput(BaseModel):
    contactId: str
    newRole: str
    evidence: list[dict]


class SetChatTitleInput(BaseModel):
    conversationId: str
    title: str


class ResolveLinkedInProfileInput(BaseModel):
    contactId: str
    profileUrl: str


class FindContactSocialsInput(BaseModel):
    contactId: str


class SetContactSocialsInput(BaseModel):
    contactId: str
    xUrl: Optional[str] = None
    githubUrl: Optional[str] = None


class GetContactWorkHistoryInput(BaseModel):
    contactId: str


class GetLinkedInProfileInput(BaseModel):
    profileUrl: str


class ListFieldsInput(BaseModel):
    entity: Optional[str] = None


class CRMService:
    async def search_crm(self, input_data: SearchCRMInput) -> SearchCRMResult:
        query = input_data.query.strip()
        kinds = input_data.kinds or ["contact", "company", "deal"]
        limit = input_data.limit
        if len(query) < 2:
            return SearchCRMResult(query=query, total=0, note="Query too short")
        words = query.split()
        email = query.lower() if "@" in query else None
        async with async_session_factory() as session:
            contacts_result = []
            companies_result = []
            deals_result = []
            if "contact" in kinds:
                cond = or_(
                    Contact.first_name.like(f"%{query}%"),
                    Contact.last_name.like(f"%{query}%"),
                    Contact.email.like(f"%{query}%"),
                )
                if email:
                    cond = or_(cond, Contact.email.ilike(f"%{email}%"))
                result = await session.execute(
                    select(Contact).where(cond).limit(limit * 3)
                )
                for c in result.scalars().all():
                    contacts_result.append({
                        "id": c.id, "name": f"{c.first_name} {c.last_name}",
                        "title": c.title, "email": c.email,
                        "company": {"id": c.company_id, "name": ""} if c.company_id else None,
                        "lastActivityAt": c.last_activity_at.isoformat() if c.last_activity_at else None,
                    })
                contacts_result = contacts_result[:limit]
            if "company" in kinds:
                result = await session.execute(
                    select(Company).where(
                        or_(
                            Company.name.like(f"%{query}%"),
                            Company.domain.like(f"%{query}%"),
                        )
                    ).limit(limit * 3)
                )
                for comp in result.scalars().all():
                    companies_result.append({
                        "id": comp.id, "name": comp.name,
                        "domain": comp.domain, "industry": comp.industry,
                        "contacts": 0, "deals": 0,
                    })
                companies_result = companies_result[:limit]
            if "deal" in kinds:
                result = await session.execute(
                    select(Deal).where(
                        or_(
                            Deal.name.like(f"%{query}%"),
                        )
                    ).limit(limit * 3)
                )
                for d in result.scalars().all():
                    deals_result.append({
                        "id": d.id, "name": d.name, "stage": d.stage,
                        "amount": d.amount, "currency": d.currency,
                        "company": {"id": d.company_id, "name": ""} if d.company_id else None,
                    })
                deals_result = deals_result[:limit]
            total = len(contacts_result) + len(companies_result) + len(deals_result)
        return SearchCRMResult(
            query=query, contacts=contacts_result, companies=companies_result,
            deals=deals_result, total=total,
            note="Nothing found" if total == 0 else None,
        )

    async def read_crm_history(self, input_data: ReadCRMHistoryInput) -> dict:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Contact).where(Contact.id == input_data.contactId)
            )
            contact = result.scalar_one_or_none()
        if not contact:
            return {"found": False, "reason": "No such contact"}
        return {"found": True, "contact": {"id": contact.id}, "note": "History data"}

    async def list_deals(self, input_data: ListDealsInput) -> dict:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Deal).limit(input_data.limit)
            )
            deals = [{"id": d.id, "name": d.name, "stage": d.stage, "amount": d.amount} for d in result.scalars().all()]
        return {"deals": deals, "hasMore": False}

    async def research_person(self, input_data: ResearchPersonInput) -> dict:
        charge = 2 if input_data.deep else 1
        async with httpx.AsyncClient() as client:
            model = "sonar-pro" if input_data.deep else "sonar"
            url = "https://api.perplexity.ai/chat/completions"
            try:
                resp = await client.post(url, json={
                    "model": model,
                    "messages": [{"role": "user", "content": input_data.question}],
                    "max_tokens": 1000,
                }, headers={"Authorization": "Bearer dummy"}, timeout=30)
                if resp.status_code == 200:
                    return {"ok": True, "answer": "Research result", "citations": []}
                return {"ok": False, "reason": "Perplexity API unavailable"}
            except Exception:
                return {"ok": False, "reason": "Perplexity API unreachable"}

    async def research_company(self, input_data: ResearchCompanyInput) -> dict:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Company).where(Company.id == input_data.companyId)
            )
            company = result.scalar_one_or_none()
        if not company:
            return {"written": False, "reason": "No such company"}
        return {"written": True, "activityId": "activity_123"}

    async def identify_contact(self, input_data: IdentifyContactInput) -> dict:
        return {"applied": True, "band": "VERIFIED", "score": 0.95}

    async def schedule_recheck(self, input_data: ScheduleRecheckInput) -> dict:
        due_at = asyncio.get_event_loop().time() + input_data.days * 86400
        return {"scheduled": True, "dueAt": due_at, "reason": input_data.reason}

    async def list_outstanding_work(self, input_data: ListOutstandingWorkInput) -> dict:
        return {"count": 0, "contacts": []}

    async def write_brief(self, input_data: WriteBriefInput) -> dict:
        return {"written": True, "score": 0.9}

    async def set_field_value(self, input_data: SetFieldValueInput) -> dict:
        return {"set": True}

    async def record_fact(self, input_data: RecordFactInput) -> dict:
        return {"applied": True, "band": "PROPOSED"}

    async def write_workspace_profile(self, input_data: WriteWorkspaceProfileInput) -> dict:
        return {"written": True}

    async def enrich_company(self, input_data: EnrichCompanyInput) -> dict:
        return {"enriched": True}

    async def fetch_contact_photo(self, input_data: FetchContactPhotoInput) -> dict:
        return {"photoUrl": None}

    async def archive_field(self, input_data: ArchiveFieldInput) -> dict:
        return {"archived": True}

    async def manage_fields(self, input_data: ManageFieldsInput) -> dict:
        return {"managed": True}

    async def record_job_change(self, input_data: RecordJobChangeInput) -> dict:
        return {"recorded": True}

    async def set_chat_title(self, input_data: SetChatTitleInput) -> dict:
        return {"titleSet": True}

    async def resolve_linkedin_profile(self, input_data: ResolveLinkedInProfileInput) -> dict:
        return {"resolved": True}

    async def find_contact_socials(self, input_data: FindContactSocialsInput) -> dict:
        return {"searched": True, "candidates": {"x": [], "github": []}}

    async def set_contact_socials(self, input_data: SetContactSocialsInput) -> dict:
        return {"set": True}

    async def get_contact_work_history(self, input_data: GetContactWorkHistoryInput) -> dict:
        return {"found": True, "profile": {}}

    async def get_linkedin_profile(self, input_data: GetLinkedInProfileInput) -> dict:
        return {"profile": {}}

    async def list_fields(self, input_data: ListFieldsInput) -> dict:
        return {"fields": []}

    async def read_company_history(self, company_id: str) -> dict:
        return {"found": True, "company": {"id": company_id}}

    async def read_deal_history(self, deal_id: str) -> dict:
        return {"found": True, "deal": {"id": deal_id}}

class RootAgentTools:
    def __init__(self):
        self._svc = CRMService()

    async def search_crm(self, input_data: SearchCRMInput) -> dict:
        return await self._svc.search_crm(input_data)

    async def read_crm_history(self, input_data: ReadCRMHistoryInput) -> dict:
        return await self._svc.read_crm_history(input_data)

    async def read_company_history(self, company_id: str) -> dict:
        return await self._svc.read_company_history(company_id)

    async def read_deal_history(self, deal_id: str) -> dict:
        return await self._svc.read_deal_history(deal_id)

    async def research_person(self, input_data: ResearchPersonInput) -> dict:
        return await self._svc.research_person(input_data)

    async def research_company(self, input_data: ResearchCompanyInput) -> dict:
        return await self._svc.research_company(input_data)

    async def identify_contact(self, input_data: IdentifyContactInput) -> dict:
        return await self._svc.identify_contact(input_data)

    async def find_contact_socials(self, input_data: FindContactSocialsInput) -> dict:
        return await self._svc.find_contact_socials(input_data)

    async def set_contact_socials(self, input_data: SetContactSocialsInput) -> dict:
        return await self._svc.set_contact_socials(input_data)

    async def resolve_linkedin_profile(self, input_data: ResolveLinkedInProfileInput) -> dict:
        return await self._svc.resolve_linkedin_profile(input_data)

    async def get_contact_work_history(self, input_data: GetContactWorkHistoryInput) -> dict:
        return await self._svc.get_contact_work_history(input_data)

    async def get_linkedin_profile(self, input_data: GetLinkedInProfileInput) -> dict:
        return await self._svc.get_linkedin_profile(input_data)

    async def list_deals(self, input_data: ListDealsInput) -> dict:
        return await self._svc.list_deals(input_data)

    async def list_fields(self, input_data: ListFieldsInput) -> dict:
        return await self._svc.list_fields(input_data)

    async def list_outstanding_work(self, input_data: ListOutstandingWorkInput) -> dict:
        return await self._svc.list_outstanding_work(input_data)

    async def manage_fields(self, input_data: ManageFieldsInput) -> dict:
        return await self._svc.manage_fields(input_data)

    async def set_field_value(self, input_data: SetFieldValueInput) -> dict:
        return await self._svc.set_field_value(input_data)

    async def archive_field(self, input_data: ArchiveFieldInput) -> dict:
        return await self._svc.archive_field(input_data)

    async def record_fact(self, input_data: RecordFactInput) -> dict:
        return await self._svc.record_fact(input_data)

    async def record_job_change(self, input_data: RecordJobChangeInput) -> dict:
        return await self._svc.record_job_change(input_data)

    async def write_brief(self, input_data: WriteBriefInput) -> dict:
        return await self._svc.write_brief(input_data)

    async def write_workspace_profile(self, input_data: WriteWorkspaceProfileInput) -> dict:
        return await self._svc.write_workspace_profile(input_data)

    async def enrich_company(self, input_data: EnrichCompanyInput) -> dict:
        return await self._svc.enrich_company(input_data)

    async def fetch_contact_photo(self, input_data: FetchContactPhotoInput) -> dict:
        return await self._svc.fetch_contact_photo(input_data)

    async def schedule_recheck(self, input_data: ScheduleRecheckInput) -> dict:
        return await self._svc.schedule_recheck(input_data)

    async def set_chat_title(self, input_data: SetChatTitleInput) -> dict:
        return await self._svc.set_chat_title(input_data)