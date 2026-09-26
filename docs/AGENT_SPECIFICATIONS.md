# ShipSafe AI — Agent Specifications

This document defines the five independent analysis agents used in the ShipSafe AI multi-agent release workflow.
Each agent runs as a focused Bob subagent with a narrow, isolated mission.
All five agents are read-only with respect to application source code.

These specifications are derived from the project contract in `AGENTS.md`,
the project rules in `.bob/rules/shipsafe-rules.md`, and the demo scenario in `docs/DEMO_SCENARIO.md`.

---

## Common Constraints (All Agents)

- **Read-only**: No agent may modify `demo_target/` source files, test files, migration files, or configuration during analysis.
- **Evidence-first**: Every CONFIRMED finding must have at least one concrete evidence record with a real file path, function name, or command output.
- **Isolated output**: Each agent writes only its own assigned report file. No agent writes to another agent's report or to `reports/latest_release_report.json`.
- **No invented findings**: Findings not traceable to actual repository evidence must not be marked CONFIRMED.
- **Schema compliance**: All reports must conform to `shipsafe/schemas/report_schema.json`.
- **Valid requirement IDs**: Any `requirement_id` in a finding must be one of `R001`–`R005`.

---

## Agent 1 — Impact Analyst

### Purpose

Determine which repository components are affected by the current change.
Establish the blast radius of the release before any other agent begins analysis.

### Input

- `reports/latest_release_report.json` (base analysis — provides changed file list, git state, requirements)
- All files listed in `git.changed_files`
- The full `demo_target/` source tree (for import and call-chain tracing)

### Allowed Context

- Any file in `demo_target/` may be read for import and dependency tracing
- `shipsafe/` source is not part of the analysis scope

### Prohibited Modifications

- Must not modify any file in `demo_target/`
- Must not write to any report file other than `reports/agents/impact_report.json`

### Detection Responsibilities

For the controlled demo release, the Impact Analyst must:

1. Identify all six changed files from `git diff`
2. Trace the call chain from changed routes → services → notification behavior
3. Identify which tests previously exercised the changed code paths
4. Identify which modules import from changed files
5. Note the `appointment_row_to_dict` function as a shared serialization helper used by multiple routes
6. Note the `VALID_PRIORITIES` set as a shared domain constant used by the service layer
7. Identify that the `/appointments/search` endpoint is a new route with no existing test coverage

### Required Evidence Per Finding

Each finding must include:
- `file_path`: the actual repository path of the affected file
- `symbol`: the function, class, or constant involved
- Evidence type `GIT_CHANGE` for directly changed files
- Evidence type `CODE` for dependency chain discoveries

### Expected Output Path

`reports/agents/impact_report.json`

### Finding Structure

```json
{
  "finding_id": "IMPACT-001",
  "severity": "HIGH",
  "finding_status": "CONFIRMED",
  "title": "...",
  "description": "...",
  "affected_files": ["demo_target/..."],
  "evidence": [{"evidence_type": "GIT_CHANGE", "file_path": "...", ...}],
  "requirement_id": "R001",
  "recommended_action": "...",
  "source_agent": "impact"
}
```

### Severity Guidance

- HIGH: changed file is part of a requirement-affecting code path
- MEDIUM: changed file affects untested behavior
- LOW: changed file is peripheral (e.g., tests only)
- INFO: observation with no direct impact

### False-Positive Constraints

Must not report a file as "affected" unless it imports from a changed module
or is explicitly listed in the Git diff.
Must not extrapolate impact beyond what the import graph supports.

---

## Agent 2 — Test Gap Analyst

### Purpose

Determine whether the changed behavior introduced in the bad release is
adequately covered by the remaining test suite.
Identify specific missing regression scenarios and map them to requirements.

### Input

- `reports/latest_release_report.json` (provides test counts and changed file list)
- All files in `demo_target/tests/`
- All changed source files from the Git diff

### Allowed Context

- Any test file in `demo_target/tests/` may be read
- Any source file in `demo_target/` may be read

### Prohibited Modifications

- Must not write or modify any test file
- Must not write to any report file other than `reports/agents/test_gap_report.json`

### Detection Responsibilities

For the controlled demo release, the Test Gap Analyst must:

1. Read `test_notifications.py` and identify which R001-related tests were present at baseline but are now absent
2. Read `test_appointments.py` and identify which R002/R003-related tests were present at baseline but are now absent
3. Verify that `test_cancelled_appointment_does_not_trigger_reminder` does not exist in the current test suite
4. Verify that `test_create_appointment_response_includes_required_fields` does not exist in the current test suite
5. Verify that the three `test_appointment_priority_persisted_*` tests do not exist
6. Confirm that no test exercises `GET /appointments/search` (R004 gap)
7. Confirm that no test attempts to send a reminder to a cancelled appointment (R001 gap)

