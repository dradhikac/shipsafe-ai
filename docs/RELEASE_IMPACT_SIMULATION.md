# ShipSafe AI — Release Impact Simulation

**System:** ShipSafe AI (Agentic Release & Regression Guardian)  
**Generated At:** 2026-09-26T14:06:56.200835+00:00  
**Methodology:** Evidence-Based Release Blast Radius Mapping (Zero Predictive Guesswork)  
**Release Status:** `RELEASE_BLOCKED`  

---

## 1. Release Impact Summary

| Metric | Count | Evidence Source |
|---|---|---|
| **Affected Components** | **6** | Git diff & dependency call-chains |
| **Affected Workflows** | **6** | Requirement coverage mapping |
| **Regression Paths** | **5** | End-to-end component vulnerability chains |
| **Critical Findings** | **1** | Security Analyst (`SECURITY-001`) |
| **High Severity Findings** | **19** | Impact, Contract, Database & Test Gap Analysts |
| **Requirements At Risk** | **5 of 5** | All active requirements non-compliant |
| **Security Vulnerabilities** | **1** | CWE-89 SQL injection in search endpoint |
| **Missing Regression Tests** | **7** | Systematic test removal detected |

---

## 2. Highest-Risk Component

**Component:** `Appointment Search & Query Path` (`demo_target/routes/appointments.py`)  
**Deterministic Risk Rationale:** Component 'Appointment Search & Query Path' is determined as highest-risk because it contains 1 confirmed CRITICAL severity finding (SECURITY-001); exposes an unauthenticated CWE-89 SQL injection vulnerability; endpoint has 0% regression test coverage (TESTGAP-006); involves 4 HIGH severity findings.  
**Contributing Findings:** `IMPACT-002, IMPACT-005, TESTGAP-006, SECURITY-001, CONTRACT-R004`  

---

## 3. Affected Components

### Appointment Search & Query Path (`COMP-SEARCH-API`)
- **Files:** `demo_target/routes/appointments.py`
- **Requirements:** `R002, R004`
- **Supporting Agents:** `contract, impact, security, test_gap`
- **Related Findings (5):** `IMPACT-002, IMPACT-005, TESTGAP-006, SECURITY-001, CONTRACT-R004`

### Notification Service (`COMP-NOTIFICATION`)
- **Files:** `demo_target/services/notification_service.py`
- **Requirements:** `R001`
- **Supporting Agents:** `contract, impact, test_gap`
- **Related Findings (3):** `IMPACT-001, TESTGAP-001, CONTRACT-R001`

### Domain Models & Serialization (`COMP-MODELS`)
- **Files:** `demo_target/models.py`
- **Requirements:** `R002, R003`
- **Supporting Agents:** `contract, database, impact, test_gap`
- **Related Findings (8):** `IMPACT-002, IMPACT-003, IMPACT-008, TESTGAP-003, TESTGAP-005, CONTRACT-R002, CONTRACT-R003, DATABASE-001`

### Database Schema & Migrations (`COMP-DATABASE`)
- **Files:** `demo_target/db.py, migrations/001_initial_schema.sql`
- **Requirements:** `R003`
- **Supporting Agents:** `contract, database, impact, test_gap`
- **Related Findings (5):** `IMPACT-003, IMPACT-004, TESTGAP-005, CONTRACT-R003, DATABASE-001`

### Appointment Service (`COMP-APPOINTMENT-SVC`)
- **Files:** `demo_target/services/appointment_service.py`
- **Requirements:** `R002, R003`
- **Supporting Agents:** `impact`
- **Related Findings (2):** `IMPACT-002, IMPACT-008`

### Regression Test Harness (`COMP-TEST-SUITE`)
- **Files:** `demo_target/tests/test_notifications.py, demo_target/tests/test_appointments.py`
- **Requirements:** `R001, R002, R003, R004, R005`
- **Supporting Agents:** `contract, impact, test_gap`
- **Related Findings (10):** `IMPACT-006, IMPACT-007, TESTGAP-001, TESTGAP-002, TESTGAP-003, TESTGAP-004, TESTGAP-005, TESTGAP-006, TESTGAP-007, CONTRACT-R005`

---

## 4. Affected Application Workflows

### `WF-REMINDER`: Appointment Reminder Delivery
- **Status:** `AFFECTED`
- **Description:** Triggering reminder notifications for scheduled appointments while blocking reminders for cancelled appointments.
- **Related Requirements:** `R001, R005`
- **Impacting Findings:** `CONTRACT-R001, CONTRACT-R005, IMPACT-001, IMPACT-006, IMPACT-007, TESTGAP-001, TESTGAP-002, TESTGAP-007`

