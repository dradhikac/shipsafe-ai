# ShipSafe AI — Requirement Traceability Matrix

**System:** ShipSafe AI (Agentic Release & Regression Guardian)  
**Generated At:** 2026-09-26T14:06:49.416015+00:00  
**Source:** Synthesized from 5 historical IBM Bob 2.0 analysis reports  

---

## 1. Traceability Summary Matrix (Post-Remediation)

| Requirement | Previous | Post-Remediation | Remediation Applied | Validation Tests | Validation State |
|---|---|---|---|---|---|
| **R001** | `FAIL` | **`PASS`** | Restored cancelled-appointment guard check in notification_service.send_reminder() to block reminder generation and DB insertion for cancelled appointments. | `test_cancelled_appointment_does_not_trigger_reminder`<br>`test_cancelled_appointment_reminder_returns_error_message` | `VALIDATED` |
| **R002** | `FAIL` | **`PASS`** | Restored 'eta_minutes' field in appointment_row_to_dict() serializer in demo_target/models.py across POST, GET, and cancellation endpoints. | `test_create_appointment_response_includes_required_fields`<br>`test_get_appointment_response_includes_required_fields`<br>`test_cancel_appointment_response_includes_required_fields` | `VALIDATED` |
| **R003** | `FAIL` | **`PASS`** | Reverted unauthorized 'critical' priority from models.py and db.py; rejected migration 002 in adherence to authoritative R003 specification ('normal', 'high', 'emergency'). | `test_appointment_priority_persisted_normal`<br>`test_appointment_priority_persisted_high`<br>`test_appointment_priority_persisted_emergency`<br>`test_create_appointment_invalid_priority_critical` | `VALIDATED` |
| **R004** | `FAIL` | **`PASS`** | Replaced unsafe raw string concatenation in /appointments/search with parameterized SQLite query db.execute('SELECT * FROM appointments WHERE status = ?', (status,)). | `test_search_appointments_by_status`<br>`test_search_appointments_sql_injection_defense` | `VALIDATED` |
| **R005** | `FAIL` | **`PASS`** | Restored all 7 deleted regression tests across test_notifications.py and test_appointments.py covering cancellation, contract fields, and priority persistence. | `test_cancelled_appointment_does_not_trigger_reminder`<br>`test_cancelled_appointment_reminder_returns_error_message`<br>`test_create_appointment_response_includes_required_fields`<br>`test_cancel_appointment_response_includes_required_fields`<br>`test_appointment_priority_persisted_normal`<br>`test_appointment_priority_persisted_high`<br>`test_appointment_priority_persisted_emergency` | `VALIDATED` |

---

## 2. Detailed Traceability Records

### R001 — Cancelled appointments must not generate reminder notifications.** - When an appointment's status is `cancelled`, any request to send a reminder notification must be rejected. - The system must return an appropriate error response. - No notification record may be persisted for a cancelled appointment.

- **Previous Status:** `FAIL`
- **Post-Remediation Status:** `PASS`
- **Validation State:** `VALIDATED`
- **Remediation Applied:** Restored cancelled-appointment guard check in notification_service.send_reminder() to block reminder generation and DB insertion for cancelled appointments.
- **Validation Tests:** `test_cancelled_appointment_does_not_trigger_reminder`, `test_cancelled_appointment_reminder_returns_error_message`

#### Implementation Evidence
- [`demo_target/services/notification_service.py`]: File demo_target/services/notification_service.py has Git status 'M' — it was modified in this release.
- [`demo_target/services/notification_service.py` lines 25–None (`send_reminder`)]: Line 25: guard condition checks only for 'completed' status. There is no corresponding check for status == 'cancelled'. A cancelled appointment will pass through to the INSERT INTO notifications statement at line 32.
- [`demo_target/services/notification_service.py` lines 25–29 (`send_reminder`)]: Guard checks only 'completed'. The value 'cancelled' is absent from this condition. Execution continues to the INSERT INTO notifications statement at lines 32-35 for any cancelled appointment.