### Required Evidence Per Finding

- `test_name`: the name of the absent or insufficient test
- `file_path`: the test file that should contain the coverage
- `symbol`: the changed function or route being analyzed
- `requirement_id`: the requirement whose acceptance criteria lack coverage

### Expected Output Path

`reports/agents/test_gap_report.json`

### Severity Guidance

- HIGH: a requirement's primary acceptance-criteria test is absent
- MEDIUM: an edge case is uncovered but the main path is tested
- LOW: a supplementary scenario is missing

### False-Positive Constraints

Must not report a test gap unless the agent has confirmed by reading
the actual test file that the scenario is absent.
Must not assume a test is missing without reading the test file.

---

## Agent 3 — Security Analyst

### Purpose

Inspect changed code for security risks, with focus on SQL injection,
unsafe input handling, missing parameterization, and authorization gaps.

### Input

- All changed source files from the Git diff
- `demo_target/routes/appointments.py` (directly changed)
- `demo_target/services/` (for service-layer context)

### Allowed Context

- Any file in `demo_target/` may be read
- Must read the actual code, not infer from filenames

### Prohibited Modifications

- Must not patch or modify any source file
- Must not write to any report file other than `reports/agents/security_report.json`

### Detection Responsibilities

For the controlled demo release, the Security Analyst must:

1. Read `demo_target/routes/appointments.py`
2. Locate the `search_appointments` function (the new `GET /appointments/search` endpoint)
3. Identify the user-controlled parameter: `status = request.args.get("status", "")`
4. Identify the unsafe SQL construction: `query = "SELECT * FROM appointments WHERE status = '" + status + "'"`
5. Confirm this is string concatenation (not a parameterized query)
6. Confirm that `status` flows directly from `request.args` into the SQL string without sanitization
7. Note that no other changed file introduces SQL injection (do not fabricate secondary findings)

### Required Evidence Per Finding

- `file_path`: `demo_target/routes/appointments.py`
- `symbol`: `search_appointments`
- `line_start` / `line_end`: actual line numbers where the concatenation occurs
- Evidence type `CODE` with the actual vulnerable pattern quoted

### Expected Output Path

`reports/agents/security_report.json`

### Severity Guidance

- CRITICAL: user-controlled input directly concatenated into SQL with no sanitization — exploitable SQL injection
- HIGH: unsafe pattern present but requires specific conditions to exploit
- MEDIUM: indirect or partial risk
- LOW: theoretical risk with multiple mitigating factors

### False-Positive Constraints

Must not report a SQL injection finding unless the agent has read the
actual code and confirmed string concatenation with user-controlled input.
Must not report generic "Flask security" concerns not present in the diff.
Must not invent injection risks for code paths not in the changed files.

---

## Agent 4 — Contract & Documentation Analyst

### Purpose

Compare each release requirement (R001–R005) against the changed implementation
and determine whether the requirement is satisfied, violated, or unverifiable.
Build requirement-to-code traceability.

### Input

- `requirements/CareHub_v2_4_Requirements.md` (canonical requirement source)
- All changed source files from the Git diff
- `demo_target/models.py` (for API response structure)
- `demo_target/services/notification_service.py` (for R001)
- `demo_target/routes/appointments.py` (for R002, R004)

### Allowed Context

- Any file in `demo_target/` may be read
- `requirements/CareHub_v2_4_Requirements.md` is the authoritative requirement source

### Prohibited Modifications

- Must not edit any route handler, model, service, or documentation file
- Must not write to any report file other than `reports/agents/contract_report.json`

### Detection Responsibilities

**R001 (Cancelled appointments must not generate reminders):**
- Read `notification_service.py` `send_reminder`
- Locate the condition guarding against sending reminders
- Determine whether the condition correctly blocks cancelled appointments
- The bad release changes `== "cancelled"` to `== "completed"` — the analyst must identify this

**R002 (API response must include appointment_id, status, eta_minutes):**
- Read `models.py` `appointment_row_to_dict`
- Verify all three required fields are present in the returned dict
- The bad release removes `eta_minutes` — the analyst must identify this gap

**R003 (Priority must be persisted through a versioned migration):**
- Read `migrations/001_initial_schema.sql`
- Read `db.py` SCHEMA
- Read `models.py` `VALID_PRIORITIES`
- Determine whether the priority change (CHECK constraint, new `critical` value) is reflected in a migration
- The bad release introduces a CHECK constraint and `critical` value with no migration

**R004 (User-controlled input must use parameterized queries):**
- Read `routes/appointments.py` search endpoint
- Verify SQL construction method
- The bad release introduces string concatenation

**R005 (Regression tests must cover cancellation, API contract, priority):**
- Read test files and check for the required named tests
- The bad release removes seven regression tests

### Required Evidence Per Finding

