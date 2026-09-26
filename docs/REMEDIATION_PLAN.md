# ShipSafe AI — Remediation Plan

**System:** ShipSafe AI (Agentic Release & Regression Guardian)  
**Generated At:** 2026-09-26T14:07:01.384537+00:00  
**Phase:** Phase 5 — Remediation Planning (Pre-Execution Blueprint)  

---

## Executive Summary

This document provides the definitive, evidence-backed remediation plan to resolve all confirmed regressions identified across the five **IBM Bob 2.0** analysis workstreams. The plan is strictly derived from repository evidence, release requirements, and synthesis reports.

| Remediation ID | Requirement | Priority | Target File | Status |
|---|---|---|---|---|
| **REM-R004** | `R004` | **CRITICAL** | `demo_target/routes/appointments.py` | `VERIFIED` |
| **REM-R001** | `R001` | **HIGH** | `demo_target/services/notification_service.py` | `VERIFIED` |
| **REM-R002** | `R002` | **HIGH** | `demo_target/models.py`, `demo_target/routes/appointments.py`, `demo_target/services/appointment_service.py` | `VERIFIED` |
| **REM-R003** | `R003` | **HIGH** | `demo_target/models.py`, `demo_target/db.py`, `demo_target/services/appointment_service.py` | `VERIFIED` |
| **REM-R005** | `R005` | **HIGH** | `demo_target/tests/test_notifications.py`, `demo_target/tests/test_appointments.py` | `VERIFIED` |

---

## R004 — SQL Injection Fix (Security First)

### Parameterize SQL query in /appointments/search route (`REM-R004`)
- **Requirement ID:** `R004`
- **Priority:** **CRITICAL**
- **Affected Files:** `demo_target/routes/appointments.py`
- **Contributing Findings:** `IMPACT-005`, `TESTGAP-006`, `SECURITY-001`, `CONTRACT-R004`

**Root Cause:**  
User-controlled 'status' query parameter in request.args was concatenated directly into raw SQL string using '+' operator without bind parameters or escaping.

**Current Problem:**  
GET /appointments/search executes raw query 'SELECT * FROM appointments WHERE status = \'' + status + '\'', exposing an exploitable CWE-89 SQL injection vulnerability.

**Required Code Change:**  
Replace string concatenation with parameterized SQL execution using SQLite parameter binding: query = 'SELECT * FROM appointments WHERE status = ?'; rows = db.execute(query, (status,)).fetchall()

**Required Tests:**
- `test_search_appointments_by_status` in `demo_target/tests/test_appointments.py`: Verify searching with valid status query parameter returns matching appointments.
- `test_search_appointments_sql_injection_defense` in `demo_target/tests/test_appointments.py`: Verify malicious SQL payloads (e.g. "' OR '1'='1") are treated as literal strings and do not return unauthorized records.

**Validation Commands:**
```bash
python -m pytest demo_target/tests/test_appointments.py -k search -q
python -m pytest demo_target/tests/test_appointments.py -q
```

**Rollback Consideration:**  
Revert search_appointments() route in demo_target/routes/appointments.py to previous state.

---

## R001 — Notification Guard Restoration

### Restore cancelled-appointment guard check in notification_service.py (`REM-R001`)
- **Requirement ID:** `R001`
- **Priority:** **HIGH**
- **Affected Files:** `demo_target/services/notification_service.py`
- **Contributing Findings:** `IMPACT-001`, `TESTGAP-001`, `TESTGAP-002`, `CONTRACT-R001`

**Root Cause:**  
send_reminder() guard condition checked only for 'completed' status. The check for 'cancelled' status was dropped.

**Current Problem:**  
Cancelled appointments pass through the reminder guard and trigger reminder notifications, inserting unwanted records into the notifications table in violation of R001.

**Required Code Change:**  
Add guard before notification insertion: if row['status'] == 'cancelled': raise ValueError(f"Appointment {appointment_id} is cancelled. Reminders must not be sent for cancelled appointments (R001).")

**Required Tests:**
- `test_cancelled_appointment_does_not_trigger_reminder` in `demo_target/tests/test_notifications.py`: Verify attempting to send a reminder for a cancelled appointment returns HTTP 400 and creates no notification record.
- `test_cancelled_appointment_reminder_returns_error_message` in `demo_target/tests/test_notifications.py`: Verify error response contains an explanatory message citing cancellation.

**Validation Commands:**
```bash
python -m pytest demo_target/tests/test_notifications.py -q
```

**Rollback Consideration:**  
Revert send_reminder() in demo_target/services/notification_service.py.

---

