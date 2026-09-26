# ShipSafe AI V2 — Product Specification

**Product Name:** ShipSafe AI  
**Tagline:** Continuous Release Safety Monitor  
**Core Promise:** *"Every time a monitored repository changes, ShipSafe investigates the change and determines what could break before it reaches production."*  
**Version:** 2.0.0 (Release Safety Platform)  
**Hackathon Target:** IBM Bob 2.0 Hackathon  

---

## 1. Product Overview

ShipSafe AI is an automated, repository-independent release safety monitor that guards production deployments against regressions, vulnerabilities, contract drifts, and missing tests.

Whenever a commit is pushed or a pull request is opened, ShipSafe automatically executes an evidence-backed analysis lifecycle:
1. Detects and parses the change deterministically from Git.
2. Extracts concrete evidence: diffs, changed symbols, tests, coverage, OpenAPI routes, database schemas, and requirement documents.
3. Dispatches the redacted evidence pack to five parallel Grok AI specialist agents.
4. Synthesizes findings, highlights architectural conflicts, and derives an authoritative release status (`READY`, `ATTENTION`, or `BLOCKED`).
5. Presents a clear DevSecOps console for developers and release managers in Streamlit.
6. Proposes actionable remediation patches that can be reviewed, applied, and verified with live regression tests before production merge.

---

## 2. Event-Driven Continuous Monitoring

ShipSafe AI integrates with GitHub via standard webhook deliveries (`POST /webhooks/github`).

### Monitored Events
- `push`: Triggered on commit pushes to monitored branches (e.g. `main`, `master`, `release/*`). Executes change-impact analysis and continuous health tracking.
- `pull_request.opened`: Full pre-merge release gate evaluation.
- `pull_request.synchronize`: Re-evaluates when new commits are pushed to an open pull request.
- `pull_request.reopened`: Re-evaluates release readiness.
- `pull_request.closed`: Updates monitoring state and records merge/close history.

### Webhook Security & Idempotency
- **Signature Verification:** Validates `X-Hub-Signature-256` using HMAC-SHA256 with the configured `GITHUB_WEBHOOK_SECRET`. Invalid requests return `401 Unauthorized`.
- **Deduplication:** Every event is tracked by `X-GitHub-Delivery`. If a delivery ID is received multiple times, ShipSafe returns `200 OK (Duplicate Ignored)` without duplicating analysis runs.
- **Fast Acknowledgment:** The webhook endpoint verifies the payload, persists the `WebhookEvent`, enqueues a background `AnalysisRun`, and responds with `HTTP 202 Accepted` in `< 50ms`.

---

## 3. Supported Repositories & Discovery

ShipSafe AI operates on **arbitrary software repositories** with zero hard-coded assumptions:
- **Languages:** Python (`pytest`, `unittest`), JavaScript / TypeScript (`jest`, `mocha`, `npm test`), Java (`junit`, `maven`, `gradle`), SQL / Migrations, and mixed full-stack repositories.
- **Auto-Discovery Engine (`shipsafe/core/discovery.py`):**
  - Identifies project root, languages, and build tools.
  - Discovers dependency manifests (`requirements.txt`, `pyproject.toml`, `package.json`, `pom.xml`, `build.gradle`, `go.mod`).
  - Discovers tests and test configuration files (`pytest.ini`, `conftest.py`, `package.json`, `pom.xml`).
  - Discovers requirements and specifications (`requirements/*.md`, `*.pdf`, `README.md`, `docs/`).
  - Discovers API contracts (`openapi.json`, `openapi.yaml`, `swagger.json`, route decorators).
  - Discovers persistence artifacts (`migrations/`, `sql/`, `schema.sql`, `prisma/schema.prisma`).

---

## 4. Five Specialist Agents & Release Synthesizer

ShipSafe AI employs five specialized Grok AI agents (`grok-4.7`) orchestrated in parallel, followed by a deterministic Release Synthesizer:

### 1. Change Impact Agent
- **Core Question:** *"What changed and what parts of the system can this change affect?"*
- **Investigation:** AST call graphs, imported modules, routes, services, shared configuration.
- **Outputs:** Changed components, affected components, impacted user-facing workflows, confidence score.

### 2. Test Gap Agent
- **Core Question:** *"Did the change introduce behavior that is not adequately covered?"*
- **Investigation:** Modified code lines vs. executed test coverage, deleted test functions, unasserted response attributes, edge case branches.
- **Outputs:** Missing regression paths, deleted tests, unverified behaviors, concrete test recommendations.

### 3. Security Agent
- **Core Question:** *"Did the change introduce a security weakness?"*
- **Investigation:** CWE catalog checks (CWE-89 SQLi, CWE-78 Command Injection, CWE-22 Path Traversal, CWE-502 Deserialization, hardcoded secrets, insecure CORS/auth).
- **Outputs:** Specific vulnerabilities with exact file, line start/end, code snippet, severity, and remediation advice.

