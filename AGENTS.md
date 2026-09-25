# ShipSafe AI — Project Contract for Bob Tasks

## Project Identity

**Product:** ShipSafe AI
**Tagline:** Agentic Release & Regression Guardian
**Repository:** shipsafe-ai

ShipSafe AI is an agentic release-readiness system that analyzes a software change across implementation, tests, requirements, APIs, security, and database impact before release. It then supports evidence-backed remediation and re-validation.

---

## Purpose

Every Bob task in this repository must serve the ShipSafe AI product. The purpose of this project is to build an agentic workflow that:

1. Accepts a repository and a current change state as input.
2. Runs independent analysis workstreams in parallel.
3. Synthesizes evidence-backed findings.
4. Supports controlled remediation.
5. Validates the result.
6. Produces a final, evidence-based release-readiness determination.

---

## Architecture Principles

1. ShipSafe AI is the product being built.
2. `demo_target/` is a separate sample application that ShipSafe analyzes — it is not ShipSafe itself.
3. IBM Bob 2.0 is the central orchestration environment for the development workflow and agentic analysis. It must be treated as a core system component, not a decorative chatbot.
4. The five analysis agents are read/analyze-only during the analysis phase. They must not edit application source code during analysis.
5. Each analysis agent writes only its own isolated report under `reports/agents/`.
6. Remediation happens only after evidence-backed findings have been synthesized by the Release Synthesizer.
7. Every important metric must come from real execution or repository evidence.
8. Every finding must be supported by concrete evidence (file path, function/class, changed code, test name, requirement ID, command output, or database schema evidence).
9. The Release Synthesizer reads the five agent reports and produces `reports/latest_release_report.json`.
10. Final release status must be based on actual validation results.

---

## Technology Constraints

- **Demo target:** Python + Flask + SQLite + pytest
- **Dashboard:** Flask + Jinja + vanilla HTML/CSS/JavaScript
- No React frontend.
- No external AI API required for the core prototype.
- No Kubernetes, Redis, or complex cloud infrastructure.
- No multi-user SaaS features.
- No enterprise authentication or GitHub OAuth.
- Keep the architecture compact and solo-developer friendly.
- Avoid unnecessary dependencies and infrastructure.

---

## Directory Responsibilities

The following structure will be used when the project is built. Do not create directories or files ahead of schedule.

```
shipsafe/
  analyzer/       — analysis engine and agent implementations
  schemas/        — JSON schemas for agent reports
  web/            — Flask dashboard (routes, templates, static assets)

demo_target/
  routes/         — Flask route handlers for the sample app
  services/       — business logic for the sample app
  tests/          — pytest tests for the sample app

requirements/     — release requirement definitions (R001–R005, etc.)
reports/          — top-level release reports
reports/agents/   — isolated per-agent JSON reports
scripts/          — utility scripts for running analyses and migrations
docs/             — architecture and product documentation
.bob/             — Bob rules, skills, and configuration
AGENTS.md         — this file
```

### Report ownership

| Agent | Report path |
|---|---|
| Impact Analyst | `reports/agents/impact_report.json` |
| Test Gap Analyst | `reports/agents/test_gap_report.json` |
| Security Analyst | `reports/agents/security_report.json` |
| Contract & Documentation Analyst | `reports/agents/contract_report.json` |
| Database Analyst | `reports/agents/database_report.json` |
| Release Synthesizer | `reports/latest_release_report.json` |

---

## Evidence Requirements

A finding without evidence must not be presented as confirmed.

Every finding must include at least one of the following:

- File path and line number
- Function or class name
- Relevant changed code snippet
- Test name and failure output
- Requirement ID (R001–R005 etc.)
- Actual command output
- Database schema or migration file evidence

Findings that cannot be traced to repository evidence must be marked as unconfirmed and must not influence release status.

---

## No-Invention Rule

**Do not invent metrics or findings.**

**Do not claim release readiness without executable evidence.**

Specifically, Bob must never:

- Invent test results (pass/fail counts, coverage percentages)
- Invent affected files or modules
- Invent security vulnerabilities
- Invent risk levels
- Invent release status
- Present an LLM opinion as a confirmed finding

If a metric cannot be measured from the repository, state that it was not measured rather than estimating.

---

## Safe-Editing Rule

During analysis workstreams, no agent or Bob task may edit application source code. Analysis is read-only. Edits are permitted only during the dedicated Remediation phase, and only for confirmed findings.

When editing application source:
- Make the smallest change that addresses the confirmed finding.
- Do not refactor unrelated code.
- Do not move or rename unrelated files.
- Do not add features not required by the current task.

---

## Analysis vs. Remediation Separation

The workflow has a strict separation:

1. **Analysis phase** — Five agents investigate in parallel and write isolated reports. No source edits.
2. **Synthesis phase** — Release Synthesizer reads all reports and produces a consolidated finding.
3. **Remediation phase** — Confirmed findings are fixed, one at a time, with supporting tests.
4. **Validation phase** — Tests are executed, coverage is measured, reports are regenerated.
5. **Release decision phase** — Final status is determined from actual validation results.

Do not skip phases or compress them into a single step.

---

## Requirement Traceability

Every finding must reference the requirement it relates to where one exists (R001, R002, R003, R004, R005). Remediation tasks must reference the originating finding and requirement. Regression tests must reference the requirement they cover.

---

## Testing Expectations

- New behavior must be covered by tests before it can be marked compliant.
- Regression tests must be added for every confirmed bug fix where applicable.
- Tests must be executed, not assumed to pass.
- Coverage measurement must come from actual tool output.

---

## Metric Integrity Rules

- Do not report coverage percentages without running a coverage tool.
- Do not report test pass counts without executing the test suite.
- Do not report migration counts without inspecting the migrations directory.
- Before/after metrics must compare actual measured values.

---

## Task Focus Instructions

- Prefer focused, single-purpose tasks over large multi-step tasks.
- Each task must have a clear scope and a clear stopping condition.
- Do not expand scope beyond what is explicitly requested.
- Do not modify `README.md` or unrelated documentation unless explicitly asked.
- Do not install dependencies unless explicitly asked.
- Do not create files or directories not required by the current task.
- Use existing project context (this file, `docs/`, `.bob/rules/`) instead of rediscovering architecture from scratch at the start of each task.

---

## No Unnecessary Dependencies

Prefer the standard library and minimal well-known packages. Do not introduce new dependencies without explicit approval. Keep `requirements.txt` entries to only what is needed and used.

---

## No Modification of Unrelated Files

When implementing a fix or feature, touch only the files that are directly required. Do not clean up unrelated code, reformat unrelated files, or reorganize directory structure beyond what the task requires.
