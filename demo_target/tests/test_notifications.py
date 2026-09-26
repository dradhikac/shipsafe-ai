"""Tests for notification / reminder behavior."""

from tests.conftest import create_patient, create_doctor, create_appointment


def _book_appointment(client, priority="normal", eta_minutes=15):
    pid = create_patient(client).get_json()["id"]
    did = create_doctor(client).get_json()["id"]
    appt = create_appointment(client, pid, did, priority=priority, eta_minutes=eta_minutes).get_json()
    return appt["appointment_id"]


# ---------------------------------------------------------------------------
# Reminders for scheduled appointments
# ---------------------------------------------------------------------------

def test_reminder_sent_for_scheduled_appointment(client):
    """A scheduled appointment should accept a reminder request."""
    appt_id = _book_appointment(client)
    response = client.post(f"/appointments/{appt_id}/reminder")
    assert response.status_code == 200
    data = response.get_json()
    assert data["sent"] is True
    assert data["appointment_id"] == appt_id


def test_reminder_response_contains_message(client):
    appt_id = _book_appointment(client)
    data = client.post(f"/appointments/{appt_id}/reminder").get_json()
    assert "message" in data
    assert len(data["message"]) > 0


def test_reminder_for_nonexistent_appointment(client):
    response = client.post("/appointments/9999/reminder")
    assert response.status_code == 400
    assert "not found" in response.get_json()["error"].lower()


def test_multiple_reminders_for_scheduled_appointment(client):
    """Sending multiple reminders for a scheduled appointment is allowed."""
    appt_id = _book_appointment(client)
    r1 = client.post(f"/appointments/{appt_id}/reminder")
    r2 = client.post(f"/appointments/{appt_id}/reminder")
    assert r1.status_code == 200
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Reminders for cancelled appointments — R001
# ---------------------------------------------------------------------------

def test_cancelled_appointment_does_not_trigger_reminder(client):
    """A cancelled appointment must reject a reminder request (R001)."""
    appt_id = _book_appointment(client)
    client.post(f"/appointments/{appt_id}/cancel")

    response = client.post(f"/appointments/{appt_id}/reminder")
    assert response.status_code == 400


def test_cancelled_appointment_reminder_returns_error_message(client):
    """The rejection response for a cancelled appointment must describe the error (R001)."""
    appt_id = _book_appointment(client)
    client.post(f"/appointments/{appt_id}/cancel")

    response = client.post(f"/appointments/{appt_id}/reminder")
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "cancelled" in data["error"].lower()
