# ShipSafe AI — Demo Release Documentation

This document describes the controlled "bad release" test fixture for the ShipSafe AI hackathon demo.
It records what the baseline does, what each deliberate regression changes, and how to apply and reverse the fixture.

**This document describes a test fixture, not a production incident.**
It does not claim that ShipSafe has already detected these issues.
Specific metrics (test counts, coverage percentages) will come from actual tool execution during the demo.

---

## Baseline Behavior

The CareHub Appointment Service baseline (commit `5f95cd1`) satisfies all five release requirements:

| File | What it does |
|---|---|
| `services/notification_service.py` | Guards `send_reminder` — raises `ValueError` when `status == "cancelled"` (R001) |
| `models.py` — `appointment_row_to_dict` | Returns `appointment_id`, `status`, and `eta_minutes` in every response (R002) |
| `db.py` SCHEMA | `appointments` table has `priority` column; `migrations/001_initial_schema.sql` exists as the versioned baseline migration (R003) |
| `services/appointment_service.py` | Inserts `priority` via parameterized query (R004 — no string concat) |
| `routes/appointments.py` | All DB queries use `?` placeholders (R004) |
| `tests/test_notifications.py` | Covers R001 — `test_cancelled_appointment_does_not_trigger_reminder` |
| `tests/test_appointments.py` | Covers R002 — `test_create_appointment_response_includes_required_fields`, `test_cancel_appointment_response_includes_required_fields`; covers R003 — `test_appointment_priority_persisted_*` |

Baseline test count: **38 passed, 0 failed**.

---

## Deliberate Regressions

### R001 — Notification Guard Broken

**Requirement:** Cancelled appointments must not generate reminder notifications.

**Baseline implementation:**
`notification_service.py` [`send_reminder`](demo_target/services/notification_service.py) checks:
```python
if row["status"] == "cancelled":
    raise ValueError(...)
```

**Regression introduced:**
The condition is changed to check `"completed"` instead of `"cancelled"`:
```python
if row["status"] == "completed":
    raise ValueError(...)
```

**Why this is realistic:**
A developer refactoring reminder rules might intend to block only "completed" appointments (e.g., after the appointment has passed) and accidentally removes the "cancelled" guard in the same edit.
The code compiles, tests still run, and no syntax error is visible in a quick diff review.

**Changed file:** `demo_target/services/notification_service.py`

**Expected evidence a ShipSafe agent would find:**
- Code pattern at `send_reminder` — the cancelled guard is absent; the condition reads `"completed"` not `"cancelled"`
- R001 requirement gap: the acceptance criterion "when status is cancelled, reminder must be rejected" is no longer satisfied

**Existing tests that become insufficient:**
- `test_cancelled_appointment_does_not_trigger_reminder` — **removed** by R005 regression (see below)
- `test_cancelled_appointment_reminder_returns_error_message` — **removed** by R005 regression

---

### R002 — API Response Missing `eta_minutes`

**Requirement:** Appointment API responses must include `appointment_id`, `status`, and `eta_minutes`.

**Baseline implementation:**
`models.py` [`appointment_row_to_dict`](demo_target/models.py) returns:
```python
{
    "appointment_id": row["id"],
    "patient_id": ...,
    "doctor_id": ...,
    "appointment_date": ...,
    "status": row["status"],
    "priority": row["priority"],
    "eta_minutes": row["eta_minutes"],   # ← present at baseline
    "created_at": ...,
}
```

**Regression introduced:**
`eta_minutes` is removed from the dict:
```python
def appointment_row_to_dict(row):
    return {
        "appointment_id": row["id"],
        ...
        "status": row["status"],
        "priority": row["priority"],
        "created_at": row["created_at"],   # eta_minutes absent
    }
```

**Why this is realistic:**
A developer "cleaning up" the serialization helper might decide `eta_minutes` is internal and drop it, not realising it is an API contract field.
All three endpoints (`POST /appointments`, `GET /appointments/<id>`, `POST /appointments/<id>/cancel`) share this helper, so all three break simultaneously.
The endpoints continue to return 200/201 with valid JSON — no error is visible without checking the field list.

**Changed file:** `demo_target/models.py`

**Expected evidence a ShipSafe agent would find:**
- `appointment_row_to_dict` in `models.py` — `eta_minutes` key absent
- R002 requirement gap across all three endpoint response paths
- The field is still present in the database SCHEMA — it is only missing from the serialized response

**Existing tests that become insufficient:**
- `test_create_appointment_response_includes_required_fields` — **removed** by R005 regression
- `test_cancel_appointment_response_includes_required_fields` — **removed** by R005 regression

---

### R003 — Priority Schema Evolution Without Migration

**Requirement:** Appointment priority must be persisted through a versioned database migration.

**Context:**
The baseline `migrations/001_initial_schema.sql` defines the `priority` column as:
```sql
priority  TEXT  NOT NULL DEFAULT 'normal'
```
There is no CHECK constraint and the accepted value set (`normal`, `high`, `emergency`) is expressed only in `models.py` `VALID_PRIORITIES` — not in the schema.
The `db.py` SCHEMA constant mirrors this unconstrained definition.

