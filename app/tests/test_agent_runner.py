import pytest
from fastapi.testclient import TestClient
from app.tests.test_fixtures import create_test_app, auth_headers
def test_ask_question():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/ask_question",
        json={"question": "What is AI?"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_bash():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/bash",
        json={"command": "ls"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_create_crm_activity():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/create_crm_activity",
        json={"type": "CALL", "contactId": "contact_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_finish_run():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/finish_run",
        json={"runId": "run_1", "summary": "done"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_glob():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/glob",
        json={"pattern": "**/*.py"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_grep():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/grep",
        json={"pattern": "test", "path": "."},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_inspect_run():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/inspect_run",
        json={"runId": "run_1", "summary": "done"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_post_slack_message():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/post_slack_message",
        json={"channel": "#general", "message": "Hello"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_query_crm():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/query_crm",
        json={"query": "Find deals"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_read_crm_record():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/read_crm_record",
        json={"recordId": "deal_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_read_file():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/read_file",
        json={"path": "/test.txt"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_todo():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/todo",
        json={"action": "test", "text": "test task"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_web_fetch():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/web_fetch",
        json={"url": "https://example.com"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_web_search():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/web_search",
        json={"query": "test"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_write_file():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/runner/write_file",
        json={"path": "/test.txt", "content": "hello"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_all_runner_tools():
    app = create_test_app()
    client = TestClient(app)
    tools = ["ask_question", "bash", "create_crm_activity", "finish_run", "glob", "grep", "inspect_run", "post_slack_message", "query_crm", "read_crm_record", "read_file", "todo", "web_fetch", "web_search", "write_file"]
    for tool in tools:
        response = client.post(f"/api/agents/runner/{tool}", json={}, headers=auth_headers())
        assert response.status_code == 200