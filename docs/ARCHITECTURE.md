# ShipSafe AI — Architecture

> **This document describes the intended architecture. The system has not yet been built.**
> Do not treat this document as an implementation guide for creating files or running code ahead of schedule.

---

## Conceptual Overview

ShipSafe AI is an agentic release-readiness system. It sits between a developer's change and the release gate. A developer submits a change, ShipSafe investigates it across multiple dimensions, synthesizes evidence, supports remediation, validates the result, and issues a final release determination.

The system is built in two clearly separated parts:

| Part | What it is |
|---|---|
| **ShipSafe AI** | The product — the analysis engine, orchestration logic, and dashboard |
| **`demo_target/`** | The software being analyzed — a separate, compact sample healthcare application |

`demo_target/` is not part of ShipSafe. It is the subject of ShipSafe's analysis during the demo.

---

## Architectural Layers

### Layer 1 — Demo Target

The demo target is a small CareHub-inspired appointment service that provides realistic software to analyze. It is the input to ShipSafe — not part of ShipSafe itself.

- Built with Python + Flask + SQLite + pytest
- Contains routes, service logic, database models, and tests
- Intentionally compact and solo-developer sized
- During the demo, a controlled bad release is applied to introduce known problems

### Layer 2 — Git / Change Source

ShipSafe reads the current state of the repository and the current change using Git. The Git diff is the primary input to the analysis engine. No proprietary version control integration is required.

- `git diff` provides the changed file set
- `git log` and `git show` provide commit context where needed
- The repository file tree provides the full source context

### Layer 3 — ShipSafe Analysis Engine

The analysis engine is the core of the product. It coordinates the five analysis workstreams, manages report I/O, and runs the Release Synthesizer.

- Located under `shipsafe/analyzer/`
- Reads the Git diff and repository state
- Dispatches to the five analysis agents
- Collects agent reports from `reports/agents/`
- Passes reports to the Release Synthesizer

During the analysis phase, the engine is strictly read-only with respect to application source.

### Layer 4 — Five Analysis Workstreams

Five independent agents investigate the change from different perspectives. They run in parallel (or in sequence for the prototype) and each writes only its own isolated report.

| Agent | Focus | Report |
|---|---|---|
| Impact Analyst | Which files, modules, APIs, and tests are affected | `reports/agents/impact_report.json` |
| Test Gap Analyst | Which behaviors lack test coverage | `reports/agents/test_gap_report.json` |
| Security Analyst | Unsafe input handling, SQL construction, secrets, auth | `reports/agents/security_report.json` |
| Contract & Documentation Analyst | Requirements and API contract compliance | `reports/agents/contract_report.json` |
| Database Analyst | Schema changes and migration consistency | `reports/agents/database_report.json` |

No agent edits application source during the analysis phase.

### Layer 5 — Release Synthesizer

The Release Synthesizer reads all five agent reports, deduplicates findings, preserves evidence, assigns severity, determines requirement compliance, and generates the master release report.

- Input: five agent reports from `reports/agents/`
- Output: `reports/latest_release_report.json`
- Sets the initial release status: `RELEASE READY`, `NEEDS ATTENTION`, or `RELEASE BLOCKED`
- Must not invent findings or upgrade severity beyond what the evidence supports

### Layer 6 — Remediation

After synthesis, confirmed findings are addressed in a controlled, sequential process. Each fix is the minimum change required to resolve the confirmed finding.

- Source edits limited to files identified in the synthesized report
- Regression tests added for each confirmed bug fix
- No unrelated refactoring
- Security fixes address the specific pattern identified in the security report
- Database migrations follow the project's versioning convention

### Layer 7 — Validation

After each remediation action, validation is executed to confirm the fix.

- `pytest` is run and output is observed
- Coverage is measured with actual tooling
- The specific scenario from the finding is confirmed passing
- Affected agent reports are regenerated
- `reports/latest_release_report.json` is updated

### Layer 8 — Reporting

All findings, metrics, compliance statuses, and release decisions are stored as structured JSON in the `reports/` directory. The report files are the authoritative record of the analysis.

```
reports/
  latest_release_report.json   — master synthesized report
  agents/
    impact_report.json
    test_gap_report.json
    security_report.json
    contract_report.json
    database_report.json
```

Reports must never contain invented metrics. All numbers must come from actual tool execution.

### Layer 9 — Dashboard

A lightweight Flask + Jinja dashboard will provide a human-readable view of the release report.

- Located under `shipsafe/web/`
- Flask routes serve the dashboard pages
- Jinja templates render the report data
- Vanilla HTML, CSS, and JavaScript only — no React or other frontend frameworks
- The dashboard reads from `reports/latest_release_report.json`
- The dashboard does not run analyses directly; it displays previously generated reports

---

## Future Repository Structure

The following structure will be used when the project is built. Not all directories exist yet.

```
shipsafe-ai/
│
├── shipsafe/
│   ├── analyzer/       — analysis engine and agent implementations
│   ├── schemas/        — JSON schemas for agent report formats
│   └── web/            — Flask dashboard (routes, templates, static)
│
├── demo_target/
│   ├── routes/         — Flask route handlers for the sample app
│   ├── services/       — business logic for the sample app
│   └── tests/          — pytest tests for the sample app
│
├── requirements/       — release requirement definitions (R001–R005)
├── reports/            — generated release reports
│   └── agents/         — per-agent isolated JSON reports
│
├── scripts/            — utility scripts (run analysis, apply migrations, etc.)
├── docs/               — architecture and product documentation
├── .bob/               — Bob rules, skills, and configuration
│   ├── rules/
│   │   └── shipsafe-rules.md
│   └── skills/
│       └── shipsafe-release/
│           └── SKILL.md
│
└── AGENTS.md           — project contract for Bob tasks
```

---

## Key Separation: ShipSafe vs. Demo Target

This distinction must be preserved throughout the project:

```
ShipSafe AI (product)
├── Analyzes software changes
├── Runs five independent agents
├── Synthesizes evidence
├── Supports remediation
├── Validates results
└── Issues release determinations

demo_target/ (software being analyzed)
├── CareHub-inspired appointment service
├── Intentionally compact
├── Has deliberate release problems introduced for the demo
└── Is the INPUT to ShipSafe, not part of ShipSafe
```

ShipSafe code must not be mixed into `demo_target/`. Analysis agent code must not be deployed inside the demo target.

---

## IBM Bob Role

IBM Bob 2.0 is the central orchestration environment for the ShipSafe development workflow. It is not a decorative chatbot. Bob:

- Executes analysis workstreams as focused tasks
- Enforces the project rules defined in `.bob/rules/shipsafe-rules.md`
- Uses the `shipsafe-release` skill to guide the release workflow
- Reads `AGENTS.md` as the authoritative project contract
- Provides the agentic coordination that makes ShipSafe a true agentic system

---

## Technology Stack

| Component | Technology |
|---|---|
| Demo target application | Python + Flask + SQLite |
| Demo target tests | pytest |
| ShipSafe analysis engine | Python |
| ShipSafe dashboard | Flask + Jinja + vanilla HTML/CSS/JS |
| Orchestration | IBM Bob 2.0 |
| Version control integration | Git (local) |
| Report format | JSON |
| No external AI API required for core prototype | — |