**Regression introduced:**
The bad release extends the priority value set by adding `"critical"` as a fourth valid priority (a triage-priority feature).
Two files change:

1. **`models.py` `VALID_PRIORITIES`** — gains `"critical"`:
   ```python
   VALID_PRIORITIES = {"normal", "high", "emergency", "critical"}
   ```

2. **`db.py` SCHEMA** — the `priority` column gains an explicit `CHECK` constraint that documents and enforces the new value set:
   ```sql
   priority  TEXT  NOT NULL DEFAULT 'normal'
                   CHECK (priority IN ('normal', 'high', 'emergency', 'critical')),
   ```

**No migration file is created** — `migrations/002_add_priority_critical.sql` does not exist.

**Why this is realistic:**
A developer implements a "critical" triage priority feature by updating the validation set in `models.py` and tightening the schema constraint in `db.py`.
They test it against a fresh database (where `CREATE TABLE IF NOT EXISTS` applies the new constraint immediately) and it works.
They forget to write a migration that:
- `ALTER TABLE` or otherwise records the new CHECK constraint for existing databases
- Documents the new allowed value in the migration history

Any existing production database created from `001_initial_schema.sql` has no `CHECK` constraint on `priority` and has no record that `"critical"` is a valid value.
The schema definition in `db.py` and the migration history in `migrations/` are now inconsistent.

**Changed files:**
- `demo_target/models.py` (also carries the R002 regression — `eta_minutes` removed)
- `demo_target/db.py`

**Expected evidence a Database Analyst would find:**
- `db.py` SCHEMA: `priority` column has `CHECK (priority IN ('normal', 'high', 'emergency', 'critical'))` — constraint not present in migration 001
- `models.py` `VALID_PRIORITIES`: `"critical"` added — application accepts and persists a value not present in migration history
- `migrations/001_initial_schema.sql`: `priority TEXT NOT NULL DEFAULT 'normal'` — no CHECK constraint, no `critical` value
- `migrations/` directory: only `001_initial_schema.sql` — no `002_*` migration file to introduce the constraint or the new value

**Existing tests that become insufficient:**
The R005 regression removes the three priority round-trip tests (`test_appointment_priority_persisted_normal/high/emergency`).
No test covers `"critical"` priority persistence.

---

### R004 — Unsafe SQL Construction

**Requirement:** User-controlled database search input must use parameterized queries.

**Baseline implementation:**
All database queries in the baseline use `?` placeholders, e.g.:
```python
db.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
```

**Regression introduced:**
A new search endpoint is added to `routes/appointments.py`:
```python
@appointments_bp.get("/appointments/search")
def search_appointments():
    status = request.args.get("status", "")
    db = get_db()
    query = "SELECT * FROM appointments WHERE status = '" + status + "'"
    rows = db.execute(query).fetchall()
    return jsonify([appointment_row_to_dict(r) for r in rows]), 200
```

The `status` parameter is a user-controlled query string value concatenated directly into the SQL string.

**Why this is realistic:**
Search and filter endpoints frequently appear as quick additions ("just a search by status").
String concatenation is a common shortcut when a developer is thinking about the query result rather than the query construction.
The endpoint works correctly for valid status values, passing manual smoke-testing.
The SQL injection risk is not visible in the test output.

**Changed file:** `demo_target/routes/appointments.py`

**Expected evidence a ShipSafe agent would find:**
- `routes/appointments.py` `search_appointments` function: string concatenation `"... status = '" + status + "'"` where `status` comes from `request.args.get("status", "")`
- User-controlled input flows directly into SQL without parameterization
- R004 requirement violation: explicit prohibition on string concatenation into SQL

**Existing tests that become insufficient:**
No test covers the `/appointments/search` endpoint at baseline or in the bad release.
The unsafe construction is not caught by any existing test.

---

### R005 — Missing Regression Test Coverage

**Requirement:** Regression tests must cover cancellation, API contract changes, and appointment priority.

**Regression introduced:**
The following tests are removed from the test files:

**From `test_notifications.py`** (R001 coverage):
- `test_cancelled_appointment_does_not_trigger_reminder`
- `test_cancelled_appointment_reminder_returns_error_message`

**From `test_appointments.py`** (R002 and R003 coverage):
- `test_create_appointment_response_includes_required_fields`
- `test_cancel_appointment_response_includes_required_fields`
- `test_appointment_priority_persisted_normal`
- `test_appointment_priority_persisted_high`
- `test_appointment_priority_persisted_emergency`

**Why this is realistic:**
Regression tests for a specific scenario are often placed immediately adjacent to the code they test.
When a developer modifies a feature (e.g., the reminder logic or the response serializer), they may remove or skip tests they consider "no longer relevant to the new design" — especially under time pressure.
The test file remains syntactically valid and passes for the remaining tests.
The regression scenario is simply absent.

