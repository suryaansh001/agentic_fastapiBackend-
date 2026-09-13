import pytest
from fastapi.testclient import TestClient
from app.tests.test_fixtures import create_test_app, auth_headers
def test_bash():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/bash",
        json={"command": "echo hello"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_glob():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/glob",
        json={"pattern": "**/*.py"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_grep():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/grep",
        json={"pattern": "test", "path": "."},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_read_file():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/read_file",
        json={"path": "/test.txt", "content": "hello"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_write_file():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/write_file",
        json={"path": "/test.txt", "content": "hello"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_todo():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/todo",
        json={"action": "test", "text": "test task"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_web_fetch():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/web_fetch",
        json={"url": "https://example.com"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_web_search():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/web_search",
        json={"query": "test"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_save_agent_draft():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/save_agent_draft",
        json={"versionId": "ver_1", "summary": "test draft"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_inspect_context():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/inspect_context",
        json={"key": "test"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_write_agent_file():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/builder/write_agent_file",
        json={"path": "/agent.md", "content": "# Agent"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_all_builder_tools():
    app = create_test_app()
    client = TestClient(app)
    tools = ["bash", "glob", "grep", "read_file", "write_file", "todo", "web_fetch", "web_search", "save_agent_draft", "inspect_context", "write_agent_file"]
    for tool in tools:
        response = client.post(f"/api/agents/builder/{tool}", json={}, headers=auth_headers())
        assert response.status_code == 200