"""Tests for appointment endpoints.

Covers:
- appointment creation (R002: response includes appointment_id, status, eta_minutes)
- appointment retrieval
- appointment cancellation
- invalid patient / doctor / unavailable doctor
- priority persistence (R003 baseline)
- invalid cancellation
"""

from tests.conftest import create_patient, create_doctor, create_appointment


def _setup_patient_and_doctor(client):
    p = create_patient(client).get_json()
    d = create_doctor(client).get_json()
    return p["id"], d["id"]


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

def test_create_appointment_success(client):
    pid, did = _setup_patient_and_doctor(client)
    response = create_appointment(client, pid, did)
    assert response.status_code == 201


def test_create_appointment_response_includes_required_fields(client):
    """R002: response must include appointment_id, status, eta_minutes."""
    pid, did = _setup_patient_and_doctor(client)
    response = create_appointment(client, pid, did, eta_minutes=20)
    data = response.get_json()
    assert "appointment_id" in data, "R002: appointment_id missing from response"
    assert "status" in data, "R002: status missing from response"
    assert "eta_minutes" in data, "R002: eta_minutes missing from response"
    assert data["status"] == "scheduled"
    assert data["eta_minutes"] == 20


def test_create_appointment_missing_fields(client):
    response = client.post("/appointments", json={})
    assert response.status_code == 400


def test_create_appointment_invalid_patient(client):
    _, did = _setup_patient_and_doctor(client)
    response = create_appointment(client, 9999, did)
    assert response.status_code == 400
    assert "not found" in response.get_json()["error"].lower()


def test_create_appointment_invalid_doctor(client):
    pid, _ = _setup_patient_and_doctor(client)
    response = create_appointment(client, pid, 9999)
    assert response.status_code == 400
    assert "not found" in response.get_json()["error"].lower()


def test_create_appointment_unavailable_doctor(client):
    pid, _ = _setup_patient_and_doctor(client)
    unavail = create_doctor(client, name="Dr Busy", specialty="ENT", available=False)
    unavail_id = unavail.get_json()["id"]
    response = create_appointment(client, pid, unavail_id)
    assert response.status_code == 400
    assert "not available" in response.get_json()["error"].lower()


def test_create_appointment_invalid_priority(client):
    pid, did = _setup_patient_and_doctor(client)
    response = client.post("/appointments", json={
        "patient_id": pid,
        "doctor_id": did,
        "appointment_date": "2025-09-01T10:00:00",
        "priority": "vip",
    })
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def test_get_appointment_success(client):
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did).get_json()["appointment_id"]

    response = client.get(f"/appointments/{appt_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["appointment_id"] == appt_id


def test_get_appointment_not_found(client):
    response = client.get("/appointments/9999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Priority persistence (R003 baseline)
# ---------------------------------------------------------------------------

def test_appointment_priority_persisted_normal(client):
    """Baseline R003: normal priority round-trips through the database."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, priority="normal").get_json()["appointment_id"]
    data = client.get(f"/appointments/{appt_id}").get_json()
    assert data["priority"] == "normal"


def test_appointment_priority_persisted_high(client):
    """Baseline R003: high priority round-trips through the database."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, priority="high").get_json()["appointment_id"]
    data = client.get(f"/appointments/{appt_id}").get_json()
    assert data["priority"] == "high"


def test_appointment_priority_persisted_emergency(client):
    """Baseline R003: emergency priority round-trips through the database."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, priority="emergency").get_json()["appointment_id"]
    data = client.get(f"/appointments/{appt_id}").get_json()
    assert data["priority"] == "emergency"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def test_cancel_appointment_success(client):
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did).get_json()["appointment_id"]

    response = client.post(f"/appointments/{appt_id}/cancel")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "cancelled"


def test_cancel_appointment_response_includes_required_fields(client):
    """R002: cancel response must also include appointment_id, status, eta_minutes."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, eta_minutes=10).get_json()["appointment_id"]

    data = client.post(f"/appointments/{appt_id}/cancel").get_json()
    assert "appointment_id" in data
    assert "status" in data
    assert "eta_minutes" in data


def test_cancel_already_cancelled_appointment(client):
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did).get_json()["appointment_id"]
    client.post(f"/appointments/{appt_id}/cancel")

    response = client.post(f"/appointments/{appt_id}/cancel")
    assert response.status_code == 400


def test_cancel_nonexistent_appointment(client):
    response = client.post("/appointments/9999/cancel")
    assert response.status_code == 400
