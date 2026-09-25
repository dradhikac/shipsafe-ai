"""Pytest configuration and shared fixtures for CareHub tests."""

import os
import sys
import tempfile
import pytest

# Make the demo_target package importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
import db as database


@pytest.fixture
def app():
    """Create a Flask test application backed by an isolated temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    application = create_app({
        "TESTING": True,
        "DATABASE": db_path,
    })

    with application.app_context():
        database.init_db()

    yield application

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Helpers shared across test modules
# ---------------------------------------------------------------------------

def create_patient(client, name="Alice", email="alice@example.com", phone="555-0100"):
    return client.post("/patients", json={"name": name, "email": email, "phone": phone})


def create_doctor(client, name="Dr Smith", specialty="General", available=True):
    return client.post("/doctors", json={"name": name, "specialty": specialty, "available": available})


def create_appointment(client, patient_id, doctor_id,
                       appointment_date="2025-09-01T10:00:00",
                       priority="normal", eta_minutes=15):
    return client.post("/appointments", json={
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "priority": priority,
        "eta_minutes": eta_minutes,
    })
