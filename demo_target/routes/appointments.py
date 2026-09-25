"""Appointment routes for CareHub."""

from flask import Blueprint, request, jsonify
from services.appointment_service import create_appointment, cancel_appointment
from services.notification_service import send_reminder
from models import appointment_row_to_dict
from db import get_db

appointments_bp = Blueprint("appointments", __name__)


@appointments_bp.post("/appointments")
def new_appointment():
    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")
    appointment_date = data.get("appointment_date", "").strip()
    priority = data.get("priority", "normal")
    eta_minutes = data.get("eta_minutes", 0)

    if not patient_id or not doctor_id or not appointment_date:
        return jsonify({"error": "patient_id, doctor_id, and appointment_date are required"}), 400

    try:
        appt = create_appointment(
            patient_id=int(patient_id),
            doctor_id=int(doctor_id),
            appointment_date=appointment_date,
            priority=priority,
            eta_minutes=int(eta_minutes),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(appt), 201


@appointments_bp.get("/appointments/<int:appointment_id>")
def get_appointment(appointment_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "Appointment not found"}), 404
    return jsonify(appointment_row_to_dict(row)), 200


@appointments_bp.post("/appointments/<int:appointment_id>/cancel")
def cancel(appointment_id):
    try:
        appt = cancel_appointment(appointment_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(appt), 200


@appointments_bp.post("/appointments/<int:appointment_id>/reminder")
def reminder(appointment_id):
    try:
        result = send_reminder(appointment_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 200
