"""Test for webhook simulation payload generator."""

from scripts.simulate_webhook import generate_push_payload, generate_pr_payload
from fastapi.testclient import TestClient
from api.app import app
import json
import uuid


def test_simulate_webhook_payloads():
    push_payload = generate_push_payload("carehub", "main", "examples/carehub")
    assert push_payload["ref"] == "refs/heads/main"
    assert push_payload["repository"]["name"] == "carehub"
    assert "local_path" in push_payload

    pr_payload = generate_pr_payload("carehub", "feature/pr-1", "examples/carehub")
    assert pr_payload["action"] == "opened"
    assert pr_payload["pull_request"]["head"]["ref"] == "feature/pr-1"


def test_simulation_integration_with_api():
    import os
    import hmac
    import hashlib

    client = TestClient(app)
    delivery_id = str(uuid.uuid4())
    payload = generate_push_payload("carehub-sim", "main", "examples/carehub")
    body_bytes = json.dumps(payload).encode("utf-8")

    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "test_secret")
    os.environ["GITHUB_WEBHOOK_SECRET"] = secret
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sig,
    }

    response = client.post("/webhooks/github", content=body_bytes, headers=headers)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["delivery_id"] == delivery_id
    assert "run_id" in data
