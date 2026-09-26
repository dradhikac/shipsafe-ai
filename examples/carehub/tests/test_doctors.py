"""Tests for doctor endpoints."""

from tests.conftest import create_doctor


def test_create_doctor_success(client):
    response = create_doctor(client)
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Dr Smith"
    assert data["specialty"] == "General"
    assert data["available"] is True


def test_create_doctor_unavailable(client):
    response = create_doctor(client, available=False)
    assert response.status_code == 201
    data = response.get_json()
    assert data["available"] is False


def test_create_doctor_missing_name(client):
    response = client.post("/doctors", json={"specialty": "Cardiology"})
    assert response.status_code == 400


def test_create_doctor_missing_specialty(client):
    response = client.post("/doctors", json={"name": "Dr Jones"})
    assert response.status_code == 400


def test_get_doctor_availability_available(client):
    create_response = create_doctor(client, available=True)
    doctor_id = create_response.get_json()["id"]

    response = client.get(f"/doctors/{doctor_id}/availability")
    assert response.status_code == 200
    data = response.get_json()
    assert data["available"] is True
    assert data["doctor_id"] == doctor_id


def test_get_doctor_availability_unavailable(client):
    create_response = create_doctor(client, available=False)
    doctor_id = create_response.get_json()["id"]

    response = client.get(f"/doctors/{doctor_id}/availability")
    assert response.status_code == 200
    data = response.get_json()
    assert data["available"] is False


def test_get_doctor_availability_not_found(client):
    response = client.get("/doctors/9999/availability")
    assert response.status_code == 404
