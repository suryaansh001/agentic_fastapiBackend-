"""Security tests for agent tool endpoints.

Dangerous tool functionality must NOT be exposed as HTTP endpoints.
These tests prove that direct access is rejected and that the safe
tool services enforce their boundaries.
"""
import pytest
from fastapi.testclient import TestClient
from app.tests.test_fixtures import create_test_app, auth_headers, dev_headers


def test_dangerous_tool_endpoints_removed():
    """bash, execute_python, write_file, read_file, web_fetch, query_crm
    must not exist as HTTP endpoints."""
    app = create_test_app()
    client = TestClient(app)
    headers = auth_headers()
    dangerous = [
        ("/api/agents/runner/bash", {"command": "ls"}),
        ("/api/agents/runner/execute_python", {"code": "print(1)"}),
        ("/api/agents/runner/write_file", {"path": "/tmp/x", "content": "x"}),
        ("/api/agents/runner/read_file", {"path": "/etc/passwd"}),
        ("/api/agents/runner/web_fetch", {"url": "http://169.254.169.254/"}),
        ("/api/agents/runner/query_crm", {"query": "SELECT * FROM deal"}),
        ("/api/agents/runner/create_chart", {"code": "pass"}),
        ("/api/agents/runner/generate_pdf", {"content": "x"}),
        ("/api/agents/runner/glob", {"pattern": "**/*"}),
        ("/api/agents/runner/grep", {"pattern": "x"}),
    ]
    for path, body in dangerous:
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 404, f"{path} should not be exposed (got {response.status_code})"


def test_builder_endpoints_removed():
    """The builder tool router is deleted entirely."""
    app = create_test_app()
    client = TestClient(app)
    headers = auth_headers()
    for path, body in [
        ("/api/agents/builder/bash", {"command": "ls"}),
        ("/api/agents/builder/write_file", {"path": "/tmp/x", "content": "x"}),
    ]:
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 404


def test_unauthenticated_request_rejected():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/")
    assert response.status_code == 401


def test_invalid_token_rejected():
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_accepted(seed_data):
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/", headers=auth_headers())
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dev_mode_email_accepted(seed_data):
    """Dev-mode allow-list grants the user their own Member role."""
    app = create_test_app()
    client = TestClient(app)
    response = client.get("/api/agents/", headers=dev_headers())
    assert response.status_code == 200


def test_wildcard_sign_in_not_accepted():
    """'*' must never grant access; only explicit dev-mode emails do."""
    import os
    app = create_test_app()
    client = TestClient(app)
    # Even in dev mode, an email not on the allow-list is rejected.
    response = client.get("/api/agents/", headers=dev_headers("attacker@example.com"))
    assert response.status_code == 401


def test_filesystem_sandbox_rejects_traversal():
    from app.agent.tools.filesystem import WorkspaceError, resolve_workspace_path
    with pytest.raises(WorkspaceError):
        resolve_workspace_path("../../etc/passwd")
    with pytest.raises(WorkspaceError):
        resolve_workspace_path("/etc/passwd")


def test_filesystem_sandbox_allows_workspace_files():
    from app.agent.tools import filesystem
    path = filesystem.resolve_workspace_path("notes.txt")
    root = filesystem.workspace_root()
    assert root in path.parents or path.parent == root
    assert ".." not in path.parts


def test_ssrf_blocks_private_and_link_local():
    from app.agent.tools.web_fetch import WebFetchError, _validate_url
    for blocked in [
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/x",
        "http://192.168.1.1/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ]:
        with pytest.raises(WebFetchError):
            _validate_url(blocked)


def test_ssrf_allows_public_http(monkeypatch):
    """A public hostname with a public resolved address passes validation."""
    import socket as _socket
    monkeypatch.setattr(
        _socket, "getaddrinfo",
        lambda host, port: [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    from app.agent.tools.web_fetch import _validate_url
    assert _validate_url("https://example.com/page")


def test_ssrf_blocks_host_resolving_to_private(monkeypatch):
    """A public hostname that resolves to a private address is rejected."""
    import socket as _socket
    monkeypatch.setattr(
        _socket, "getaddrinfo",
        lambda host, port: [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))],
    )
    from app.agent.tools.web_fetch import WebFetchError, _validate_url
    with pytest.raises(WebFetchError):
        _validate_url("https://internal.example.com/page")


@pytest.mark.asyncio
async def test_crm_query_rejects_unknown_operation():
    from app.agent.tools.crm_query import CrmQueryError, crm_query_service
    class FakeSession:
        pass
    with pytest.raises(CrmQueryError):
        await crm_query_service.execute(FakeSession(), "DROP TABLE deal")


@pytest.mark.asyncio
async def test_crm_query_rejects_unknown_params():
    from app.agent.tools.crm_query import CrmQueryError, crm_query_service
    class FakeSession:
        pass
    with pytest.raises(CrmQueryError):
        await crm_query_service.execute(FakeSession(), "list_deals", {"unexpected": "1"})


@pytest.mark.asyncio
async def test_crm_query_requires_required_params():
    from app.agent.tools.crm_query import CrmQueryError, crm_query_service
    class FakeSession:
        pass
    with pytest.raises(CrmQueryError):
        await crm_query_service.execute(FakeSession(), "deal_summary", {})
