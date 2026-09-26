# ShipSafe AI

> **Agentic Release & Regression Guardian**

ShipSafe AI is an agentic release-readiness and regression prevention system. It analyzes software changes across implementation, regression test gaps, security vulnerabilities, requirement compliance, and database migrations before release, supports evidence-backed remediation, and validates the final release candidate with real test execution.

---

## Problem

Software changes often introduce subtle, cross-cutting regressions that slip past isolated code reviews and standard CI pipelines:
- **Test Gap Masking:** Developers or automated tools may delete or weaken tests to make failing suites turn green.
- **Contract Drifts:** Subtle changes in serialization models break downstream client API expectations.
- **Security Vulnerabilities:** Seemingly innocent query adjustments introduce critical vulnerabilities like SQL injection (CWE-89).
- **Migration & Schema Conflicts:** Runtime code introduces new domain values or table constraints that have no corresponding versioned database migrations.
- **Conflicting Guidance:** Different review disciplines (e.g., database specialists vs. API contract authors) often provide contradictory recommendations for the same change.

Validating release safety across all these dimensions manually is error-prone, fragmented, and vulnerable to guesswork.

---

## Solution

ShipSafe AI establishes an end-to-end, deterministic release guardian workflow:
1. **Parallel Multi-Agent Analysis:** Specialized read-only agents investigate five distinct analysis workstreams.
2. **Deterministic Release Synthesis:** Unifies individual findings into an authoritative report, normalizing evidence, deduplicating findings, and surfacing architectural conflicts.
3. **Traceability Matrix:** Links release requirements directly to implementation code, test coverage, and confirmed findings.
4. **Release Impact Simulation:** Maps blast radiuses, affected application workflows, and concrete regression flow paths with zero probabilistic guesswork.
5. **Prioritized Remediation:** Generates a step-by-step fix plan ordered by severity.
6. **Post-Remediation Verification:** Executes real tests and coverage measurements to certify release readiness.

---

## Why IBM Bob 2.0

IBM Bob 2.0 serves as the core agentic orchestration environment:
- **Parallel Subagent Execution:** Orchestrated five specialized subagents simultaneously, ensuring complete workstream isolation.
- **Strict Evidence Standards:** Enforced read-only analysis discipline during investigation, requiring concrete evidence (file paths, line numbers, test names, command outputs) for every finding.
- **Architectural Conflict Surfacing:** Captured real technical disagreements (such as the R003 database vs. contract recommendation conflict) rather than forcing an artificial consensus.
- **Immutable Audit Trail:** Stored independent analysis artifacts in isolated files under `reports/agents/` that serve as a permanent, tamper-proof record.

---

## Architecture

ShipSafe AI is organized into a modular, lightweight architecture:

```
shipsafe-ai/
├── shipsafe/
│   ├── analyzer/           # Core deterministic engine
│   │   ├── git_analyzer.py      # Git commit, branch, and diff inspection
│   │   ├── test_analyzer.py     # Subprocess pytest and coverage collection
│   │   ├── requirements.py      # Requirement parsing and tracking
│   │   ├── metrics.py           # Metric aggregation
│   │   ├── report_builder.py    # Standardized report builder
│   │   ├── runner.py            # Local base analysis pipeline
│   │   ├── synthesizer.py       # IBM Bob report consolidation & synthesis
│   │   ├── traceability.py      # Requirement-to-code traceability engine
│   │   ├── release_simulator.py # Deterministic release blast radius simulation
│   │   ├── remediation.py       # Evidence-backed remediation planner
│   │   └── comparison.py        # 3-way milestone comparison engine
│   ├── schemas/            # JSON Schema definitions for reports
│   └── web/                # Self-contained Flask DevSecOps dashboard
├── demo_target/            # CareHub Appointment Service (sample target application)
│   ├── routes/             # Flask API endpoints
│   ├── services/           # Business logic & notifications
│   ├── models.py           # Domain models & serialization
│   ├── db.py               # SQLite database access
│   └── tests/              # Pytest test suite
├── requirements/           # Release requirements (R001–R005)
├── reports/                # Top-level synthesized release reports
│   └── agents/             # 5 immutable historical IBM Bob analysis reports
├── scripts/                # Demo fixtures (apply_demo_release.py, reset_demo.py)
└── docs/                   # Architectural & validation specifications
```

---

