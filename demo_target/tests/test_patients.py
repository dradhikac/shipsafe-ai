"""Tests for patient endpoints."""

from tests.conftest import create_patient


def test_create_patient_success(client):
    response = create_patient(client)
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data


def test_create_patient_returns_phone(client):
    response = create_patient(client, phone="555-9999")
    data = response.get_json()
    assert data["phone"] == "555-9999"


def test_create_patient_missing_name(client):
    response = client.post("/patients", json={"email": "x@example.com"})
    assert response.status_code == 400


def test_create_patient_missing_email(client):
    response = client.post("/patients", json={"name": "Bob"})
    assert response.status_code == 400


def test_create_patient_duplicate_email(client):
    create_patient(client)
    response = create_patient(client)  # same email
    assert response.status_code == 409


def test_get_patient_success(client):
    create_response = create_patient(client)
    patient_id = create_response.get_json()["id"]

    response = client.get(f"/patients/{patient_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == patient_id
    assert data["name"] == "Alice"


def test_get_patient_not_found(client):
    response = client.get("/patients/9999")
    assert response.status_code == 404
