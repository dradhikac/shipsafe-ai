"""Doctor routes for CareHub."""

from flask import Blueprint, request, jsonify
from db import get_db
from models import doctor_row_to_dict

doctors_bp = Blueprint("doctors", __name__)


@doctors_bp.post("/doctors")
def create_doctor():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    specialty = data.get("specialty", "").strip()
    available = data.get("available", True)

    if not name or not specialty:
        return jsonify({"error": "name and specialty are required"}), 400

    db = get_db()
    cursor = db.execute(
        "INSERT INTO doctors (name, specialty, available) VALUES (?, ?, ?)",
        (name, specialty, 1 if available else 0),
    )
    db.commit()
    row = db.execute("SELECT * FROM doctors WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(doctor_row_to_dict(row)), 201


@doctors_bp.get("/doctors/<int:doctor_id>/availability")
def get_availability(doctor_id):
    db = get_db()
    row = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify({
        "doctor_id": row["id"],
        "name": row["name"],
        "specialty": row["specialty"],
        "available": bool(row["available"]),
    }), 200
