#!/usr/bin/env python3
"""Apply the controlled bad-release demo fixture to the CareHub demo target.

This script introduces five deterministic, evidence-backed regressions that
violate the CareHub v2.4 release requirements (R001-R005).  It is the
counterpart to reset_demo.py which restores the clean baseline.

Usage:
    python scripts/apply_demo_release.py

Safety rules enforced:
  - Verifies the repository starts from the expected clean baseline commit.
  - Refuses to run if the working tree contains unrelated modifications.
  - Never modifies ShipSafe engine files (shipsafe/).
  - Reports exactly which files it changed.
"""

import os
import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOTIFICATION_SERVICE = os.path.join(REPO_ROOT, "demo_target", "services", "notification_service.py")
MODELS = os.path.join(REPO_ROOT, "demo_target", "models.py")
DB = os.path.join(REPO_ROOT, "demo_target", "db.py")
APPOINTMENTS_ROUTE = os.path.join(REPO_ROOT, "demo_target", "routes", "appointments.py")
TEST_NOTIFICATIONS = os.path.join(REPO_ROOT, "demo_target", "tests", "test_notifications.py")
TEST_APPOINTMENTS = os.path.join(REPO_ROOT, "demo_target", "tests", "test_appointments.py")

# Files that this script will modify (relative to repo root for display)
CHANGED_FILES = [
    "demo_target/services/notification_service.py",
    "demo_target/models.py",
    "demo_target/db.py",
    "demo_target/routes/appointments.py",
    "demo_target/tests/test_notifications.py",
    "demo_target/tests/test_appointments.py",
]

# ---------------------------------------------------------------------------
# Expected baseline commit (HEAD of clean baseline)
# ---------------------------------------------------------------------------