## Five IBM Bob Analysis Agents

During the candidate release analysis phase, IBM Bob 2.0 orchestrated five independent analysis agents:

| Agent | Report Path | Findings | Primary Focus |
|---|---|---|---|
| **Impact Analyst** | `reports/agents/impact_report.json` | 8 | Code impact, modified symbols, affected caller chains |
| **Test Gap Analyst** | `reports/agents/test_gap_report.json` | 7 | Deleted regression tests, coverage drops, unverified behaviors |
| **Security Analyst** | `reports/agents/security_report.json` | 1 | Unsafe query concatenation (CWE-89 SQL Injection) |
| **Contract Analyst** | `reports/agents/contract_report.json` | 5 | Missing API response fields (`eta_minutes`), invalid priorities |
| **Database Analyst** | `reports/agents/database_report.json` | 1 | Unmigrated SQLite CHECK constraints, missing migration files |

*All 5 agent report files remain immutable in `reports/agents/` as permanent historical evidence.*

---

## Detection → Synthesis → Traceability → Remediation → Validation

```
[1. Candidate Release]
       │
       ▼
[2. Five IBM Bob Analysis Agents] (Impact, Test Gap, Security, Contract, Database)
       │
       ▼
[3. Release Synthesizer] (Consolidates 22 findings, detects R003 conflict, blocks release)
       │
       ▼
[4. Traceability & Simulation] (Matrix R001-R005, 5 regression paths, blast radius)
       │
       ▼
[5. Remediation Execution] (P1 SQLi -> P2 Guard -> P3 ETA -> P4 Priority -> P5 Tests)
       │
       ▼
[6. Post-Remediation Verification] (172 passing tests, 98% coverage, RELEASE_READY)
```

---

## Demonstrated Impact

All metrics are measured from actual test runs, coverage tools, and repository inspection. No values are simulated:

| Metric | Baseline | Candidate Bad Release | Post-Remediation | Net Improvement |
|---|---|---|---|---|
| **Total Tests** | 38 | 31 (-7 deleted) | **42** | **+11 tests** |
| **Passed Tests** | 38 | 31 | **42** | **+11 passed** |
| **Failed Tests** | 0 | 0 | **0** | **0** |
| **Statement Coverage** | 98.0% (434 stmts) | 96.0% (396 stmts) | **98.0% (478 stmts)** | **+2.0% coverage** |
| **Requirements Compliant** | 5 / 5 | 0 / 5 (all failed) | **5 / 5** | **5 requirements restored** |
| **Critical Vulnerabilities** | 0 | 1 (CWE-89 SQLi) | **0** | **-1 critical** |
| **High Severity Issues** | 0 | 19 | **0** | **-19 high** |
| **Total Active Findings** | 0 | 22 | **0** | **-22 findings** |
| **Release Decision** | `RELEASE_READY` | `RELEASE_BLOCKED` | **`RELEASE_READY`** | **Safe for deployment** |

---

## Technology Stack

- **Orchestration & Agents:** IBM Bob 2.0
- **Programming Language:** Python 3.11
- **Web Application & API:** Flask 3.1
- **Testing & Coverage:** pytest 9.1, pytest-cov 7.1
- **Database:** SQLite3
- **Frontend Dashboard:** Vanilla HTML5, CSS3 (Dark Graphite DevSecOps Design System), JavaScript (ES6+)
- **Validation Schemas:** JSON Schema (Draft 7)
- **Version Control:** Git

*No external AI API calls, no heavyweight SaaS dependencies, no Node/npm build steps.*

---

## Project Structure

