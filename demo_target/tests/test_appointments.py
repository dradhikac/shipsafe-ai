"""Tests for appointment endpoints.

Covers:
- appointment creation
- appointment retrieval
- appointment cancellation
- invalid patient / doctor / unavailable doctor
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
# Cancellation
# ---------------------------------------------------------------------------

def test_cancel_appointment_success(client):
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did).get_json()["appointment_id"]

    response = client.post(f"/appointments/{appt_id}/cancel")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "cancelled"


def test_cancel_already_cancelled_appointment(client):
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did).get_json()["appointment_id"]
    client.post(f"/appointments/{appt_id}/cancel")

    response = client.post(f"/appointments/{appt_id}/cancel")
    assert response.status_code == 400


def test_cancel_nonexistent_appointment(client):
    response = client.post("/appointments/9999/cancel")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Search / R004 SQL Parameterization tests
# ---------------------------------------------------------------------------

def test_search_appointments_by_status(client):
    """Verify searching appointments by status returns matching records (R004)."""
    pid, did = _setup_patient_and_doctor(client)
    appt1_id = create_appointment(client, pid, did).get_json()["appointment_id"]
    appt2_id = create_appointment(client, pid, did).get_json()["appointment_id"]
    client.post(f"/appointments/{appt2_id}/cancel")

    res = client.get("/appointments/search?status=scheduled")
    assert res.status_code == 200
    scheduled = res.get_json()
    assert any(a["appointment_id"] == appt1_id for a in scheduled)
    assert not any(a["appointment_id"] == appt2_id for a in scheduled)


def test_search_appointments_sql_injection_defense(client):
    """Verify malicious SQL injection payload is safely parameterized as literal data (R004)."""
    pid, did = _setup_patient_and_doctor(client)
    create_appointment(client, pid, did)

    # Classic SQL injection attempt to dump all records
    malicious_payload = "' OR '1'='1"
    res = client.get(f"/appointments/search?status={malicious_payload}")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


# ---------------------------------------------------------------------------
# Required fields in API responses — R002
# ---------------------------------------------------------------------------

def test_create_appointment_response_includes_required_fields(client):
    """POST /appointments response must include appointment_id, status, eta_minutes (R002)."""
    pid, did = _setup_patient_and_doctor(client)
    res = create_appointment(client, pid, did, eta_minutes=30)
    assert res.status_code == 201
    data = res.get_json()
    assert "appointment_id" in data
    assert "status" in data
    assert "eta_minutes" in data
    assert data["eta_minutes"] == 30


def test_get_appointment_response_includes_required_fields(client):
    """GET /appointments/<id> response must include appointment_id, status, eta_minutes (R002)."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, eta_minutes=25).get_json()["appointment_id"]
    res = client.get(f"/appointments/{appt_id}")
    assert res.status_code == 200
    data = res.get_json()
    assert "appointment_id" in data
    assert "status" in data
    assert "eta_minutes" in data
    assert data["eta_minutes"] == 25


def test_cancel_appointment_response_includes_required_fields(client):
    """POST /appointments/<id>/cancel response must include required fields (R002)."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, eta_minutes=15).get_json()["appointment_id"]
    res = client.post(f"/appointments/{appt_id}/cancel")
    assert res.status_code == 200
    data = res.get_json()
    assert "appointment_id" in data
    assert "status" in data
    assert "eta_minutes" in data
    assert data["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Priority persistence & validation — R003
# ---------------------------------------------------------------------------

def test_appointment_priority_persisted_normal(client):
    """Normal priority must be persisted and retrievable (R003)."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, priority="normal").get_json()["appointment_id"]
    data = client.get(f"/appointments/{appt_id}").get_json()
    assert data["priority"] == "normal"


def test_appointment_priority_persisted_high(client):
    """High priority must be persisted and retrievable (R003)."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, priority="high").get_json()["appointment_id"]
    data = client.get(f"/appointments/{appt_id}").get_json()
    assert data["priority"] == "high"


def test_appointment_priority_persisted_emergency(client):
    """Emergency priority must be persisted and retrievable (R003)."""
    pid, did = _setup_patient_and_doctor(client)
    appt_id = create_appointment(client, pid, did, priority="emergency").get_json()["appointment_id"]
    data = client.get(f"/appointments/{appt_id}").get_json()
    assert data["priority"] == "emergency"


def test_create_appointment_invalid_priority_critical(client):
    """Unauthorized priority 'critical' must be rejected with 400 (R003)."""
    pid, did = _setup_patient_and_doctor(client)
    res = create_appointment(client, pid, did, priority="critical")
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data
    assert "invalid priority" in data["error"].lower()
