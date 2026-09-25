"""Notification service for CareHub.

Handles reminder notifications for appointments.

BASELINE RULE (R001):
  Cancelled appointments must NOT generate reminder notifications.
  This service enforces that rule before writing any notification record.
"""

from db import get_db


def send_reminder(appointment_id: int) -> dict:
    """Send a reminder notification for an appointment.

    Returns a dict describing the outcome.
    Raises ValueError if the appointment is cancelled or does not exist.
    """
    db = get_db()

    row = db.execute(
        "SELECT id, status FROM appointments WHERE id = ?",
        (appointment_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"Appointment {appointment_id} not found.")

    if row["status"] == "cancelled":
        raise ValueError(
            f"Appointment {appointment_id} is cancelled. "
            "Reminders must not be sent for cancelled appointments (R001)."
        )

    message = f"Reminder: your appointment #{appointment_id} is coming up."
    db.execute(
        "INSERT INTO notifications (appointment_id, message) VALUES (?, ?)",
        (appointment_id, message),
    )
    db.commit()

    return {"appointment_id": appointment_id, "message": message, "sent": True}


def get_notifications_for_appointment(appointment_id: int) -> list:
    """Return all notification records for the given appointment."""
    db = get_db()
    rows = db.execute(
        "SELECT id, appointment_id, message, sent_at "
        "FROM notifications WHERE appointment_id = ?",
        (appointment_id,),
    ).fetchall()
    return [dict(r) for r in rows]
