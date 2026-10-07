"""Phase 2 tests: canonical tool registry."""
import pytest

from app.agent.tools.registry import (
    RISK_APPROVAL_REQUIRED,
    RISK_SAFE,
    ToolContext,
    default_registry,
)


@pytest.fixture
def registry():
    return default_registry()


def test_registry_has_all_tools(registry):
    names = registry.names()
    expected = {
        "ask_question",
        "query_crm",
        "create_crm_activity",
        "finish_run",
        "glob",
        "grep",
        "inspect_run",
        "post_slack_message",
        "read_crm_record",
        "read_file",
        "spawn_subagent",
        "todo",
        "web_fetch",
        "web_search",
        "write_file",
    }
    assert set(names) == expected


def test_llm_schemas_are_function_calling_shaped(registry):
    schemas = registry.llm_schemas()
    assert len(schemas) == len(registry.names())
    for schema in schemas:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"]
        assert fn["description"]
        assert "properties" in fn["parameters"]


@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error(registry):
    result = await registry.execute("does_not_exist", {})
    assert result["success"] is False
    assert "unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_execute_query_crm_returns_seed_data(registry, db_session):
    ctx = ToolContext(user_id="user_1", session=db_session)
    result = await registry.execute(
        "query_crm", {"operation": "list_deals", "params": {"limit": 10}}, ctx
    )
    assert result["success"] is True
    assert isinstance(result["rows"], list)
    assert "id" in result["columns"]
    id_idx = result["columns"].index("id")
    assert any(row[id_idx] == "deal_1" for row in result["rows"])


@pytest.mark.asyncio
async def test_execute_query_crm_lists_companies(registry, db_session):
    ctx = ToolContext(user_id="user_1", session=db_session)
    result = await registry.execute(
        "query_crm", {"operation": "list_companies", "params": {"limit": 10}}, ctx
    )
    assert result["success"] is True
    name_idx = result["columns"].index("name")
    assert any(row[name_idx] == "Acme Corp" for row in result["rows"])


@pytest.mark.asyncio
async def test_execute_query_crm_rejects_unknown_operation(registry, db_session):
    ctx = ToolContext(session=db_session)
    result = await registry.execute(
        "query_crm", {"operation": "drop_tables", "params": {}}, ctx
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_execute_read_file_blocks_traversal(registry):
    result = await registry.execute(
        "read_file", {"path": "../../etc/passwd"}, ToolContext()
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_execute_finish_run(registry):
    result = await registry.execute(
        "finish_run",
        {"runId": "run_1", "summary": "done", "result": {"rows": 2}},
        ToolContext(),
    )
    assert result["finished"] is True
    assert result["runId"] == "run_1"


def test_risk_tiers(registry):
    approval_tools = {
        spec.name for spec in registry.list_tools()
        if spec.risk == RISK_APPROVAL_REQUIRED
    }
    assert approval_tools == {
        "create_crm_activity",
        "post_slack_message",
        "write_file",
    }
    for spec in registry.list_tools():
        assert spec.risk in (RISK_SAFE, RISK_APPROVAL_REQUIRED)


def test_registry_is_singleton(registry):
    assert default_registry() is registry
