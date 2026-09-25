# ShipSafe AI — Official Demo Scenario

---

## Scenario

A CareHub-inspired appointment service is receiving a new release.

The service handles patient registration, appointment creation and cancellation, doctor availability, appointment priority, and reminder notifications. It exposes a REST API and uses SQLite for persistence.

---

## Baseline

The baseline implementation is correct. Its existing tests pass. The system satisfies all release requirements in its pre-release state.

ShipSafe analysis of the baseline should produce no Critical or High findings and a release status of `RELEASE READY`.

---

## Controlled Release

A new release is applied to the baseline. This release intentionally introduces five known problems that a careful developer might miss during a manual review.

### Problem 1 — Cancelled Appointments Trigger Reminders

The reminder notification service is called for cancelled appointments. A conditional check that should prevent this is absent or incorrect in the changed code.

**Violates:** R001

### Problem 2 — API Response Missing `eta_minutes`

The appointment API endpoint no longer includes `eta_minutes` in its response. The field was present in the baseline and is required by the API contract.

**Violates:** R002

### Problem 3 — Appointment Priority Added Without Migration

A new `priority` field has been added to the appointment model. No corresponding versioned database migration file has been created. The schema and the migration history are inconsistent.

**Violates:** R003

### Problem 4 — Unsafe SQL Construction

A database search function constructs its SQL query by concatenating user-controlled input directly into the query string rather than using parameterized queries.

**Violates:** R004

### Problem 5 — Missing Regression Coverage

The test suite does not cover the cancellation-reminder behavior, the API contract field requirements, or the appointment priority persistence. The regression scenarios for the changed behavior are absent.

**Violates:** R005

---

## Release Requirements

The following requirements are active for this release:

**R001**
Cancelled appointments must not generate reminder notifications.

**R002**
Appointment API responses must include `appointment_id`, `status`, and `eta_minutes`.

**R003**
Appointment priority must be persisted through a versioned database migration.

**R004**
User-controlled database search input must use parameterized queries.

**R005**
Regression tests must cover cancellation behavior, API contract changes, and appointment priority.

---

## Expected Demo Flow

```
1. Baseline state
   └── ShipSafe analysis
       └── RELEASE READY (no critical findings)

2. Apply controlled bad release
   └── Git diff shows changed files

3. Run ShipSafe analysis
   ├── Phase 1: Discover — scope established, R001–R005 loaded
   ├── Phase 2: Parallel Analysis
   │   ├── Impact Analyst      → impact_report.json
   │   ├── Test Gap Analyst    → test_gap_report.json
   │   ├── Security Analyst    → security_report.json
   │   ├── Contract Analyst    → contract_report.json
   │   └── Database Analyst    → database_report.json
   └── Phase 3: Synthesis
       └── latest_release_report.json → RELEASE BLOCKED

4. Remediation
   ├── Fix R001: add cancellation guard in reminder service
   ├── Fix R002: restore eta_minutes in API response
   ├── Fix R003: create versioned migration for priority field
   ├── Fix R004: replace string concatenation with parameterized query
   └── Fix R005: add regression tests for all five requirements

5. Validation
   └── Execute pytest
       └── All tests pass, coverage measured

6. Re-analysis
   └── Regenerate reports
       └── latest_release_report.json → RELEASE READY

7. Before/after comparison
   └── Metrics from actual tool execution
       (specific numbers will come from real execution, not this document)
```

---

## Expected ShipSafe Findings

The following findings are expected after ShipSafe analyzes the controlled bad release. Specific file paths and line numbers will be determined from actual repository evidence at runtime.

| Finding | Severity | Requirement | Agent |
|---|---|---|---|
| Cancelled appointment triggers reminder | High | R001 | Contract Analyst, Test Gap Analyst |
| `eta_minutes` absent from API response | High | R002 | Contract Analyst |
| `priority` field added without migration | High | R003 | Database Analyst |
| Unsafe SQL string concatenation with user input | Critical | R004 | Security Analyst |
| No regression tests for cancellation, API contract, or priority | High | R005 | Test Gap Analyst |

---

## What the Demo Does Not Do

- Does not invent metric values. All before/after numbers come from actual `pytest` and coverage tool execution.
- Does not claim `RELEASE READY` until validation has been executed and all findings are resolved.
- Does not skip the synthesis step and go directly from analysis to remediation.
- Does not treat a code review observation as a confirmed finding without repository evidence.

---

## Expected Judge Takeaway

> "ShipSafe does not merely review changed code. It investigates whether a release is actually safe across requirements, tests, security, APIs, and database impact."

The demo illustrates that five different types of release problem — a logic bug, an API contract violation, a missing migration, a security vulnerability, and missing test coverage — can exist simultaneously in a single small change, and that a systematic agentic workflow is more reliable than a manual review at catching all of them before release.

---

## Notes on Metrics

Do not invent specific final metric values in this document.

Before/after metrics (test pass counts, coverage percentages, finding counts) will be populated from actual tool execution when the demo is run. The scenario document records the structure of the demo, not the specific numbers. Numbers placed here would be fabricated and would violate the no-invention rule in `AGENTS.md`.