BASELINE_COMMIT = "5f95cd16041b2f63ffd9f811516fa42916f34e56"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd, cwd=None):
    result = subprocess.run(
        cmd, cwd=cwd or REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result


def _abort(message):
    print(f"\nERROR: {message}", file=sys.stderr)
    print("Demo release not applied. Repository is unchanged.", file=sys.stderr)
    sys.exit(1)


def _verify_baseline():
    """Verify the repo is at the expected clean baseline commit."""
    # Check HEAD commit
    r = _run(["git", "rev-parse", "HEAD"])
    if r.returncode != 0:
        _abort("Could not determine HEAD commit. Is this a Git repository?")
    head = r.stdout.strip()
    if not head.startswith(BASELINE_COMMIT[:12]):
        _abort(
            f"HEAD is {head[:12]}, expected baseline {BASELINE_COMMIT[:12]}.\n"
            "Run `python scripts/reset_demo.py` first to restore the clean baseline."
        )

    # Check working tree cleanliness — only allow migrations/ and scripts/ additions
    r = _run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if r.returncode != 0:
        _abort("Could not check git status.")

    lines = [l for l in r.stdout.splitlines() if l.strip()]
    forbidden = []
    for line in lines:
        # Porcelain v1: XY<space>path — XY is the two-char status code
        xy = line[:2]
        path = line[3:].strip()
        # Allow untracked new files in demo-support directories
        if xy == "??" and (
            path.startswith("migrations/") or
            path.startswith("scripts/") or
            path.startswith("reports/") or
            path.startswith("docs/")
        ):
            continue
        # Allow modified .gitignore (from the analysis-engine baseline commit)
        if path == ".gitignore" and xy in (" M", "M "):
            continue
        forbidden.append(f"  {line}")

    if forbidden:
        _abort(
            "Working tree has unrelated modifications:\n" + "\n".join(forbidden) + "\n\n"
            "Please commit or stash these changes before applying the demo release."
        )


def _write(path, content):
    """Write content to path, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Bad-release content for each changed file
# ---------------------------------------------------------------------------

# R001 regression: The cancelled-appointment guard now checks for "completed"
# instead of "cancelled", so cancelled appointments silently receive reminders.
NOTIFICATION_SERVICE_BAD = textwrap.dedent('''\
    """Notification service for CareHub.

    Handles reminder notifications for appointments.
    """

    from db import get_db


    def send_reminder(appointment_id: int) -> dict:
        """Send a reminder notification for an appointment.

        Returns a dict describing the outcome.
        Raises ValueError if the appointment does not exist or is completed.
        """
        db = get_db()

        row = db.execute(
            "SELECT id, status FROM appointments WHERE id = ?",
            (appointment_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Appointment {appointment_id} not found.")

        if row["status"] == "completed":
            raise ValueError(
                f"Appointment {appointment_id} is completed. "
                "Reminders cannot be sent for completed appointments."
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
''')


# R002 regression: eta_minutes removed from appointment_row_to_dict.
# The field is stored in the database but no longer returned in API responses.
# R003 regression: VALID_PRIORITIES gains "critical" — the application now
# accepts and persists a fourth priority value that the schema has no migration
# for. migration 001 has no 'critical' value and no CHECK constraint.
MODELS_BAD = textwrap.dedent('''\
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
            "created_at": row["created_at"],
        }


    # Valid domain values
    VALID_STATUSES = {"scheduled", "cancelled", "completed"}
    VALID_PRIORITIES = {"normal", "high", "emergency", "critical"}
''')


# R003 regression: the priority column in SCHEMA gains an explicit CHECK
# constraint that includes the new "critical" value.  This is a concrete schema
# evolution: the constraint did not exist at all in migration 001, and the new
# allowed value set is not documented by any migration file.
DB_BAD = textwrap.dedent('''\
    """Database connection and schema initialisation for CareHub."""

    import sqlite3
    import os
    from flask import g, current_app


    def get_db():
        """Return a database connection bound to the current application context."""
        if "db" not in g:
            g.db = sqlite3.connect(
                current_app.config["DATABASE"],
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db


    def close_db(e=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()


    SCHEMA = """
    CREATE TABLE IF NOT EXISTS patients (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        email       TEXT    NOT NULL UNIQUE,
        phone       TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime(\'now\'))
    );

    CREATE TABLE IF NOT EXISTS doctors (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        specialty   TEXT    NOT NULL,
        available   INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS appointments (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id       INTEGER NOT NULL REFERENCES patients(id),
        doctor_id        INTEGER NOT NULL REFERENCES doctors(id),
        appointment_date TEXT    NOT NULL,
        status           TEXT    NOT NULL DEFAULT \'scheduled\',
        priority         TEXT    NOT NULL DEFAULT \'normal\'
                             CHECK (priority IN (\'normal\', \'high\', \'emergency\', \'critical\')),
        eta_minutes      INTEGER NOT NULL DEFAULT 0,
        created_at       TEXT    NOT NULL DEFAULT (datetime(\'now\'))
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id  INTEGER NOT NULL REFERENCES appointments(id),
        message         TEXT    NOT NULL,
        sent_at         TEXT    NOT NULL DEFAULT (datetime(\'now\'))
    );

    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     TEXT PRIMARY KEY,
        applied_at  TEXT NOT NULL DEFAULT (datetime(\'now\'))
    );
    """


    def init_db(db=None):
        """Create all tables if they do not exist."""
        conn = db if db is not None else get_db()
        conn.executescript(SCHEMA)
        conn.commit()


    def init_app(app):
        app.teardown_appcontext(close_db)
''')


# R004 regression: search_appointments endpoint uses string concatenation.
# Route layer is otherwise identical to baseline (no urgency_level).
APPOINTMENTS_ROUTE_BAD = textwrap.dedent('''\
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


    @appointments_bp.get("/appointments/search")
    def search_appointments():
        """Search appointments by status.

        R004 violation: user-supplied status is concatenated directly into the
        SQL query string instead of using a parameterized placeholder.
        """
        status = request.args.get("status", "")
        db = get_db()
        query = "SELECT * FROM appointments WHERE status = \'" + status + "\'"
        rows = db.execute(query).fetchall()
        return jsonify([appointment_row_to_dict(r) for r in rows]), 200
''')


# R005 regression: remove the specific regression tests that cover R001, R002,
# and R003.  The test file is structurally intact but the key regression
# scenarios are gone — realistic "behavior changed, test not updated" pattern.
TEST_NOTIFICATIONS_BAD = textwrap.dedent('''\
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
''')


TEST_APPOINTMENTS_BAD = textwrap.dedent('''\
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
''')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("ShipSafe Demo — Apply Bad Release")
    print("=" * 60)

    print("\n[1/3] Verifying clean baseline...")
    _verify_baseline()
    print(f"  OK — HEAD is baseline commit {BASELINE_COMMIT[:12]}")
    print("  OK — Working tree is clean (allowing demo support files)")

    print("\n[2/3] Applying regressions...")

    changes = [
        (NOTIFICATION_SERVICE, NOTIFICATION_SERVICE_BAD,
         "R001 — cancelled guard changed from 'cancelled' to 'completed'"),
        (MODELS, MODELS_BAD,
         "R002/R003 — eta_minutes removed; VALID_PRIORITIES gains 'critical'"),
        (DB, DB_BAD,
         "R003 — priority column gains CHECK constraint with 'critical' value; no migration"),
        (APPOINTMENTS_ROUTE, APPOINTMENTS_ROUTE_BAD,
         "R004 — unsafe SQL search endpoint added"),
        (TEST_NOTIFICATIONS, TEST_NOTIFICATIONS_BAD,
         "R005 — R001 regression tests removed from test_notifications.py"),
        (TEST_APPOINTMENTS, TEST_APPOINTMENTS_BAD,
         "R005 — R002/R003 regression tests removed from test_appointments.py"),
    ]

    for path, content, description in changes:
        _write(path, content)
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        print(f"  CHANGED  {rel}")
        print(f"           {description}")

    print("\n[3/3] Summary")
    print(f"  Files changed: {len(changes)}")
    for rel_path in CHANGED_FILES:
        print(f"    {rel_path}")

    print("""
Regressions applied:
  R001  notification_service.py — cancelled guard broken
  R002  models.py               — eta_minutes absent from API responses
  R003  db.py + models.py       — 'critical' priority + CHECK constraint added without migration
  R004  routes/appointments.py  — unsafe SQL search endpoint
  R005  test_notifications.py + test_appointments.py — regression tests removed

ShipSafe engine files were NOT modified.

To restore the clean baseline:
  python scripts/reset_demo.py
""")


if __name__ == "__main__":
    main()