#### Test Coverage & Gaps
- **`test_cancelled_appointment_does_not_trigger_reminder`** in `demo_target/tests/test_notifications.py` (`MISSING`): test_cancelled_appointment_does_not_trigger_reminder confirmed absent: test_notifications.py contains only test_reminder_sent_for_scheduled_appointment, test_reminder_response_contains_message, test_reminder_for_nonexistent_appointment, test_multiple_reminders_for_scheduled_appointment. No test cancels an appointment and then asserts the reminder is blocked.
- **`test_cancelled_appointment_reminder_returns_error_message`** in `demo_target/tests/test_notifications.py` (`MISSING`): test_cancelled_appointment_reminder_returns_error_message confirmed absent from test_notifications.py. No test asserts the 400 response or error text when reminder is attempted on a cancelled appointment.

#### Contributing IBM Bob Findings
- **IMPACT-001** (`impact`, `HIGH`): notification_service.py: cancelled-appointment guard removed — R001 violated
- **TESTGAP-001** (`test_gap`, `HIGH`): Missing test: cancelled appointment must not trigger reminder
- **TESTGAP-002** (`test_gap`, `HIGH`): Missing test: cancelled appointment reminder must return error message
- **CONTRACT-R001** (`contract`, `HIGH`): R001 FAIL — guard condition does not block cancelled appointments

#### Recommended Actions
- **[impact / IMPACT-001]:** Restore the cancelled-appointment guard in send_reminder(): add `if row['status'] == 'cancelled': raise ValueError(...)` before the notification INSERT.
- **[test_gap / TESTGAP-001]:** Restore test_cancelled_appointment_does_not_trigger_reminder in test_notifications.py and fix the guard in send_reminder to check status == 'cancelled'.
- **[test_gap / TESTGAP-002]:** Restore test_cancelled_appointment_reminder_returns_error_message in test_notifications.py.

### R002 — Appointment API responses must include `appointment_id`, `status`, and `eta_minutes`.** - The `POST /appointments` response body must include the fields `appointment_id`, `status`, and `eta_minutes`. - The `GET /appointments/<id>` response body must include the fields `appointment_id`, `status`, and `eta_minutes`. - The `POST /appointments/<id>/cancel` response body must include the fields `appointment_id`, `status`, and `eta_minutes`.

- **Previous Status:** `FAIL`
- **Post-Remediation Status:** `PASS`
- **Validation State:** `VALIDATED`
- **Remediation Applied:** Restored 'eta_minutes' field in appointment_row_to_dict() serializer in demo_target/models.py across POST, GET, and cancellation endpoints.
- **Validation Tests:** `test_create_appointment_response_includes_required_fields`, `test_get_appointment_response_includes_required_fields`, `test_cancel_appointment_response_includes_required_fields`

#### Implementation Evidence
- [`demo_target/models.py`]: File demo_target/models.py has Git status 'M' — it was modified in this release.
- [`demo_target/models.py` lines 27–None (`appointment_row_to_dict`)]: Lines 27-36: appointment_row_to_dict returns keys appointment_id, patient_id, doctor_id, appointment_date, status, priority, created_at. The eta_minutes key is not present.
- [`demo_target/routes/appointments.py` lines 46–None (`get_appointment`)]: routes/appointments.py line 46: GET /appointments/<id> calls appointment_row_to_dict(row) and returns the result — so eta_minutes will be absent from the response.
- [`demo_target/services/appointment_service.py` lines 55–None (`create_appointment`)]: services/appointment_service.py line 55: create_appointment() calls appointment_row_to_dict(row) and returns the result used by POST /appointments — eta_minutes will be absent.
- [`demo_target/models.py` lines 28–36 (`appointment_row_to_dict`)]: Lines 28-36: appointment_row_to_dict returns appointment_id, patient_id, doctor_id, appointment_date, status, priority, created_at — eta_minutes is omitted. The db schema (db.py line 50) still stores eta_minutes.
- [`demo_target/models.py` lines 27–36 (`appointment_row_to_dict`)]: The dict literal contains seven keys: appointment_id, patient_id, doctor_id, appointment_date, status, priority, created_at. The key 'eta_minutes' is absent. All three endpoints (POST /appointments, GET /appointments/<id>, POST /appointments/<id>/cancel) serialise responses via this function, so all three violate R002.

