import pytest
from fastapi.testclient import TestClient
from app.tests.test_fixtures import create_test_app, auth_headers
def test_search_crm_by_name():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/search_crm",
        json={"query": "Acme", "kinds": ["company", "contact"]},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Acme"
    assert isinstance(data["total"], int)

def test_search_crm_by_email():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/search_crm",
        json={"query": "john@acme.com", "kinds": ["contact"]},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "contacts" in data

def test_search_crm_by_deal_name():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/search_crm",
        json={"query": "Enterprise", "kinds": ["deal"]},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "deals" in data

def test_read_crm_history():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/read_crm_history",
        json={"contactId": "contact_1", "threads": 5},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "found" in data

def test_read_company_history():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/read_company_history",
        params={"company_id": "company_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_read_deal_history():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/read_deal_history",
        params={"deal_id": "deal_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_list_deals():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/list_deals",
        json={"status": "open", "limit": 10},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "deals" in data

def test_research_person():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/research_person",
        json={"question": "What has Acme Corp announced recently?", "deep": False},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data or "answer" in data

def test_research_company():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/research_company",
        json={"companyId": "company_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_identify_contact():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/identify_contact",
        json={
            "contactId": "contact_1",
            "fullName": "John Doe",
            "evidence": [{"kind": "email", "detail": "Signed email signature"}],
            "sourceUrl": "https://example.com",
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "applied" in data

def test_schedule_recheck():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/schedule_recheck",
        json={
            "contactId": "contact_1",
            "days": 14,
            "reason": "Champion on open deal",
            "budget": 4,
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scheduled"] is True

def test_list_outstanding_work():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/list_outstanding_work",
        json={"limit": 10},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "count" in data

def test_write_brief():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/write_brief",
        json={
            "contactId": "contact_1",
            "narrative": "John Doe is the CEO of Acme Corp. He has been leading the company for 5 years.",
            "evidence": [{"kind": "email", "detail": "Email signature"}],
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "written" in data

def test_find_contact_socials():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/find_contact_socials",
        json={"contactId": "contact_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert "searched" in data

def test_list_fields():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/list_fields",
        json={"entity": "contact"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_manage_fields():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/manage_fields",
        json={"entity": "contact", "fields": [{"name": "title", "type": "text"}]},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_set_field_value():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/set_field_value",
        json={"contactId": "contact_1", "fieldId": "field_1", "value": "CEO"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_record_fact():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/record_fact",
        json={
            "contactId": "contact_1",
            "field": "title",
            "value": "CEO",
            "evidence": [{"kind": "email", "detail": "Signature"}],
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_record_job_change():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/record_job_change",
        json={
            "contactId": "contact_1",
            "newRole": "CEO at Acme Corp",
            "evidence": [{"kind": "email", "detail": "LinkedIn update"}],
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_enrich_company():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/enrich_company",
        json={"companyId": "company_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_fetch_contact_photo():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/fetch_contact_photo",
        json={"contactId": "contact_1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200

def test_set_chat_title():
    app = create_test_app()
    client = TestClient(app)
    response = client.post(
        "/api/agents/root/set_chat_title",
        json={"conversationId": "conv_1", "title": "Acme Analysis"},
        headers=auth_headers(),
    )
    assert response.status_code == 200