**Changed files:**
- `demo_target/tests/test_notifications.py`
- `demo_target/tests/test_appointments.py`

**Expected evidence a ShipSafe agent would find:**
- `test_notifications.py`: `test_cancelled_appointment_does_not_trigger_reminder` absent
- `test_appointments.py`: `test_create_appointment_response_includes_required_fields` absent, priority tests absent
- R001, R002, R003 requirement gaps: the required acceptance-criteria tests are missing
- Changed behavior (notification guard, serializer, schema) has no corresponding regression coverage

---

## Files Changed by the Demo Release

| File | Regressions |
|---|---|
| `demo_target/services/notification_service.py` | R001 |
| `demo_target/models.py` | R002, R003 |
| `demo_target/db.py` | R003 |
| `demo_target/routes/appointments.py` | R004 |
| `demo_target/tests/test_notifications.py` | R005 |
| `demo_target/tests/test_appointments.py` | R005 |

`demo_target/services/appointment_service.py` is **unchanged** in the bad release — the service already delegates priority validation to `VALID_PRIORITIES` from `models.py`, so it automatically accepts `"critical"` when that set is updated. No separate change is needed there.

Files NOT changed: all `shipsafe/` files, all other `demo_target/` files, `requirements/`, `docs/`, `.bob/`.

---

## Expected Test Behavior After the Bad Release

The bad release was designed so that the remaining tests continue to pass.
The regressions are silent — the test suite is green but the coverage of the changed behavior is absent.

**Expected bad-release test result: all remaining tests pass.**

This is intentional and is the most realistic demo scenario: a release that looks safe from the test output alone but has real problems detectable only by a systematic analysis.

The following tests that existed at baseline no longer exist in the bad release:

| Removed test | Was covering |
|---|---|
| `test_cancelled_appointment_does_not_trigger_reminder` | R001 |
| `test_cancelled_appointment_reminder_returns_error_message` | R001 |
| `test_create_appointment_response_includes_required_fields` | R002 |
| `test_cancel_appointment_response_includes_required_fields` | R002 |
| `test_appointment_priority_persisted_normal` | R003 |
| `test_appointment_priority_persisted_high` | R003 |
| `test_appointment_priority_persisted_emergency` | R003 |

---

## How to Apply the Demo Release

```
python scripts/apply_demo_release.py
```

The script:
1. Verifies the repository starts from the expected clean baseline commit.
2. Refuses to run if the working tree contains unrelated modifications.
3. Writes the exact bad-release content to each of the seven changed files.
4. Reports exactly which files it changed.
5. Does not touch ShipSafe engine files.

---

## How to Reset the Demo

```
python scripts/reset_demo.py
```

The script:
1. Runs `git checkout HEAD -- <file>` for each of the six changed files.
2. Removes any generated artifacts (none in the current demo).
3. Runs `pytest demo_target/tests/ -q` to verify the baseline.
4. Reports success only when all baseline tests pass.

---

## Repeatability

The demo cycle is fully repeatable:

```
python scripts/apply_demo_release.py   # introduce regressions
git diff --stat                        # observe changed files
python -m shipsafe.analyzer.runner     # engine sees the change state
python scripts/reset_demo.py           # restore baseline
python -m pytest demo_target/tests/ -q # verify 38 tests pass
```

The scripts use deterministic file writes and Git checkout — no regex, no fragile patching.
Running the cycle multiple times produces the same result each time.

---

## What ShipSafe Should Observe After the Bad Release

At the time this fixture is created, the deterministic engine (`shipsafe.analyzer.runner`) will report:

- Changed files from `git status`
- Current test counts and coverage from `pytest`
- Loaded requirements (R001–R005)
- No findings (findings are added by the five analysis agents, not the deterministic engine)

The five Bob analysis agents, when run in the next phase of the demo, are expected to produce the following findings by reading actual code in the changed files:

| Finding | Severity | Requirement |
|---|---|---|
| Cancelled appointment triggers reminder (guard checks "completed" not "cancelled") | High | R001 |
| `eta_minutes` absent from all appointment API responses | High | R002 |
| `priority` column gains CHECK constraint + `"critical"` value; no migration | High | R003 |
| Unsafe SQL string concatenation with user-controlled `status` param | Critical | R004 |
| No regression tests for R001, R002, or R003 changed behavior | High | R005 |

These findings are anticipated based on the known content of the bad release.
They are not confirmed by the deterministic engine alone.
Confirmation requires the analysis agents to inspect the actual code and produce evidence-backed reports.

---

## Notes

- `migrations/001_initial_schema.sql` is a committed baseline artifact.
  It exists to give the Database Analyst concrete evidence that a migration system is in use and that the new `urgency_level` column has no corresponding migration.
  It must NOT be deleted by `reset_demo.py`.

- The demo does not introduce any `migrations/002_*` file.
  The absence of this file is the R003 finding.

- The bad release does not make any existing tests fail.
  A green test suite with missing regression coverage is exactly the problem ShipSafe is designed to catch.