```
├── AGENTS.md                          # Repository rules and agent contract
├── README.md                          # Project documentation
├── requirements.txt                   # Minimal Python dependencies
├── migrations/                        # Versioned database migrations
│   └── 001_initial_schema.sql         # Baseline table schema
├── requirements/                      # Release requirements
│   ├── CareHub_v2_4_Requirements.md   # Requirement definitions R001–R005
│   └── CareHub_v2_4_Requirements.pdf  # Compiled requirement document
├── reports/                           # Output reports
│   ├── latest_release_report.json     # Synthesized release report
│   ├── traceability.json              # Traceability matrix JSON
│   ├── release_simulation.json        # Release blast radius simulation JSON
│   ├── remediation_plan.json          # Prioritized remediation plan JSON
│   ├── comparison.json                # 3-way milestone comparison JSON
│   ├── final_requirement_validation.json # Final requirement audit
│   └── agents/                        # 5 historical IBM Bob reports
├── docs/                              # Comprehensive documentation
│   ├── BOB_ANALYSIS_AUDIT.md          # Phase 1 Bob agent report audit
│   ├── SYNTHESIS.md                   # Phase 2 Release synthesis specification
│   ├── TRACEABILITY.md                # Phase 3 Requirement traceability matrix
│   ├── RELEASE_IMPACT_SIMULATION.md   # Phase 4 Release impact simulation
│   ├── REMEDIATION_PLAN.md            # Phase 5 Prioritized remediation plan
│   ├── METRICS.md                     # Phase 6 Measurement specification
│   ├── DASHBOARD.md                   # Phase 7 Dashboard documentation
│   ├── POST_REMEDIATION_REPORT.md     # Phase 8 Remediation & validation report
│   ├── FINAL_REQUIREMENT_VALIDATION.md# Final requirement verification audit
│   ├── HACKATHON_DEMO.md              # 3-minute hackathon demo script
│   └── SUBMISSION_ARTIFACT_INDEX.md   # Index of submission deliverables
└── scripts/
    ├── apply_demo_release.py          # Applies controlled regressions
    ├── reset_demo.py                  # Restores clean baseline
    └── generate_requirements_pdf.py   # PDF requirement compiler
```

---

## Running the Dashboard

Launch the local DevSecOps guardian dashboard on default port **5000**:

```bash
python -m shipsafe.web.app
```

Then open your browser at:
`http://127.0.0.1:5000`

### Available API Endpoints
- `GET /api/overview` — High-level status, release decision, and KPI metrics
- `GET /api/agents` — Five IBM Bob 2.0 analysis agents and attributions
- `GET /api/requirements` — R001–R005 requirement compliance status
- `GET /api/findings` — Synthesized findings (supports `?severity=CRITICAL`)
- `GET /api/traceability` — Requirement-to-code traceability matrix
- `GET /api/simulation` — Impact simulation and 5 regression paths
- `GET /api/remediation` — Prioritized remediation action items
- `GET /api/comparison` — 3-way milestone metrics (Baseline → Bad Release → Post-Remediation)
- `POST /api/refresh` — Reloads all report artifacts from disk

---

## Running the Tests

Execute the entire test suite across demo target and ShipSafe engines:

```bash
# Run all tests in the workspace (172 tests)
python -m pytest -q

# Run target application tests with coverage (42 tests, 98% coverage)
python -m pytest demo_target/tests/ --cov=demo_target --cov-report=term-missing
```

---

## Reproducing the Demo

To reproduce the complete detection, remediation, and validation flow:

```bash
# 1. Reset target to baseline
python scripts/reset_demo.py

# 2. Inject bad release regressions (mutates 6 files, deletes 7 tests, injects SQLi)
python scripts/apply_demo_release.py

# 3. Run analysis & synthesis
python -m shipsafe.analyzer.runner --no-coverage
python -m shipsafe.analyzer.synthesizer
python -m shipsafe.analyzer.traceability
python -m shipsafe.analyzer.release_simulator

# 4. View dashboard (shows RELEASE_BLOCKED, 22 findings, 5 regression paths)
python -m shipsafe.web.app

# 5. Review remediation plan
cat docs/REMEDIATION_PLAN.md

# 6. Re-analyze post-remediation
python -m shipsafe.analyzer.runner --no-coverage
python -m shipsafe.analyzer.synthesizer
python -m shipsafe.analyzer.comparison --post-remediation

# 7. View dashboard (shows RELEASE_READY, 42 tests passing, 98% coverage, 0 findings)
```

---

## IBM Bob Attribution

The five specialized analysis reports under `reports/agents/` were generated by **IBM Bob 2.0** acting as an autonomous multi-agent release guardian:
- Impact Analyst: `reports/agents/impact_report.json`
- Test Gap Analyst: `reports/agents/test_gap_report.json`
- Security Analyst: `reports/agents/security_report.json`
- Contract Analyst: `reports/agents/contract_report.json`
- Database Analyst: `reports/agents/database_report.json`

ShipSafe AI's deterministic synthesis, simulation, traceability, comparison, and web dashboard were built to ingest, validate, and execute upon these historical agent findings.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
