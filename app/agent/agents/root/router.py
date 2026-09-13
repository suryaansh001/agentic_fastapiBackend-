from fastapi import APIRouter, Depends
from typing import Optional
from app.dependencies.auth import get_current_user, CurrentUser
from app.agent.agents.root.tools import (
    CRMService, SearchCRMInput, SearchCRMResult, ReadCRMHistoryInput,
    ResearchCompanyInput, ResearchPersonInput, IdentifyContactInput,
    ListDealsInput, ScheduleRecheckInput, ListOutstandingWorkInput,
    SetFieldValueInput, RecordFactInput, WriteBriefInput,
    WriteWorkspaceProfileInput, EnrichCompanyInput, FetchContactPhotoInput,
    ArchiveFieldInput, ManageFieldsInput, RecordJobChangeInput,
    SetChatTitleInput, ResolveLinkedInProfileInput, FindContactSocialsInput,
    SetContactSocialsInput, GetContactWorkHistoryInput, GetLinkedInProfileInput,
    ListFieldsInput,
)

router = APIRouter(prefix="/api/agents/root", tags=["root-agent"])
svc = CRMService()


@router.post("/search_crm", response_model=SearchCRMResult)
async def search_crm(input_data: SearchCRMInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.search_crm(input_data)


@router.post("/read_crm_history")
async def read_crm_history(input_data: ReadCRMHistoryInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.read_crm_history(input_data)


@router.post("/read_company_history")
async def read_company_history(company_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.read_company_history(company_id)


@router.post("/read_deal_history")
async def read_deal_history(deal_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.read_deal_history(deal_id)


@router.post("/research_person")
async def research_person(input_data: ResearchPersonInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.research_person(input_data)


@router.post("/research_company")
async def research_company(input_data: ResearchCompanyInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.research_company(input_data)


@router.post("/identify_contact")
async def identify_contact(input_data: IdentifyContactInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.identify_contact(input_data)


@router.post("/find_contact_socials")
async def find_contact_socials(input_data: FindContactSocialsInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.find_contact_socials(input_data)


@router.post("/set_contact_socials")
async def set_contact_socials(input_data: SetContactSocialsInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.set_contact_socials(input_data)


@router.post("/resolve_linkedin_profile")
async def resolve_linkedin_profile(input_data: ResolveLinkedInProfileInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.resolve_linkedin_profile(input_data)


@router.post("/get_contact_work_history")
async def get_contact_work_history(input_data: GetContactWorkHistoryInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.get_contact_work_history(input_data)


@router.post("/get_linkedin_profile")
async def get_linkedin_profile(input_data: GetLinkedInProfileInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.get_linkedin_profile(input_data)


@router.post("/list_deals")
async def list_deals(input_data: ListDealsInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.list_deals(input_data)


@router.post("/list_fields")
async def list_fields(input_data: ListFieldsInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.list_fields(input_data)


@router.post("/list_outstanding_work")
async def list_outstanding_work(input_data: ListOutstandingWorkInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.list_outstanding_work(input_data)


@router.post("/manage_fields")
async def manage_fields(input_data: ManageFieldsInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.manage_fields(input_data)


@router.post("/set_field_value")
async def set_field_value(input_data: SetFieldValueInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.set_field_value(input_data)


@router.post("/archive_field")
async def archive_field(input_data: ArchiveFieldInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.archive_field(input_data)


@router.post("/record_fact")
async def record_fact(input_data: RecordFactInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.record_fact(input_data)


@router.post("/record_job_change")
async def record_job_change(input_data: RecordJobChangeInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.record_job_change(input_data)


@router.post("/write_brief")
async def write_brief(input_data: WriteBriefInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.write_brief(input_data)


@router.post("/write_workspace_profile")
async def write_workspace_profile(input_data: WriteWorkspaceProfileInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.write_workspace_profile(input_data)


@router.post("/enrich_company")
async def enrich_company(input_data: EnrichCompanyInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.enrich_company(input_data)


@router.post("/fetch_contact_photo")
async def fetch_contact_photo(input_data: FetchContactPhotoInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.fetch_contact_photo(input_data)


@router.post("/schedule_recheck")
async def schedule_recheck(input_data: ScheduleRecheckInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.schedule_recheck(input_data)


@router.post("/set_chat_title")
async def set_chat_title(input_data: SetChatTitleInput, current_user: CurrentUser = Depends(get_current_user)):
    return await svc.set_chat_title(input_data)