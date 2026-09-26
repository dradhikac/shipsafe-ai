"""Tests for the health endpoint."""


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json(client):
    response = client.get("/health")
    data = response.get_json()
    assert data is not None
    assert data["status"] == "ok"
    assert "CareHub" in data["service"]
