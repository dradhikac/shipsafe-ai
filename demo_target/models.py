"""Domain helpers for CareHub models.

These functions convert sqlite3.Row objects into plain dicts for JSON
serialisation and provide simple query helpers.
"""


def patient_row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "created_at": row["created_at"],
    }


def doctor_row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "specialty": row["specialty"],
        "available": bool(row["available"]),
    }


def appointment_row_to_dict(row):
    return {
        "appointment_id": row["id"],
        "patient_id": row["patient_id"],
        "doctor_id": row["doctor_id"],
        "appointment_date": row["appointment_date"],
        "status": row["status"],
        "priority": row["priority"],
        "eta_minutes": row["eta_minutes"],
        "created_at": row["created_at"],
    }


# Valid domain values
VALID_STATUSES = {"scheduled", "cancelled", "completed"}
VALID_PRIORITIES = {"normal", "high", "emergency"}