### 4. Requirements & API Agent
- **Core Question:** *"Does the implementation still match requirements and external contracts?"*
- **Investigation:** Compares code behavior against Markdown/PDF requirements, OpenAPI schemas, and documentation.
- **Outputs:** Non-compliant requirement clauses, breaking API changes, parameter discrepancies.

### 5. Database & Dependency Agent
- **Core Question:** *"Are persistence and dependencies still consistent with the change?"*
- **Investigation:** Compares model/entity definitions against SQL migrations; checks for unversioned table constraints, schema drifts, and risky dependency additions.
- **Outputs:** Schema drifts, missing migrations, dependency vulnerability flags.

### 6. Release Synthesizer
- **Consolidation:** Ingests the 5 agent reports, deduplicates overlapping findings, and surfaces cross-agent recommendation conflicts.
- **Release Blast Radius Simulation:** Deterministically traces potential failure chains:  
  `Commit → Modified Line → Component → API Route → Database → Affected Workflow → Impacted Users`.
- **Authoritative Gate Decision:** Computes final release gate.

---

## 5. Release Gate Logic

The Release Gate is derived from concrete evidence, not arbitrary probabilistic scores:

```
[ CRITICAL finding exists ] ─────────────► BLOCKED
[ Failing change-related tests ] ────────► BLOCKED
[ Confirmed blocking requirement gap ] ──► BLOCKED
[ Unmigrated database schema drift ] ────► BLOCKED

[ HIGH finding without mitigation ] ─────► ATTENTION
[ Meaningful regression test gap ] ──────► ATTENTION
[ API contract / schema warning ] ───────► ATTENTION
[ Requirement ambiguity / warning ] ────► ATTENTION

[ All required tests pass ]
[ Zero CRITICAL or HIGH blockers ] ──────► READY
[ Requirements verified compliant ]
[ Database schema verified ]
```

---

## 6. Streamlit DevSecOps Console Specification

The user interface is an enterprise engineering console designed in Streamlit:
- **Style:** Clean light/graphite theme, clear contrast, monospace code formatting for symbols and SHAs, compact status badges (`READY` in green, `ATTENTION` in amber, `BLOCKED` in red).
- **No Chatbots:** No avatars, no conversational bubbles, no neon glassmorphism.
- **Navigation (10 Sections):**
  1. **Overview:** Fleet status across all monitored repositories, active release gates, blocker count.
  2. **Repositories:** Manage monitored Git repositories, trigger manual evaluations, view branches.
  3. **Live Events:** Real-time stream of GitHub webhook deliveries, delivery IDs, payloads, and processing stages.
  4. **Release Runs:** Historical log of analysis runs with duration, commit SHAs, test counts, and gate results.
  5. **Findings:** Filterable table of all detected findings with severity badges, evidence drawers, and file links.
  6. **Impact Map:** Interactive visual flowchart tracing changes from commit to workflows.
  7. **Requirements:** Matrix linking requirements directly to verified implementation files and test results.
  8. **Release Simulation:** Blast radius visualization detailing affected customer workflows and regression paths.
  9. **Remediation:** Patch inspection, unified diff preview, `[ APPLY PATCH ]` button, test re-runner, and before/after verification.
  10. **Settings:** Provider configuration (`AI_PROVIDER`, `XAI_MODEL`), webhook secrets, database connection string.

---

## 7. Evidence Verification & Privacy Guarantees

1. **Zero Hallucination Display:**  
   Before any agent finding is rendered in the UI, ShipSafe validates:
   - The file exists on disk in the target repository at the checked-out commit.
   - Line numbers exist within the file's line boundaries.
   - Snippet text matches the actual source lines.
   - Findings that fail verification are filtered out or flagged as unconfirmed.
2. **Strict Secret Redaction:**  
   Before sending any evidence to Grok:
   - Secret files (`.env`, `.pem`, `id_rsa`, `*.key`) are completely excluded.
   - Regex scrubbers redact API keys, JWTs, AWS credentials, bearer tokens, connection strings, and passwords.
   - Binary files and virtual environments (`.venv/`, `node_modules/`, `.git/`) are ignored.

---

## 8. Truthful Attribution: IBM Bob 2.0 & Grok

- **IBM Bob 2.0:** Orchestrated the original multi-agent development environment, agent mode tasks, and historical analysis workstreams. All historical Bob analysis artifacts are preserved in `archive/` and documented in `docs/BOB_USAGE.md`.
- **Grok (xAI):** Powers the live, event-driven runtime multi-agent analysis for monitored GitHub repositories.
- The two systems are strictly and truthfully differentiated throughout the documentation and codebase.
