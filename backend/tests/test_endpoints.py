"""
backend/tests/test_endpoints.py — Integration tests for FastAPI endpoints and agent pipeline.
"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient

os.environ["USE_FAKE_MEMORY"] = "true"

from app.main import app


@pytest.fixture(autouse=True)
def setup_test_data():
    with TestClient(app) as client:
        client.post(
            "/api/clients",
            json={
                "id": "client_acme",
                "name": "Acme Corp",
                "company": "Acme Corp",
                "primary_contact": "Sarah Jenkins",
                "quirks": ["No calls before 11am EST"],
            },
        )
        yield client


def test_health_endpoint(setup_test_data):
    client = setup_test_data
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_clients_crud(setup_test_data):
    client = setup_test_data
    res = client.get("/api/clients")
    assert res.status_code == 200
    clients = res.json()
    assert any(c["id"] == "client_acme" for c in clients)

    res_dup = client.post(
        "/api/clients",
        json={"id": "client_acme", "name": "Acme Corp Duplicate"},
    )
    assert res_dup.status_code == 400


def test_import_endpoint(setup_test_data):
    client = setup_test_data
    res = client.post(
        "/api/import",
        json={
            "client_id": "client_acme",
            "text": "Acme Corp VP Sarah Jenkins prefers Slack messages over email.",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["client_id"] == "client_acme"
    assert len(data["recalled_memories"]) > 0


def test_feedback_idempotency(setup_test_data):
    client = setup_test_data
    unique_resp_id = f"resp-test-{uuid.uuid4().hex[:8]}"

    res1 = client.post(
        "/api/feedback",
        json={
            "response_id": unique_resp_id,
            "outcome": "went_well",
            "notes": "Client approved proposal instantly.",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"

    res2 = client.post(
        "/api/feedback",
        json={
            "response_id": unique_resp_id,
            "outcome": "went_well",
            "notes": "Duplicate post",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "already_processed"
    assert data2["feedback_id"] == data1["feedback_id"]


def test_empty_and_oversized_input_validation(setup_test_data):
    client = setup_test_data

    res_empty = client.post(
        "/api/respond",
        json={"client_id": "client_acme", "incoming_text": "   "},
    )
    assert res_empty.status_code == 422

    res_huge = client.post(
        "/api/respond",
        json={"client_id": "client_acme", "incoming_text": "x" * 10001},
    )
    assert res_huge.status_code == 422