## R002 — API Contract Serialization Restoration

### Restore eta_minutes field in appointment_row_to_dict serialization (`REM-R002`)
- **Requirement ID:** `R002`
- **Priority:** **HIGH**
- **Affected Files:** `demo_target/models.py`, `demo_target/routes/appointments.py`, `demo_target/services/appointment_service.py`
- **Contributing Findings:** `IMPACT-002`, `TESTGAP-003`, `TESTGAP-004`, `CONTRACT-R002`

**Root Cause:**  
The dictionary literal returned by appointment_row_to_dict() in demo_target/models.py omitted the 'eta_minutes' key.

**Current Problem:**  
POST /appointments, GET /appointments/<id>, and POST /appointments/<id>/cancel all omit eta_minutes from their JSON response bodies, violating API contracts.

**Required Code Change:**  
Restore 'eta_minutes': row['eta_minutes'] inside the return dictionary of appointment_row_to_dict() in demo_target/models.py.

**Required Tests:**
- `test_create_appointment_response_includes_required_fields` in `demo_target/tests/test_appointments.py`: Verify POST /appointments response JSON includes appointment_id, status, and eta_minutes.
- `test_get_appointment_response_includes_required_fields` in `demo_target/tests/test_appointments.py`: Verify GET /appointments/<id> response JSON includes appointment_id, status, and eta_minutes.
- `test_cancel_appointment_response_includes_required_fields` in `demo_target/tests/test_appointments.py`: Verify POST /appointments/<id>/cancel response JSON includes appointment_id, status, and eta_minutes.

**Validation Commands:**
```bash
python -m pytest demo_target/tests/test_appointments.py -k fields -q
python -m pytest demo_target/tests/test_appointments.py -q
```

**Rollback Consideration:**  
Revert appointment_row_to_dict() in demo_target/models.py to previous 7-key dictionary.

---

## R003 — Priority & Schema Harmonization (Conflict Resolved)

### Revert unauthorized 'critical' priority and harmonize schema with R003 requirement (`REM-R003`)
- **Requirement ID:** `R003`
- **Priority:** **HIGH**
- **Affected Files:** `demo_target/models.py`, `demo_target/db.py`, `demo_target/services/appointment_service.py`
- **Contributing Findings:** `IMPACT-003`, `IMPACT-004`, `IMPACT-008`, `TESTGAP-005`, `CONTRACT-R003`, `DATABASE-001`

**Root Cause:**  
VALID_PRIORITIES in models.py and SCHEMA in db.py were modified to include 'critical', violating Requirement R003 which explicitly restricts priority to 'normal', 'high', 'emergency'. No compliant migration exists for 'critical'.

**Current Problem:**  
Application accepts unauthorized 'critical' priority, while migrations/001_initial_schema.sql does not define a constraint for it, introducing divergence between fresh databases and migration history.

**Required Code Change:**  
1. In demo_target/models.py, revert VALID_PRIORITIES = {'normal', 'high', 'emergency'}.
2. In demo_target/db.py, revert appointments.priority CHECK constraint to CHECK (priority IN ('normal', 'high', 'emergency')).
3. Reject creation of migration 002 for 'critical'. Preserve 001_initial_schema.sql.
4. Ensure appointment_service.py validates against the approved 3-value set.

**Conflict Resolution Rationale:**  
The Database Analyst (DATABASE-001) recommended creating migration '002_add_priority_critical.sql'. This suggestion is REJECTED by requirement authority: Requirement R003 explicitly states 'The field must accept values: normal, high, emergency'. Creating a migration for 'critical' would formalize an unauthorized requirement deviation. Therefore, remediation must: (1) Remove 'critical' from VALID_PRIORITIES in models.py; (2) Revert CHECK constraint in db.py to ('normal', 'high', 'emergency'); (3) Do NOT create a migration for 'critical'; (4) Preserve baseline migration 001_initial_schema.sql.

**Required Tests:**
- `test_appointment_priority_persisted_normal` in `demo_target/tests/test_appointments.py`: Verify appointment created with priority='normal' persists and matches value from GET.
- `test_appointment_priority_persisted_high` in `demo_target/tests/test_appointments.py`: Verify appointment created with priority='high' persists and matches value from GET.
- `test_appointment_priority_persisted_emergency` in `demo_target/tests/test_appointments.py`: Verify appointment created with priority='emergency' persists and matches value from GET.
- `test_create_appointment_invalid_priority_critical` in `demo_target/tests/test_appointments.py`: Verify appointment creation with unauthorized priority='critical' is rejected with HTTP 400.

