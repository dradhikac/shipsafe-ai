"""Tests for FastAPI endpoints, webhook ingestion, and database persistence."""

import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from api.app import app
from shipsafe.database import SessionLocal, init_db, Repository, AnalysisRun, WebhookEvent


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["product"] == "ShipSafe AI"


def test_repository_registration(client):
    payload = {
        "name": "test-repo-sample",
        "repo_url": "https://github.com/example/test-repo-sample.git",
        "default_branch": "main"
    }
    response = client.post("/api/repositories", json=payload)
    assert response.status_code in (201, 400)
    
    # List repositories
    list_resp = client.get("/api/repositories")
    assert list_resp.status_code == 200
    repos = list_resp.json()
    assert any(r["name"] == "test-repo-sample" for r in repos)


def test_webhook_push_event(client):
    secret = "testsecret123"
    payload = {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": "1111111111111111111111111111111111111111",
        "repository": {
            "name": "carehub-service",
            "clone_url": "https://github.com/example/carehub.git",
            "default_branch": "main"
        }
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    import os
    import uuid
    os.environ["GITHUB_WEBHOOK_SECRET"] = secret

    delivery_id = f"test-delivery-{uuid.uuid4()}"
    headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sig,
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/github", content=body_bytes, headers=headers)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["delivery_id"] == delivery_id
    assert "run_id" in data

    # Test Duplicate Delivery ID handling
    dup_resp = client.post("/webhooks/github", content=body_bytes, headers=headers)
    assert dup_resp.status_code == 202
    dup_data = dup_resp.json()
    assert dup_data["status"] == "duplicate_ignored"


def test_webhook_invalid_signature(client):
    import os
    os.environ["GITHUB_WEBHOOK_SECRET"] = "secret_key"
    payload = {"some": "data"}
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "test-delivery-invalid-sig",
        "X-Hub-Signature-256": "sha256=invalidhashvalue123456",
        "Content-Type": "application/json",
    }
    response = client.post("/webhooks/github", content=body_bytes, headers=headers)
    assert response.status_code == 401