### `WF-API-SERIALIZATION`: Appointment API Response Serialization
- **Status:** `AFFECTED`
- **Description:** Serializing appointment records with appointment_id, status, and eta_minutes for API callers.
- **Related Requirements:** `R002, R005`
- **Impacting Findings:** `CONTRACT-R002, CONTRACT-R005, IMPACT-002, IMPACT-006, IMPACT-007, TESTGAP-003, TESTGAP-004, TESTGAP-007`

### `WF-PRIORITY-PERSISTENCE`: Appointment Priority & Persistence
- **Status:** `AFFECTED`
- **Description:** Validating priority values ('normal', 'high', 'emergency') and persisting through versioned schema.
- **Related Requirements:** `R003, R005`
- **Impacting Findings:** `CONTRACT-R003, CONTRACT-R005, DATABASE-001, IMPACT-003, IMPACT-004, IMPACT-006, IMPACT-007, IMPACT-008, TESTGAP-005, TESTGAP-007`

### `WF-SEARCH`: Appointment Search by Status
- **Status:** `AFFECTED`
- **Description:** Executing database queries for appointments filtered by status query parameter.
- **Related Requirements:** `R004`
- **Impacting Findings:** `CONTRACT-R004, IMPACT-005, SECURITY-001, TESTGAP-006`

### `WF-CANCELLATION`: Appointment Cancellation & Followup
- **Status:** `AFFECTED`
- **Description:** Cancelling an appointment, receiving updated status/eta_minutes, and preventing subsequent reminders.
- **Related Requirements:** `R001, R002, R005`
- **Impacting Findings:** `CONTRACT-R001, CONTRACT-R002, CONTRACT-R005, IMPACT-001, IMPACT-002, IMPACT-006, IMPACT-007, TESTGAP-001, TESTGAP-002, TESTGAP-003, TESTGAP-004, TESTGAP-007`

### `WF-REGRESSION-HARNESS`: Release Regression Testing
- **Status:** `AFFECTED`
- **Description:** Automated regression testing ensuring code changes do not break existing requirements.
- **Related Requirements:** `R005`
- **Impacting Findings:** `CONTRACT-R005, IMPACT-006, IMPACT-007, TESTGAP-007`

---

## 5. Evidence-Backed Regression Paths

### `REG-PATH-001` — Cancelled appointment reminder guard suppression bypass (R001)
*Cancelled appointments generate unsolicited reminder notifications and persist records to the database.*

**Causal Chain:**
```text
[1] demo_target/services/notification_service.py -> Changed guard condition (line 25)
[2] Notification persistence logic -> Execution flows through to notification INSERT
[3] Reminder delivery workflow -> Cancelled appointments receive reminder notifications
[4] Requirement R001 -> Acceptance criteria violated
```
- **Supporting Findings:** `IMPACT-001, TESTGAP-001, TESTGAP-002, CONTRACT-R001`

### `REG-PATH-002` — Appointment response serialization omission of eta_minutes (R002)
*API client integrations expecting eta_minutes will experience breaking response contract failures.*

**Causal Chain:**
```text
[1] demo_target/models.py -> appointment_row_to_dict() dropped eta_minutes (line 27)
[2] demo_target/routes/appointments.py -> GET /appointments/<id> and cancellation routes call serializer
[3] demo_target/services/appointment_service.py -> create_appointment() calls serializer
[4] API consumer contract -> All appointment API responses omit required eta_minutes field
```
- **Supporting Findings:** `IMPACT-002, TESTGAP-003, TESTGAP-004, CONTRACT-R002`

### `REG-PATH-003` — Unapproved priority value and database migration divergence (R003)
*Schema drift between fresh installs and migrated environments; application accepts priority not in specification.*

**Causal Chain:**
```text
[1] demo_target/models.py -> VALID_PRIORITIES expanded with 'critical' (line 41)
[2] demo_target/db.py -> In-memory SCHEMA CHECK constraint modified (line 49)
[3] migrations/001_initial_schema.sql -> Migration file does not include CHECK constraint or 'critical'
[4] Database persistence -> Environments diverge depending on initialization path; unapproved priority accepted
```
- **Supporting Findings:** `IMPACT-003, IMPACT-004, IMPACT-008, TESTGAP-005, CONTRACT-R003, DATABASE-001`

### `REG-PATH-004` — Unparameterized user query parameter directly concatenated into SQL (R004)
*Remote attackers can manipulate SQL queries, bypass status filtering, and exfiltrate appointment database records.*

