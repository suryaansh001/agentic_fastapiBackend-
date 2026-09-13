from typing import Optional
from pydantic import BaseModel, Field
from typing import List, Dict


class BashInput(BaseModel):
    command: str
    timeout: Optional[int] = None


class AskQuestionInput(BaseModel):
    question: str
    options: Optional[list[str]] = None


class CreateCrmActivityInput(BaseModel):
    contactId: Optional[str] = None
    companyId: Optional[str] = None
    type: str
    body: str


class FinishRunInput(BaseModel):
    runId: str
    summary: str
    result: Optional[dict] = None


class InspectRunInput(BaseModel):
    runId: str


class PostSlackMessageInput(BaseModel):
    channel: str
    message: str


class QueryCRMInput(BaseModel):
    query: str


class ReadCRMRecordInput(BaseModel):
    recordId: str
    kind: str


class ReadFileInput(BaseModel):
    path: str


class TodoInput(BaseModel):
    action: str
    text: Optional[str] = None


class WebFetchInput(BaseModel):
    url: str


class WebSearchInput(BaseModel):
    query: str


class WriteFileInput(BaseModel):
    path: str
    content: str


class RunnerAgentTools:
    def ask_question(self, input_data: AskQuestionInput) -> dict:
        return {"question": input_data.question, "options": input_data.options or []}

    def bash(self, command: str) -> dict:
        return {"output": f"Executed: {command}"}

    def create_crm_activity(self, input_data: CreateCrmActivityInput) -> dict:
        return {"activityId": "activity_123"}

    def finish_run(self, input_data: FinishRunInput) -> dict:
        return {"finished": True, "runId": input_data.runId}

    def glob(self, pattern: str) -> dict:
        return {"files": []}

    def grep(self, pattern: str, path: Optional[str] = None) -> dict:
        return {"matches": []}

    def inspect_run(self, input_data: InspectRunInput) -> dict:
        return {"runId": input_data.runId, "status": "COMPLETED"}

    def post_slack_message(self, input_data: PostSlackMessageInput) -> dict:
        return {"posted": True, "channel": input_data.channel}

    def query_crm(self, input_data: QueryCRMInput) -> dict:
        return {"results": []}

    def read_crm_record(self, input_data: ReadCRMRecordInput) -> dict:
        return {"record": {"id": input_data.recordId, "kind": input_data.kind}}

    def read_file(self, input_data: ReadFileInput) -> dict:
        return {"content": ""}

    def todo(self, input_data: TodoInput) -> dict:
        return {"todo": input_data.text or input_data.action}

    def web_fetch(self, input_data: WebFetchInput) -> dict:
        return {"content": ""}

    def web_search(self, input_data: WebSearchInput) -> dict:
        return {"results": []}

    def write_file(self, input_data: WriteFileInput) -> dict:
        return {"written": True, "path": input_data.path}