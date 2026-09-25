"""Tests for notification / reminder behavior.

Key baseline rule (R001):
  Cancelled appointments must NOT generate reminder notifications.
"""

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


# ---------------------------------------------------------------------------
# R001 — Cancelled appointments must NOT generate reminders
# ---------------------------------------------------------------------------

def test_cancelled_appointment_does_not_trigger_reminder(client):
    """R001: sending a reminder for a cancelled appointment must be refused."""
    appt_id = _book_appointment(client)

    # Cancel the appointment
    cancel_response = client.post(f"/appointments/{appt_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.get_json()["status"] == "cancelled"

    # Attempt to send a reminder — must be rejected
    reminder_response = client.post(f"/appointments/{appt_id}/reminder")
    assert reminder_response.status_code == 400
    error = reminder_response.get_json()["error"].lower()
    assert "cancelled" in error


def test_cancelled_appointment_reminder_returns_error_message(client):
    """R001: the error response must clearly indicate the appointment is cancelled."""
    appt_id = _book_appointment(client)
    client.post(f"/appointments/{appt_id}/cancel")

    data = client.post(f"/appointments/{appt_id}/reminder").get_json()
    assert "error" in data


def test_reminder_for_nonexistent_appointment(client):
    response = client.post("/appointments/9999/reminder")
    assert response.status_code == 400
    assert "not found" in response.get_json()["error"].lower()


# ---------------------------------------------------------------------------
# Idempotency — multiple reminders for a scheduled appointment
# ---------------------------------------------------------------------------

def test_multiple_reminders_for_scheduled_appointment(client):
    """Sending multiple reminders for a scheduled appointment is allowed."""
    appt_id = _book_appointment(client)
    r1 = client.post(f"/appointments/{appt_id}/reminder")
    r2 = client.post(f"/appointments/{appt_id}/reminder")
    assert r1.status_code == 200
    assert r2.status_code == 200
