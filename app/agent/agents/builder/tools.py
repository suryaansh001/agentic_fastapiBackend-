from typing import Optional
from pydantic import BaseModel, Field
from typing import List, Dict


class BashInput(BaseModel):
    command: str
    timeout: Optional[int] = None


class GlobInput(BaseModel):
    pattern: str


class GrepInput(BaseModel):
    pattern: str
    path: Optional[str] = None


class ReadFileInput(BaseModel):
    path: str
    offset: Optional[int] = None
    limit: Optional[int] = None


class WriteFileInput(BaseModel):
    path: str
    content: str


class TodoInput(BaseModel):
    action: str
    text: Optional[str] = None


class WebFetchInput(BaseModel):
    url: str


class WebSearchInput(BaseModel):
    query: str


class SaveAgentDraftInput(BaseModel):
    versionId: str
    summary: str


class InspectContextInput(BaseModel):
    key: str


class WriteAgentFileInput(BaseModel):
    path: str
    content: str
    language: Optional[str] = None


class BuilderAgentTools:
    def bash(self, input_data: BashInput) -> dict:
        return {"output": f"Executed: {input_data.command}"}

    def glob(self, input_data: GlobInput) -> dict:
        return {"files": []}

    def grep(self, input_data: GrepInput) -> dict:
        return {"matches": []}

    def read_file(self, input_data: ReadFileInput) -> dict:
        return {"content": ""}

    def write_file(self, input_data: WriteFileInput) -> dict:
        return {"written": True}

    def todo(self, input_data: TodoInput) -> dict:
        return {"todo": input_data.text or input_data.action}

    def web_fetch(self, input_data: WebFetchInput) -> dict:
        return {"content": ""}

    def web_search(self, input_data: WebSearchInput) -> dict:
        return {"results": []}

    def save_agent_draft(self, input_data: SaveAgentDraftInput) -> dict:
        return {"saved": True, "versionId": input_data.versionId}

    def inspect_context(self, input_data: InspectContextInput) -> dict:
        return {"key": input_data.key, "value": None}

    def write_agent_file(self, input_data: WriteAgentFileInput) -> dict:
        return {"written": True, "path": input_data.path}