#### Test Coverage & Gaps
- **`test_create_appointment_response_includes_required_fields`** in `demo_target/tests/test_appointments.py` (`MISSING`): test_create_appointment_response_includes_required_fields confirmed absent: test_appointments.py contains 11 tests; none assert the full set of fields returned by the creation response, and none reference eta_minutes.
- **`test_cancel_appointment_response_includes_required_fields`** in `demo_target/tests/test_appointments.py` (`MISSING`): test_cancel_appointment_response_includes_required_fields confirmed absent: test_cancel_appointment_success (lines 81-88) only asserts status == 'cancelled'; no test checks the complete field set of the cancel response.

#### Contributing IBM Bob Findings
- **IMPACT-002** (`impact`, `HIGH`): models.py: appointment_row_to_dict missing eta_minutes field — R002 violated
- **TESTGAP-003** (`test_gap`, `HIGH`): Missing test: appointment creation response includes required fields
- **TESTGAP-004** (`test_gap`, `HIGH`): Missing test: cancel appointment response includes required fields
- **CONTRACT-R002** (`contract`, `HIGH`): R002 FAIL — eta_minutes absent from appointment_row_to_dict

#### Recommended Actions
- **[impact / IMPACT-002]:** Restore the 'eta_minutes': row['eta_minutes'] entry in appointment_row_to_dict() in demo_target/models.py.
- **[test_gap / TESTGAP-003]:** Restore test_create_appointment_response_includes_required_fields in test_appointments.py and restore eta_minutes in appointment_row_to_dict.
- **[test_gap / TESTGAP-004]:** Restore test_cancel_appointment_response_includes_required_fields in test_appointments.py.

### R003 — Appointment priority must be persisted through a versioned database migration.** - The `priority` field must be stored in the `appointments` table. - The field must accept values: `normal`, `high`, `emergency`. - A versioned migration file must exist in the `migrations/` directory that introduces the `priority` column. - The priority value submitted at appointment creation must be retrievable via `GET /appointments/<id>`.

- **Previous Status:** `FAIL`
- **Post-Remediation Status:** `PASS`
- **Validation State:** `VALIDATED`
- **Remediation Applied:** Reverted unauthorized 'critical' priority from models.py and db.py; rejected migration 002 in adherence to authoritative R003 specification ('normal', 'high', 'emergency').
- **Validation Tests:** `test_appointment_priority_persisted_normal`, `test_appointment_priority_persisted_high`, `test_appointment_priority_persisted_emergency`, `test_create_appointment_invalid_priority_critical`
- **Historical Bob Disagreement Resolution:** Database Analyst (DATABASE-001) recommended creating migration 002 to add 'critical'. Contract & Impact Analysts identified 'critical' as unauthorized. Synthesizer resolved in favor of authoritative requirement specification by rejecting 'critical'.

#### Implementation Evidence
- [`demo_target/models.py`]: File demo_target/models.py has Git status 'M' — modified in this release.
- [`demo_target/models.py` lines 41–None (`VALID_PRIORITIES`)]: Line 41: VALID_PRIORITIES = {"normal", "high", "emergency", "critical"} — the value 'critical' is not in the approved set defined by R003.
- [`demo_target/db.py` lines 49–None (`SCHEMA`)]: db.py line 49: CHECK constraint now reads CHECK (priority IN ('normal', 'high', 'emergency', 'critical')), adding 'critical' to the database-level constraint in lockstep with models.py.
- [`demo_target/db.py`]: File demo_target/db.py has Git status 'M' — modified in this release.
- [`demo_target/services/appointment_service.py` lines 6–None (`create_appointment`)]: appointment_service.py line 6: `from models import VALID_PRIORITIES, appointment_row_to_dict` — the service imports VALID_PRIORITIES directly and uses it for input validation on line 22.
- [`demo_target/services/appointment_service.py` lines 22–None (`create_appointment`)]: appointment_service.py line 22: `if priority not in VALID_PRIORITIES:` — validation passes for 'critical' because VALID_PRIORITIES now includes it (models.py line 41).
- [`demo_target/db.py` lines 48–49 (`SCHEMA`)]: Snippet: priority         TEXT    NOT NULL DEFAULT 'normal'
                     CHECK (priority IN ('normal', 'high', 'emergency', 'critical')), | The migration file contains no CHECK constraint on priority and no 'critical' value. The application SCHEMA adds both the CHECK constraint and 'critical' without a corresponding versioned migration. R003 requires values 'normal', 'high', 'emergency' only; 'critical' is an unapproved addition. The migrations/ directory contains only 001_initial_schema.sql — no migration covering this change exists.
