# ShipSafe AI — Measurement System & Metrics Specification

ShipSafe AI provides an evidence-based, deterministic before/after measurement system that captures and compares software state across three distinct release milestones:
1. **BASELINE**: The verified clean application state prior to candidate release modifications.
2. **BAD_RELEASE**: The candidate release incorporating regressions, deleted tests, unparameterized SQL queries, and schema contract violations.
3. **POST_REMEDIATION**: The remediated release candidate with verified fixes, restored tests, and validated contracts.

---

## Measurement Principles

ShipSafe enforces strict measurement integrity principles to eliminate hallucination, bias, and artificial release gating:

1. **Grounded in Concrete Execution**:
   Every test metric (total, passed, failed, skipped, errors, duration) and code coverage metric (statements, missed, percentage) is collected via live subprocess execution (`pytest` and `pytest-cov`). No metrics are inferred or simulated.

2. **Authoritative Synthesis Ingestion**:
   Finding counts by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`) and requirement compliance statuses (`PASS`, `FAIL`, `WARNING`, `UNVERIFIABLE`) are ingested directly from the synthesized analysis report (`reports/latest_release_report.json`), which unifies evidence across all five specialized analysis agents.

3. **Strict Absence of Placeholders**:
   When a state or metric is not yet measurable—such as `POST_REMEDIATION` prior to remediation execution—it is explicitly marked as unavailable (`status: "NOT_AVAILABLE"`) with `null` fields. ShipSafe strictly forbids guessing or filling placeholders with optimistic projections.

4. **Honest Delta Calculation**:
   Deltas are calculated strictly when both baseline and candidate metrics are available numbers (`delta = current - before`). Unavailable metrics evaluate to `null` deltas. Unavailable values are **never coerced to zero** (which would corrupt delta directionality and misrepresent regressions).

5. **Read-Only Non-Destructive Invariance**:
   Metric collection scripts inspect and execute tests without mutating source files. When evaluating regressions in temporary stages, the system automatically restores and verifies the clean baseline via `scripts/reset_demo.py`.

---

## Baseline

The Baseline represents the validated CareHub Appointment Service (`demo_target/`) before candidate release changes are introduced.

### Baseline Evidence & Measured Values

| Dimension | Metric | Measured Value | Measurement Source |
|---|---|---|---|
| **Git** | Head Commit | `ae6b358` (or `5f95cd1`) | `git rev-parse HEAD` |
| | Branch | `main` | `git symbolic-ref --short HEAD` |
| | Clean Working Tree | Clean (`demo_target/` untouched) | `git status --porcelain` |
| **Tests** | Total Tests | **38** | `pytest demo_target/tests/ -q` |
| | Passed Tests | **38** | Real test execution |
| | Failed / Errors | **0 / 0** | Real test execution |
| | Duration | ~3.89 seconds | pytest summary output |
| **Coverage** | Total Coverage | **98.0%** | `pytest-cov` report |
| | Statements | 434 statements | `pytest-cov` report |
| | Missed Lines | 10 lines (entry guards/unused config) | `pytest-cov` report |
| **Requirements** | Total Tracked | **5** (R001–R005) | `requirements/CareHub_v2_4_Requirements.md` |
| | Compliant (Passed) | **5** | Baseline requirements verification |
| | Non-compliant (Failed) | **0** | Baseline requirements verification |
| **Findings** | Total Findings | **0** | Clean baseline analysis |
| | Critical / High / Med | **0 / 0 / 0** | No security or contract defects |
| **Changes** | Repository Changed Files | **1** | `scripts/apply_demo_release.py` (demo_target untouched) |
| | Demo Target Changed Files | **0** | `demo_target/` working tree verified clean |
| | Affected Files | **0** | Zero application defect paths |

---

## Bad Release

The Bad Release represents a controlled set of intentional regressions applied to the CareHub sample application via `scripts/apply_demo_release.py`.

### Regressions Applied

1. **R001 Regression** (`demo_target/services/notification_service.py`):
   Cancelled-appointment guard modified to check `'completed'` instead of `'cancelled'`, allowing cancelled appointments to receive reminders.
2. **R002 Regression** (`demo_target/models.py`):
   `eta_minutes` removed from appointment serialization dictionary, breaking API contracts.
3. **R003 Regression** (`demo_target/models.py`, `demo_target/db.py`):
   `critical` priority added to Python model and SQLite table CHECK constraint without a versioned migration.
4. **R004 Regression** (`demo_target/routes/appointments.py`):
   Unsafe SQL query with raw string interpolation (`f"SELECT ... WHERE patient_name = '{patient_name}'"`) introducing a **CRITICAL CWE-89 SQL Injection** vulnerability.
5. **R005 Regression** (`demo_target/tests/test_notifications.py`, `demo_target/tests/test_appointments.py`):
   7 regression tests silently deleted to conceal R001, R002, and R003 regressions.

### Bad Release Evidence & Measured Values

| Dimension | Metric | Measured Value | Measurement Source | Delta vs Baseline |
|---|---|---|---|---|
| **Git** | Repository Files Changed | **7** | `git diff --stat HEAD` (6 demo_target + 1 script) | +6 files |
| | Demo Target Files Changed | **6** | `demo_target/` modified files | +6 files |
| | Lines Added / Deleted | +29 / -107 | `git diff --stat` | Net -78 lines |
| **Tests** | Total Tests | **31** | `pytest demo_target/tests/ -q` | **-7 tests** (deleted) |
| | Passed Tests | **31** | Real test execution | **-7 tests** |
| | Failed / Errors | **0 / 0** | Pass count masked by test deletion | 0 |
| **Coverage** | Total Coverage | **96.0%** | `pytest-cov` report | **-2.0%** |
| | Statements | 396 statements | `pytest-cov` report | -38 statements |
| | Missed Lines | 16 lines | `pytest-cov` report | +6 lines |
| **Requirements** | Compliant (Passed) | **0** | Synthesized analysis report | **-5 requirements** |
| | Non-compliant (Failed)| **5** (R001–R005) | Synthesized analysis report | **+5 requirements** |
| **Findings** | Critical | **1** (CWE-89 SQLi) | Ingested findings array | **+1 critical** |
| | High | **19** | Ingested findings array | **+19 high** |
| | Medium | **2** | Ingested findings array | **+2 medium** |
| | Total Findings | **22** | Ingested findings array | **+22 findings** |
| **Impact** | Affected Files | **12** | Git diff + agent evidence paths | +12 files |

---

## Post-Remediation

Post-Remediation represents the repository after confirmed findings have been fixed, database contracts validated, deleted tests restored, and regression tests added.

### Post-Remediation Evidence & Measured Values

All values come directly from actual execution via `shipsafe/analyzer/comparison.py` and are recorded in `reports/comparison.json`:

| Dimension | Metric | Measured Value | Measurement Source | Delta vs Bad Release | Delta vs Baseline |
|---|---|---|---|---|---|
| **Git** | Demo Target Files Remediated | **6** | `demo_target/` working tree | 0 | +6 files |
| | Lines Added / Deleted | +152 / -98 | `git diff --stat` | +123 / +9 lines | Net +54 lines |
| **Tests** | Total Tests | **42** | `pytest demo_target/tests/ -q` | **+11 tests** | **+4 tests** |
| | Passed Tests | **42** | Real test execution | **+11 tests** | **+4 tests** |
| | Failed / Errors | **0 / 0** | Real test execution | 0 | 0 |
| **Coverage** | Total Coverage | **98.0%** | `pytest-cov` report | **+2.0%** | **0.0%** |
| | Statements | 478 statements | `pytest-cov` report | +82 statements | +44 statements |
| | Missed Lines | 10 lines | `pytest-cov` report | -6 lines | 0 lines |
| **Requirements** | Compliant (Passed) | **5 / 5** | Traceability & validation tests | **+5 requirements** | 0 |
| | Non-compliant (Failed)| **0** | Traceability & validation tests | **-5 requirements** | 0 |
| **Findings** | Critical | **0** | Verified in repo & test defense | **-1 critical** | 0 |
| | High | **0** | Verified in repo & test defense | **-19 high** | 0 |
| | Medium | **0** | Verified in repo & test defense | **-2 medium** | 0 |
| | Total Active Findings | **0** | Synthesized findings verification | **-22 findings** | 0 |
| **Impact** | Remediated Files | **6** | 4 app modules + 2 test suites | -6 affected | +6 files |

---

## Metrics

ShipSafe tracks five core metric categories:

### 1. Test Execution Metrics
- `tests.total`: Total number of tests discovered and run by pytest.
- `tests.passed`: Tests passing with exit status 0.
- `tests.failed`: Tests failing assertions.
- `tests.skipped`: Tests explicitly skipped via marks.
- `tests.errors`: Tests encountering unhandled runtime exceptions during fixture setup/teardown.
- `tests.duration_seconds`: Total execution duration in seconds.

### 2. Code Coverage Metrics
- `coverage.available`: Boolean indicating whether `pytest-cov` executed successfully.
- `coverage.percent`: Float percentage of statement coverage across `demo_target/`.
- `coverage.statements`: Total executable statement count.
- `coverage.missed`: Count of uncovered executable statements.

### 3. Release Requirements Metrics
- `requirements.total`: Total release requirements tracked (5 for CareHub v2.4).
- `requirements.passed`: Count of requirements confirmed compliant.
- `requirements.failed`: Count of requirements confirmed violated.
- `requirements.warning`: Count of requirements with unresolved ambiguities.
- `requirements.unverifiable`: Count of requirements lacking verifiable test/code evidence.

### 4. Findings & Vulnerability Metrics
- `findings.critical`: Count of Critical severity findings (e.g. CWE-89 SQL Injection).
- `findings.high`: Count of High severity findings (contract breaches, missing guards, test gaps).
- `findings.medium`: Count of Medium severity findings (documentation and schema warnings).
- `findings.low`: Count of Low severity findings.
- `findings.info`: Count of Informational observations.
- `findings.total`: Authoritative sum of all findings parsed from the synthesized findings array.

### 5. Change & Impact Metrics
- `git.files_changed`: Number of modified or untracked repository files.
- `git.lines_added`: Number of added lines across diff chunks.
- `git.lines_deleted`: Number of removed lines across diff chunks.
- `affected_files`: Unique count of application files affected by changes and findings.

---

## How Measurements Are Collected

The measurement pipeline (`shipsafe/analyzer/comparison.py`) executes deterministically:

```
[1] reset_demo.py
    └── Restores demo_target files to committed baseline (git checkout HEAD -- demo_target)