**Causal Chain:**
```text
[1] demo_target/routes/appointments.py -> status parameter read from request.args (line 74)
[2] Raw query concatenation -> status concatenated via + operator without escaping (line 76)
[3] SQLite driver -> db.execute() executes raw unparameterized query (line 77)
[4] Application security boundary -> Critical CWE-89 SQL injection vulnerability exposed
```
- **Supporting Findings:** `IMPACT-005, TESTGAP-006, SECURITY-001, CONTRACT-R004`

### `REG-PATH-005` — Systematic removal of 7 regression tests covering changed behavior (R005)
*Passing CI test suite conceals 4 requirement regressions due to targeted test removal.*

**Causal Chain:**
```text
[1] demo_target/tests/test_notifications.py -> 2 tests removed (cancelled reminder blocking & error message)
[2] demo_target/tests/test_appointments.py -> 5 tests removed (eta_minutes response & priority persistence)
[3] Pytest execution harness -> Suite reports 31/31 passing tests despite functional defects
[4] Quality gate / Release validation -> False sense of release readiness masked by test deletion
```
- **Supporting Findings:** `IMPACT-006, IMPACT-007, TESTGAP-007, CONTRACT-R005`

---

## 6. Required Remediation Actions

- **[R001 / IMPACT-001]:** Restore the cancelled-appointment guard in send_reminder(): add `if row['status'] == 'cancelled': raise ValueError(...)` before the notification INSERT.
- **[R001 / TESTGAP-001]:** Restore test_cancelled_appointment_does_not_trigger_reminder in test_notifications.py and fix the guard in send_reminder to check status == 'cancelled'.
- **[R001 / TESTGAP-002]:** Restore test_cancelled_appointment_reminder_returns_error_message in test_notifications.py.
- **[R002 / IMPACT-002]:** Restore the 'eta_minutes': row['eta_minutes'] entry in appointment_row_to_dict() in demo_target/models.py.
- **[R002 / TESTGAP-003]:** Restore test_create_appointment_response_includes_required_fields in test_appointments.py and restore eta_minutes in appointment_row_to_dict.
- **[R002 / TESTGAP-004]:** Restore test_cancel_appointment_response_includes_required_fields in test_appointments.py.
- **[R003 / DATABASE-001]:** Create migrations/002_add_priority_critical.sql that adds the CHECK constraint and documents the new 'critical' value. Because SQLite does not support ALTER TABLE ... ADD CONSTRAINT directly, this migration should recreate the appointments table with the new column definition (using the standard SQLite table-rebuild pattern: rename old table, create new table with constraint, copy data, drop old table), then insert '002' into schema_migrations.
- **[R003 / IMPACT-003]:** Remove 'critical' from VALID_PRIORITIES in models.py and from the CHECK constraint in db.py. Revert to {'normal', 'high', 'emergency'} as required by R003.
- **[R003 / IMPACT-004]:** Revert the CHECK constraint in db.py SCHEMA to CHECK (priority IN ('normal', 'high', 'emergency')) as required by R003.
- **[R003 / IMPACT-008]:** Fixing VALID_PRIORITIES in models.py (IMPACT-003) will automatically fix this downstream impact. No change needed in appointment_service.py itself.
- **[R003 / TESTGAP-005]:** Restore priority persistence tests for all four valid values (normal, high, emergency, critical) in test_appointments.py.
- **[R004 / IMPACT-005]:** Replace string concatenation with a parameterized query: `db.execute("SELECT * FROM appointments WHERE status = ?", (status,))`.
- **[R004 / SECURITY-001]:** Replace string concatenation with a parameterized query. Use `db.execute("SELECT * FROM appointments WHERE status = ?", (status,))` so the database driver safely handles the user-supplied value as a literal parameter, not executable SQL.
- **[R004 / TESTGAP-006]:** Add tests for GET /appointments/search in test_appointments.py, including a test that confirms parameterized queries are used.
- **[R005 / IMPACT-006]:** Restore a test that: (1) creates and cancels an appointment, (2) calls POST /appointments/<id>/reminder, (3) asserts HTTP 400 is returned and no notification is created.
- **[R005 / IMPACT-007]:** Restore tests that: (1) assert 'eta_minutes' and 'status' appear in all appointment API responses (R002), and (2) verify that a priority submitted at creation matches the value returned by GET /appointments/<id> (R003).
- **[R005 / TESTGAP-007]:** Restore all 7 removed tests and ensure regression coverage for every changed code path.

---

## 7. Evidence Sources & Auditability

All mappings in this simulation are derived from confirmed records generated by the five **IBM Bob 2.0** analysis agents:
- `reports/agents/impact_report.json`
- `reports/agents/test_gap_report.json`
- `reports/agents/security_report.json`
- `reports/agents/contract_report.json`
- `reports/agents/database_report.json`

Zero subjective predictions or probabilistic guesses are used.