from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, CurrentUser
from app.agent.agents.builder.tools import BuilderAgentTools
from app.agent.agents.builder.tools import (
    BashInput, GlobInput, GrepInput, ReadFileInput, WriteFileInput,
    TodoInput, WebFetchInput, WebSearchInput, SaveAgentDraftInput,
    InspectContextInput, WriteAgentFileInput,
)

router = APIRouter(prefix="/api/agents/builder", tags=["builder-agent"])
tools = BuilderAgentTools()


@router.post("/bash")
def bash(input_data: BashInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.bash(input_data)


@router.post("/glob")
def glob(input_data: GlobInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.glob(input_data)


@router.post("/grep")
def grep(input_data: GrepInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.grep(input_data)


@router.post("/read_file")
def read_file(input_data: ReadFileInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.read_file(input_data)


@router.post("/write_file")
def write_file(input_data: WriteFileInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.write_file(input_data)


@router.post("/todo")
def todo(input_data: TodoInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.todo(input_data)


@router.post("/web_fetch")
def web_fetch(input_data: WebFetchInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.web_fetch(input_data)


@router.post("/web_search")
def web_search(input_data: WebSearchInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.web_search(input_data)


@router.post("/save_agent_draft")
def save_agent_draft(input_data: SaveAgentDraftInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.save_agent_draft(input_data)


@router.post("/inspect_context")
def inspect_context(input_data: InspectContextInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.inspect_context(input_data)


@router.post("/write_agent_file")
def write_agent_file(input_data: WriteAgentFileInput, current_user: CurrentUser = Depends(get_current_user)):
    return tools.write_agent_file(input_data)