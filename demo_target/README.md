# CareHub Appointment Service

A compact healthcare appointment management service used as the **demo target** for ShipSafe AI analysis.

> **Note:** This is NOT the ShipSafe AI product. This is the software that ShipSafe AI will later analyze for release readiness.

---

## What it does

- Patient registration
- Doctor management and availability
- Appointment creation, retrieval, and cancellation
- Reminder notifications (with R001 enforcement — cancelled appointments never receive reminders)
- Appointment priority and ETA tracking
- Fully parameterized SQLite persistence

---

## Technology

- Python 3.11+
- Flask 3.x
- SQLite (via Python's built-in `sqlite3`)
- pytest

---

## Quick start

```bash
cd demo_target
pip install -r requirements.txt
python app.py
```

The service starts on `http://localhost:5050`.

---

## Health check

```
GET /health
```

Returns:
```json
{"service": "CareHub Appointment Service", "status": "ok"}
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service health check |
| POST | `/patients` | Register a patient |
| GET | `/patients/<id>` | Get patient details |
| POST | `/doctors` | Create a doctor record |
| GET | `/doctors/<id>/availability` | Check doctor availability |
| POST | `/appointments` | Create an appointment |
| GET | `/appointments/<id>` | Get appointment details |
| POST | `/appointments/<id>/cancel` | Cancel an appointment |
| POST | `/appointments/<id>/reminder` | Send a reminder notification |

---

## Running tests

```bash
cd demo_target
pytest tests/ -v
```

To measure coverage:
```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Release requirements (ShipSafe demo)

See `requirements/CareHub_v2_4_Requirements.md` for the five release requirements (R001–R005) that ShipSafe AI will validate.
