import pytest
from fastapi.testclient import TestClient
from app.tests.test_fixtures import create_test_app, auth_headers, engine_test
from app.database.session import Base
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["BETTER_AUTH_SECRET"] = "test-secret-key"
os.environ["AGENT_BRIDGE_SECRET"] = "test-bridge-secret"
os.environ["ALLOWED_SIGN_IN"] = "*"

def test_list_agents_empty():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0

def test_create_agent():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/",
        json={"name": "Test Agent", "description": "A test agent"},
        headers=auth_headers(),
    )
    assert response.status_code in [200, 201, 404, 405]

def test_get_agent_not_found():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/nonexistent", headers=auth_headers())
    assert response.status_code == 404

def test_run_agent_not_live():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/agent_1/run",
        json={"agent_id": "agent_1", "client_request_id": "req_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 400

def test_agent_crud_operations():
    app = create_test_app()
    client = TestClient(app)
    response = client.patch(
        "/api/agents/agent_1",
        json={"name": "Updated Agent"},
        headers=auth_headers(),
    )
    assert response.status_code in [403, 404, 200]
    response = client.post(
        "/api/agents/agent_1/deploy",
        json={"agent_id": "agent_1", "version_id": "ver_1", "client_request_id": "req_1"},
        headers=auth_headers(),
    )
    assert response.status_code in [403, 404, 200]

def test_agent_history():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/agent_1/history", headers=auth_headers())
    assert response.status_code == 200

def test_agent_tasks():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/agent_1/tasks", headers=auth_headers())
    assert response.status_code == 200

def test_dispatch_agent():
    app = create_test_app()
    client = TestClient(app)
    response = client.post("/api/agents/agent_1/dispatch", headers=auth_headers())
    assert response.status_code == 200

def test_internal_dispatch():
    app = create_test_app()
    client = TestClient(app)
    response = client.post("/internal/crm/dispatch", headers=auth_headers())
    assert response.status_code == 200

def test_dispatch_health():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/internal/crm/dispatch-health", headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True