- [`demo_target/models.py` lines 41–41 (`VALID_PRIORITIES`)]: Snippet: VALID_PRIORITIES = {"normal", "high", "emergency", "critical"} | The migration file contains no CHECK constraint on priority and no 'critical' value. The application SCHEMA adds both the CHECK constraint and 'critical' without a corresponding versioned migration. R003 requires values 'normal', 'high', 'emergency' only; 'critical' is an unapproved addition. The migrations/ directory contains only 001_initial_schema.sql — no migration covering this change exists.
- [`migrations/001_initial_schema.sql` lines 26–26]: Snippet: priority         TEXT    NOT NULL DEFAULT 'normal', | The migration file contains no CHECK constraint on priority and no 'critical' value. The application SCHEMA adds both the CHECK constraint and 'critical' without a corresponding versioned migration. R003 requires values 'normal', 'high', 'emergency' only; 'critical' is an unapproved addition. The migrations/ directory contains only 001_initial_schema.sql — no migration covering this change exists.
- [`migrations/001_initial_schema.sql`]: migrations/ directory contains only 001_initial_schema.sql — no 002_* migration file exists to introduce the CHECK constraint or the 'critical' value into databases that were initialised incrementally from migration 001.

#### Test Coverage & Gaps
- **`test_appointment_priority_persisted_normal`** in `demo_target/tests/test_appointments.py` (`MISSING`): test_appointment_priority_persisted_normal confirmed absent from test_appointments.py. No test reads back the priority field after creating an appointment with priority='normal'.
- **`test_appointment_priority_persisted_high`** in `demo_target/tests/test_appointments.py` (`MISSING`): test_appointment_priority_persisted_high confirmed absent. No test reads back the priority field after creating an appointment with priority='high'.
- **`test_appointment_priority_persisted_emergency`** in `demo_target/tests/test_appointments.py` (`MISSING`): test_appointment_priority_persisted_emergency confirmed absent. No test reads back the priority field after creating an appointment with priority='emergency'.

#### Contributing IBM Bob Findings
- **IMPACT-003** (`impact`, `HIGH`): models.py: VALID_PRIORITIES expanded with undocumented 'critical' value — R003 violated
- **IMPACT-004** (`impact`, `HIGH`): db.py: SCHEMA CHECK constraint expanded with unauthorised 'critical' priority value — R003 violated
- **IMPACT-008** (`impact`, `MEDIUM`): appointment_service.py imports VALID_PRIORITIES from models.py — now validates against expanded set including 'critical'
- **TESTGAP-005** (`test_gap`, `HIGH`): Missing tests: appointment priority round-trip for normal/high/emergency/critical
- **CONTRACT-R003** (`contract`, `HIGH`): R003 FAIL — priority CHECK constraint + 'critical' value added without migration
- **DATABASE-001** (`database`, `HIGH`): Priority column CHECK constraint and 'critical' value added without versioned migration

