from typing import Optional, List

from app.agent.tools.crm_query import CrmQueryError, crm_query_service
from app.agent.tools.filesystem import (
    WorkspaceError,
    grep_workspace,
    list_workspace,
    read_text_file,
    write_text_file,
)
from app.agent.tools.web_fetch import WebFetchError, safe_fetch
from app.agent.tools.registry import (
    AskQuestionInput,
    CreateCrmActivityInput,
    FinishRunInput,
    InspectRunInput,
    PostSlackMessageInput,
    QueryCRMInput,
    ReadCRMRecordInput,
    ReadFileInput,
    TodoInput,
    WebFetchInput,
    WebSearchInput,
    WriteFileInput,
)


class RunnerAgentTools:
    """Safe runner tools.

    Removed from production (Phase 0): bash, execute_python, create_chart,
    generate_pdf — arbitrary code execution and LLM-authored code paths.
    Filesystem and web access are sandboxed; CRM access is allow-listed
    read-only queries. Tools are invoked by the agent execution engine via
    the canonical tool registry, never by direct HTTP endpoints.
    """

    def ask_question(self, input_data: AskQuestionInput) -> dict:
        return {"question": input_data.question, "options": input_data.options or []}

    async def query_crm(self, input_data: QueryCRMInput) -> dict:
        from app.database.session import async_session_factory
        try:
            async with async_session_factory() as session:
                result = await crm_query_service.execute(
                    session, input_data.operation, input_data.params
                )
                return {"success": True, **result}
        except CrmQueryError as e:
            return {"success": False, "error": str(e)}

    def create_crm_activity(self, input_data: CreateCrmActivityInput) -> dict:
        return {"activityId": "activity_123"}

    def finish_run(self, input_data: FinishRunInput) -> dict:
        return {"finished": True, "runId": input_data.runId}

    def glob(self, pattern: str) -> dict:
        try:
            return {"files": list_workspace(pattern), "success": True}
        except WorkspaceError as e:
            return {"success": False, "error": str(e)}

    def grep(self, pattern: str, path: Optional[str] = None) -> dict:
        try:
            return {"matches": grep_workspace(pattern, path), "success": True}
        except WorkspaceError as e:
            return {"success": False, "error": str(e)}

    def inspect_run(self, input_data: InspectRunInput) -> dict:
        return {"runId": input_data.runId, "status": "COMPLETED"}

    def post_slack_message(self, input_data: PostSlackMessageInput) -> dict:
        return {"posted": True, "channel": input_data.channel}

    def read_crm_record(self, input_data: ReadCRMRecordInput) -> dict:
        return {"record": {"id": input_data.recordId, "kind": input_data.kind}}

    def read_file(self, input_data: ReadFileInput) -> dict:
        try:
            return {"content": read_text_file(input_data.path), "success": True}
        except WorkspaceError as e:
            return {"success": False, "error": str(e)}

    def todo(self, input_data: TodoInput) -> dict:
        return {"todo": input_data.text or input_data.action}

    async def web_fetch(self, input_data: WebFetchInput) -> dict:
        try:
            result = await safe_fetch(input_data.url)
            return result
        except WebFetchError as e:
            return {"success": False, "error": str(e)}

    def web_search(self, input_data: WebSearchInput) -> dict:
        return {"results": [], "note": "web_search is not configured"}

    def write_file(self, input_data: WriteFileInput) -> dict:
        try:
            path = write_text_file(input_data.path, input_data.content)
            return {"written": True, "path": path, "success": True}
        except WorkspaceError as e:
            return {"success": False, "error": str(e)}