**Validation Commands:**
```bash
python -m pytest demo_target/tests/test_appointments.py -k priority -q
python -m pytest demo_target/tests/test_appointments.py -q
```

**Rollback Consideration:**  
Restore expanded VALID_PRIORITIES in models.py and expanded CHECK constraint in db.py.

---

## R005 — Regression Test Suite Restoration

### Restore 7 deleted regression tests across test_notifications.py and test_appointments.py (`REM-R005`)
- **Requirement ID:** `R005`
- **Priority:** **HIGH**
- **Affected Files:** `demo_target/tests/test_notifications.py`, `demo_target/tests/test_appointments.py`
- **Contributing Findings:** `IMPACT-006`, `IMPACT-007`, `TESTGAP-007`, `CONTRACT-R005`

**Root Cause:**  
Seven regression tests were deliberately removed from test suite (reducing test count from 38 to 31) to mask regressions in R001, R002, and R003.

**Current Problem:**  
Passing test suite (31/31) provides a false sense of security while critical requirement behaviors for cancellation, API responses, and priority persistence remain untested.

**Required Code Change:**  
Restore the 7 removed regression tests:
- In test_notifications.py: restore test_cancelled_appointment_does_not_trigger_reminder and test_cancelled_appointment_reminder_returns_error_message.
- In test_appointments.py: restore test_create_appointment_response_includes_required_fields, test_cancel_appointment_response_includes_required_fields, test_appointment_priority_persisted_normal, test_appointment_priority_persisted_high, and test_appointment_priority_persisted_emergency.

**Required Tests:**
- `test_cancelled_appointment_does_not_trigger_reminder` in `demo_target/tests/test_notifications.py`: Cover R001 reminder guard.
- `test_cancelled_appointment_reminder_returns_error_message` in `demo_target/tests/test_notifications.py`: Cover R001 error response.
- `test_create_appointment_response_includes_required_fields` in `demo_target/tests/test_appointments.py`: Cover R002 creation contract.
- `test_cancel_appointment_response_includes_required_fields` in `demo_target/tests/test_appointments.py`: Cover R002 cancellation contract.
- `test_appointment_priority_persisted_normal` in `demo_target/tests/test_appointments.py`: Cover R003 normal priority persistence.
- `test_appointment_priority_persisted_high` in `demo_target/tests/test_appointments.py`: Cover R003 high priority persistence.
- `test_appointment_priority_persisted_emergency` in `demo_target/tests/test_appointments.py`: Cover R003 emergency priority persistence.

**Validation Commands:**
```bash
python -m pytest demo_target/tests/ -q
python -m pytest -q
python -m shipsafe.analyzer.runner --no-coverage
```

**Rollback Consideration:**  
Revert test additions in demo_target/tests/test_notifications.py and demo_target/tests/test_appointments.py.

---

## Safe Execution Order

Remediation must be executed in this operationally safe sequence:

1. **`REM-R004` (Security First):** Parameterizing the `/appointments/search` SQL query closes the active CWE-89 injection vulnerability before any feature adjustments.
2. **`REM-R001` (Notification Guard):** Restores backend logic preventing cancelled appointments from triggering reminder notifications.
3. **`REM-R002` (API Response Contract):** Restores `eta_minutes` in the domain model serializer, ensuring all endpoints return compliant contracts.
4. **`REM-R003` (Priority Schema Alignment):** Removes unauthorized `'critical'` priority from `models.py` and reverts `db.py` constraints, restoring compliance without invalid migrations.
5. **`REM-R005` (Regression Test Restoration):** Re-establishes the 7 missing regression tests across `test_notifications.py` and `test_appointments.py`, validating all fixes.

---

## Validation Strategy

- **Step 1:** Execute unit tests per modified component after each fix.
- **Step 2:** Run `python -m pytest demo_target/tests/ -q` to verify CareHub target suite passes with 38+ tests.
- **Step 3:** Run `python -m pytest -q` across the entire workspace.
- **Step 4:** Run deterministic re-analysis via `python -m shipsafe.analyzer.runner --no-coverage` to confirm zero remaining violations.

---

## Rollback Considerations

Every remediation step is isolated and reversible at the file/workspace level:
- `REM-R004`: Revert query string in `demo_target/routes/appointments.py`.
- `REM-R001`: Revert guard in `demo_target/services/notification_service.py`.
- `REM-R002`: Revert serializer dictionary in `demo_target/models.py`.
- `REM-R003`: Restore previous dictionary set in `models.py` and SCHEMA in `db.py`.
- `REM-R005`: Revert newly added test functions in test files.