"""Patient routes for CareHub."""

from flask import Blueprint, request, jsonify
from db import get_db
from models import patient_row_to_dict

patients_bp = Blueprint("patients", __name__)


@patients_bp.post("/patients")
def create_patient():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip() or None

    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM patients WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        return jsonify({"error": "A patient with that email already exists"}), 409

    cursor = db.execute(
        "INSERT INTO patients (name, email, phone) VALUES (?, ?, ?)",
        (name, email, phone),
    )
    db.commit()
    row = db.execute("SELECT * FROM patients WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(patient_row_to_dict(row)), 201


@patients_bp.get("/patients/<int:patient_id>")
def get_patient(patient_id):
    db = get_db()
    row = db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(patient_row_to_dict(row)), 200
