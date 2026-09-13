from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.agent.agents.runner.tools import RunnerAgentTools
from app.agent.agents.runner.tools import (
    AskQuestionInput, CreateCrmActivityInput, FinishRunInput,
    InspectRunInput, PostSlackMessageInput, QueryCRMInput,
    ReadCRMRecordInput, ReadFileInput, TodoInput, WebFetchInput,
    WebSearchInput, WriteFileInput, BashInput,
)

router = APIRouter(prefix="/api/agents/runner", tags=["runner-agent"])
tools = RunnerAgentTools()


@router.post("/ask_question")
def ask_question(input_data: AskQuestionInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.ask_question(input_data)


@router.post("/bash")
def bash(input_data: BashInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.bash(input_data.command)


@router.post("/create_crm_activity")
def create_crm_activity(input_data: CreateCrmActivityInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.create_crm_activity(input_data)


@router.post("/finish_run")
def finish_run(input_data: FinishRunInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.finish_run(input_data)


@router.post("/glob")
def glob(pattern: str = "", current_user: CurrentUser = Depends(get_current_user)):
    return tools.glob(pattern)


@router.post("/grep")
def grep(pattern: str, path: str = None, current_user: CurrentUser = Depends(get_current_user)):
    return tools.grep(pattern, path)


@router.post("/inspect_run")
def inspect_run(input_data: InspectRunInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.inspect_run(input_data)


@router.post("/post_slack_message")
def post_slack_message(input_data: PostSlackMessageInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.post_slack_message(input_data)


@router.post("/query_crm")
def query_crm(input_data: QueryCRMInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.query_crm(input_data)


@router.post("/read_crm_record")
def read_crm_record(input_data: ReadCRMRecordInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.read_crm_record(input_data)


@router.post("/read_file")
def read_file(input_data: ReadFileInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.read_file(input_data)


@router.post("/todo")
def todo(input_data: TodoInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.todo(input_data)


@router.post("/web_fetch")
def web_fetch(input_data: WebFetchInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.web_fetch(input_data)


@router.post("/web_search")
def web_search(input_data: WebSearchInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.web_search(input_data)


@router.post("/write_file")
def write_file(input_data: WriteFileInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.write_file(input_data)