#### Recommended Actions
- **[impact / IMPACT-003]:** Remove 'critical' from VALID_PRIORITIES in models.py and from the CHECK constraint in db.py. Revert to {'normal', 'high', 'emergency'} as required by R003.
- **[impact / IMPACT-004]:** Revert the CHECK constraint in db.py SCHEMA to CHECK (priority IN ('normal', 'high', 'emergency')) as required by R003.
- **[impact / IMPACT-008]:** Fixing VALID_PRIORITIES in models.py (IMPACT-003) will automatically fix this downstream impact. No change needed in appointment_service.py itself.
- **[test_gap / TESTGAP-005]:** Restore priority persistence tests for all four valid values (normal, high, emergency, critical) in test_appointments.py.
- **[database / DATABASE-001]:** Create migrations/002_add_priority_critical.sql that adds the CHECK constraint and documents the new 'critical' value. Because SQLite does not support ALTER TABLE ... ADD CONSTRAINT directly, this migration should recreate the appointments table with the new column definition (using the standard SQLite table-rebuild pattern: rename old table, create new table with constraint, copy data, drop old table), then insert '002' into schema_migrations.

### R004 — User-controlled database search input must use parameterized database queries.** - Any database query that incorporates user-supplied input must use parameterized queries (e.g., `?` placeholders with a values tuple). - String concatenation or f-string interpolation directly into SQL query text is prohibited. - This applies to all routes and service functions that accept user input and interact with the database.

- **Previous Status:** `FAIL`
- **Post-Remediation Status:** `PASS`
- **Validation State:** `VALIDATED`
- **Remediation Applied:** Replaced unsafe raw string concatenation in /appointments/search with parameterized SQLite query db.execute('SELECT * FROM appointments WHERE status = ?', (status,)).
- **Validation Tests:** `test_search_appointments_by_status`, `test_search_appointments_sql_injection_defense`

#### Implementation Evidence
- [`demo_target/routes/appointments.py`]: File demo_target/routes/appointments.py has Git status 'M' — modified in this release.
- [`demo_target/routes/appointments.py` lines 76–None (`search_appointments`)]: Line 76: query = "SELECT * FROM appointments WHERE status = '" + status + "'" — user input from request.args is concatenated directly into SQL. The route's own docstring at line 71 explicitly labels this an R004 violation.
- [`demo_target/routes/appointments.py` lines 74–77 (`search_appointments`)]: Lines 74–77 contain the injection. Line 74 captures unsanitized user input: `status = request.args.get("status", "")`. Line 76 builds the SQL string by direct concatenation: `query = "SELECT * FROM appointments WHERE status = '" + status + "'"`. Line 77 executes the constructed query verbatim: `rows = db.execute(query).fetchall()`. There is no parameterization, allow-list validation, or escaping anywhere in this code path.
- [`demo_target/routes/appointments.py` lines 67–78 (`search_appointments`)]: Line 76 concatenates user-supplied input (request.args.get('status')) directly into the SQL query string using string concatenation (+). No parameterized placeholder (?) is used. The function docstring at lines 69-72 explicitly notes: 'R004 violation: user-supplied status is concatenated directly into the SQL query string instead of using a parameterized placeholder.'

#### Test Coverage & Gaps
- **`test_search_appointments_by_status`** in `demo_target/tests/test_appointments.py` (`MISSING_OR_REMOVED`): Confirmed absent from all 5 test files: test_appointments.py (14 tests), test_notifications.py (4), test_patients.py (7), test_doctors.py (7), test_health.py (2). None reference '/appointments/search'.
- ***Unnamed assertion*** in `demo_target/tests` (`MISSING`): Requirement R004 mandates that all database queries use parameterized statements (prepared statements / bind variables) to prevent SQL injection. The search_appointments implementation directly violates R004 by constructing a query via string concatenation instead. Every other query in the codebase (appointment_service.py, notification_service.py, and the other endpoints in routes/appointments.py) correctly uses the `?` placeholder pattern required by R004; this endpoint is the sole non-compliant outlier introduced in the current diff.

#### Contributing IBM Bob Findings
- **IMPACT-005** (`impact`, `HIGH`): routes/appointments.py: new /appointments/search endpoint uses unsafe SQL string concatenation — R004 violated
- **TESTGAP-006** (`test_gap`, `HIGH`): No test for GET /appointments/search endpoint
- **SECURITY-001** (`security`, `CRITICAL`): SQL injection via user-controlled status parameter in /appointments/search
- **CONTRACT-R004** (`contract`, `HIGH`): R004 FAIL — user-controlled status concatenated into SQL