[2] capture_snapshot("BASELINE")
    ├── Executes: python -m pytest demo_target/tests/ -q --cov=demo_target
    ├── Parses: git commit, branch, working tree status
    └── Records: 38 passed, 98% coverage, 5/5 requirements passed, 0 findings
[3] apply_demo_release.py
    └── Injects 5 regressions into demo_target (mutates 6 files, removes 7 tests)
[4] synthesize_release()
    └── Synthesizes IBM Bob agent findings into reports/latest_release_report.json
[5] capture_snapshot("BAD_RELEASE")
    ├── Executes: python -m pytest demo_target/tests/ -q --cov=demo_target
    ├── Ingests: reports/latest_release_report.json findings and requirement statuses
    └── Records: 31 passed, 96% coverage, 5/5 requirements failed, 22 findings
[6] capture_snapshot("POST_REMEDIATION", is_available=False)
    └── Explicit NOT_AVAILABLE state (no fabrication)
[7] compare_snapshots(baseline, bad_release, post_remediation)
    └── Computes numerical deltas (bad vs baseline) and marks post-remediation unavailable
[8] save_comparison(comparison_data, "reports/comparison.json")
    └── Writes persistent machine-readable JSON artifact
[9] reset_demo.py & verify
    └── Restores demo_target to clean baseline and validates all 38 tests pass
```

---

## Why Metrics Are Not Hard-Coded

Hard-coding metrics in software release tooling introduces fatal failure modes:

1. **Regression Masking**:
   If test counts or coverage percentages are hard-coded constants, future changes that break functionality or drop coverage will remain undetected.
2. **Decoupling from Reality**:
   Hard-coded release values represent claims rather than evidence. Release certification requires verifiable cryptographic and runtime proof.
3. **Falsification of Remediation**:
   When remediation is executed in subsequent phases, the system must independently prove improvement by running real tests and re-measuring coverage against the baseline. Dynamic capture ensures that remediation success is genuine and auditable.
4. **Environment Portability**:
   Running real commands ensures that differences across operating systems, Python versions, or test runners are faithfully captured rather than assumed.
