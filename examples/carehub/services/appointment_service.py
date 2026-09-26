"""Appointment service for CareHub.

Encapsulates business rules for creating and cancelling appointments.
"""

from models import VALID_PRIORITIES, appointment_row_to_dict
from db import get_db


def create_appointment(patient_id: int, doctor_id: int,
                       appointment_date: str, priority: str = "normal",
                       eta_minutes: int = 0) -> dict:
    """Create a new appointment.

    Validates:
    - Patient exists
    - Doctor exists and is available
    - Priority is a valid value

    Returns the created appointment as a dict.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority '{priority}'. "
            f"Must be one of: {', '.join(sorted(VALID_PRIORITIES))}."
        )

    db = get_db()

    patient = db.execute(
        "SELECT id FROM patients WHERE id = ?", (patient_id,)
    ).fetchone()
    if patient is None:
        raise ValueError(f"Patient {patient_id} not found.")

    doctor = db.execute(
        "SELECT id, available FROM doctors WHERE id = ?", (doctor_id,)
    ).fetchone()
    if doctor is None:
        raise ValueError(f"Doctor {doctor_id} not found.")
    if not doctor["available"]:
        raise ValueError(f"Doctor {doctor_id} is not available.")

    cursor = db.execute(
        """INSERT INTO appointments
               (patient_id, doctor_id, appointment_date, status, priority, eta_minutes)
           VALUES (?, ?, ?, 'scheduled', ?, ?)""",
        (patient_id, doctor_id, appointment_date, priority, eta_minutes),
    )
    db.commit()

    row = db.execute(
        "SELECT * FROM appointments WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return appointment_row_to_dict(row)


def cancel_appointment(appointment_id: int) -> dict:
    """Cancel an appointment.

    Only appointments in 'scheduled' status may be cancelled.
    Returns the updated appointment as a dict.
    """
    db = get_db()

    row = db.execute(
        "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
    ).fetchone()

    if row is None:
        raise ValueError(f"Appointment {appointment_id} not found.")

    if row["status"] != "scheduled":
        raise ValueError(
            f"Appointment {appointment_id} has status '{row['status']}' "
            "and cannot be cancelled."
        )

    db.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
        (appointment_id,),
    )
    db.commit()

    updated = db.execute(
        "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
    ).fetchone()
    return appointment_row_to_dict(updated)