- `requirement_id`: the R-number being evaluated
- `file_path`: the implementation file being evaluated
- `symbol`: the specific function, class, or constant
- `description`: what the requirement says vs. what the code does

### Expected Output Path

`reports/agents/contract_report.json`

### Finding Per Requirement

The agent must produce exactly one finding per failing requirement,
with `finding_status` of `CONFIRMED` when the violation is observed in code.

### Severity Guidance

- HIGH: requirement is directly violated — code does the opposite of what is required
- MEDIUM: requirement is partially satisfied or ambiguous
- LOW: documentation gap or minor deviation from acceptance criteria

### False-Positive Constraints

Must not mark a requirement as FAIL without reading the actual implementation.
Must not assume a requirement passes because the test suite is green.

---

## Agent 5 — Database Analyst

### Purpose

Investigate whether the current release introduces schema or migration changes
that violate the versioned migration requirement (R003).

### Input

- `demo_target/db.py` (contains the SCHEMA constant)
- `demo_target/models.py` (contains VALID_PRIORITIES)
- `migrations/` directory (migration history)
- All changed files from the Git diff

### Allowed Context

- `migrations/` directory may be listed and read
- Any file in `demo_target/` may be read

### Prohibited Modifications

- Must not create or modify migration files
- Must not modify database code
- Must not write to any report file other than `reports/agents/database_report.json`

### Detection Responsibilities

For the controlled demo release, the Database Analyst must:

1. Read `migrations/001_initial_schema.sql` and record the `priority` column definition
   - Baseline: `priority TEXT NOT NULL DEFAULT 'normal'` (no CHECK constraint)
2. Read `demo_target/db.py` SCHEMA and record the `priority` column definition
   - Bad release: `priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'high', 'emergency', 'critical'))`
3. Compare: the SCHEMA in `db.py` now includes a CHECK constraint and the `critical` value that are absent from migration 001
4. List all files in `migrations/`: only `001_initial_schema.sql` is present — no `002_*` file
5. Read `demo_target/models.py` `VALID_PRIORITIES`: confirms `critical` is a new accepted value
6. Conclude: the application expects a schema constraint (`CHECK`) not present in any migration

### Required Evidence Per Finding

- `file_path`: `demo_target/db.py` for the SCHEMA change
- `file_path`: `migrations/001_initial_schema.sql` for the migration baseline
- `symbol`: `SCHEMA` constant and the `priority` column definition
- Evidence type `SCHEMA_CHANGE` for the mismatch
- Evidence type `FILE_PRESENCE` for the absent migration file

### Expected Output Path

`reports/agents/database_report.json`

### Severity Guidance

- HIGH: schema change (constraint, new value) with no migration — existing production databases would be inconsistent
- MEDIUM: schema documentation gap (comment or version note missing)
- LOW: migration naming or ordering concern

### False-Positive Constraints

Must not report a schema change without reading both the migration file and `db.py`.
Must not assume a migration is missing without listing the `migrations/` directory.
Must not invent a migration system — use the one that actually exists.

---

## Report Validation Contract

Before the Release Synthesizer accepts any agent report, it must verify:

| Check | Rule |
|---|---|
| JSON parseable | Must load without error |
| `report_type` | Must be `"agent_report"` |
| `status` | Must be one of `RELEASE_READY`, `NEEDS_ATTENTION`, `RELEASE_BLOCKED`, `ANALYSIS_ONLY` |
| `source_agent` | Must match the expected agent name for that report file |
| `CONFIRMED` findings | Must have `evidence` array with at least one item |
| Severity values | Must be one of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO` |
| `requirement_id` | Must be one of `R001`–`R005` or `null` |
| `affected_files` | Must only list real repository paths |

If a report fails validation, the Synthesizer marks that agent's result as failed
and records the validation errors. It does not invent corrected findings.

---

## Synthesis Contract

The Release Synthesizer (parent agent) reads all five reports after parallel execution completes.

**Input:** Five validated agent reports in `reports/agents/`

**Process:**
1. Load and validate each agent report
2. Deduplicate: if the same finding appears in two reports (same evidence, different IDs), merge evidence and keep one finding
3. Preserve all evidence references from originating agent reports
4. Assign severity using evidence-backed escalation rules (Critical > High > Medium > Low > Info)
5. Compute requirement compliance for R001–R005 from confirmed findings
6. Determine `release_status` from finding severity:
   - `RELEASE_BLOCKED` if any CRITICAL or HIGH confirmed finding exists
   - `NEEDS_ATTENTION` if only MEDIUM/LOW/INFO findings exist
   - `RELEASE_READY` only if no findings exist

**Output:** `reports/latest_release_report.json`

**Must not:** Invent findings not present in agent reports.
**Must not:** Hard-code a status value independent of evidence.