#### Recommended Actions
- **[impact / IMPACT-005]:** Replace string concatenation with a parameterized query: `db.execute("SELECT * FROM appointments WHERE status = ?", (status,))`.
- **[test_gap / TESTGAP-006]:** Add tests for GET /appointments/search in test_appointments.py, including a test that confirms parameterized queries are used.
- **[security / SECURITY-001]:** Replace string concatenation with a parameterized query. Use `db.execute("SELECT * FROM appointments WHERE status = ?", (status,))` so the database driver safely handles the user-supplied value as a literal parameter, not executable SQL.

### R005 — Regression tests must cover cancellation, API contract changes, and appointment priority.** - Tests must verify that a cancelled appointment does not trigger a reminder notification (R001). - Tests must verify that appointment API responses include `appointment_id`, `status`, and `eta_minutes` (R002). - Tests must verify that appointment priority values are persisted and retrievable (R003). - All regression tests must be present in the `tests/` directory and must pass.

- **Previous Status:** `FAIL`
- **Post-Remediation Status:** `PASS`
- **Validation State:** `VALIDATED`
- **Remediation Applied:** Restored all 7 deleted regression tests across test_notifications.py and test_appointments.py covering cancellation, contract fields, and priority persistence.
- **Validation Tests:** `test_cancelled_appointment_does_not_trigger_reminder`, `test_cancelled_appointment_reminder_returns_error_message`, `test_create_appointment_response_includes_required_fields`, `test_cancel_appointment_response_includes_required_fields`, `test_appointment_priority_persisted_normal`, `test_appointment_priority_persisted_high`, `test_appointment_priority_persisted_emergency`

#### Implementation Evidence
- *No production implementation records identified.*

#### Test Coverage & Gaps
- ***Unnamed assertion*** in `demo_target/tests/test_notifications.py` (`MISSING_OR_REMOVED`): File demo_target/tests/test_notifications.py has Git status 'M' — modified in this release.
- ***Unnamed assertion*** in `demo_target/tests/test_appointments.py` (`MISSING_OR_REMOVED`): File demo_target/tests/test_appointments.py has Git status 'M' — modified in this release.
- **`test_cancelled_appointment_does_not_trigger_reminder`** in `demo_target/tests/test_notifications.py` (`MISSING`): test_notifications.py now has 4 tests; 2 covering cancelled-appointment reminder blocking were removed.
- **`test_create_appointment_response_includes_required_fields`** in `demo_target/tests/test_appointments.py` (`MISSING`): test_appointments.py now has 11 tests; 2 response-field tests and 3 priority-persistence tests were removed.

#### Contributing IBM Bob Findings
- **IMPACT-006** (`impact`, `HIGH`): test_notifications.py: R001 regression tests covering cancelled-appointment guard removed — R005 violated
- **IMPACT-007** (`impact`, `HIGH`): test_appointments.py: R002/R003 regression tests for eta_minutes and priority removed — R005 violated
- **TESTGAP-007** (`test_gap`, `MEDIUM`): Regression test suite reduced from 38 to 31: 7 tests deliberately removed
- **CONTRACT-R005** (`contract`, `HIGH`): R005 FAIL — R001/R002/R003 regression tests absent

#### Recommended Actions
- **[impact / IMPACT-006]:** Restore a test that: (1) creates and cancels an appointment, (2) calls POST /appointments/<id>/reminder, (3) asserts HTTP 400 is returned and no notification is created.
- **[impact / IMPACT-007]:** Restore tests that: (1) assert 'eta_minutes' and 'status' appear in all appointment API responses (R002), and (2) verify that a priority submitted at creation matches the value returned by GET /appointments/<id> (R003).
- **[test_gap / TESTGAP-007]:** Restore all 7 removed tests and ensure regression coverage for every changed code path.
