# ShipSafe AI V2 — Multi-Agent Workflow Specification

This document details the agentic execution model, data contracts, and parallel orchestration of the five Grok specialist agents and the Release Synthesizer.

---

## 1. Workflow Architecture & Lifecycle

When a monitored repository event is triggered (via GitHub webhook or manual trigger), the ShipSafe Analysis Worker orchestrates the analysis through four distinct stages:

```
[ STAGE 1: DETERMINISTIC EXTRACTION ]
├── Clone / checkout base & head commits
├── Generate structured Git diff & changed symbol map
├── Discover tests, frameworks, and run test suites
├── Discover API routes, OpenAPI schemas, and Markdown/PDF requirements
├── Discover database migrations, ORM entities, and package manifests
└── Construct redacted Evidence Pack

[ STAGE 2: PARALLEL AGENT EXECUTION ]
Concurrent dispatch with curated evidence:
├── Agent 1: Change Impact Agent        (Imports, callsites, affected workflows)
├── Agent 2: Test Gap Agent             (Missing regression tests, coverage gaps)
├── Agent 3: Security Agent             (CWE vulnerabilities, injection, secrets)
├── Agent 4: Requirements & API Agent   (Contract drift, specification compliance)
└── Agent 5: Database & Dependency Agent(Schema drift, unversioned migrations)

[ STAGE 3: SYNTHESIS & RELEASE GATE ]
├── Deduplicate overlapping findings across agents
├── Detect cross-agent conflicts (e.g. database vs. contract recommendations)
├── Build release blast radius simulation & regression paths
├── Derive authoritative Release Gate: READY / ATTENTION / BLOCKED
└── Formulate prioritized remediation actions

[ STAGE 4: PERSISTENCE & OBSERVABILITY ]
├── Persist AnalysisRun, AgentRuns, Findings, and Actions in Database
├── Broadcast state update to Streamlit DevSecOps console
└── Expose structured results via REST API
```

---

## 2. Agent Input Contract: The Evidence Pack

Every agent receives a specialized slice of the **Evidence Pack** produced deterministically by `shipsafe/core/evidence.py`. The Evidence Pack contains only verified facts:

```json
{
  "repository": {
    "name": "example-repo",
    "base_sha": "a1b2c3d4e5",
    "head_sha": "f6g7h8i9j0",
    "branch": "main",
    "primary_language": "python"
  },
  "git_diff": {
    "files_changed": [
      {
        "path": "routes/appointments.py",
        "status": "modified",
        "additions": 4,
        "deletions": 2,
        "hunks": ["@@ -35,6 +35,8 @@ ..."]
      }
    ],
    "changed_symbols": [
      {
        "file": "routes/appointments.py",
        "symbol": "search_appointments",
        "kind": "function",
        "lines": [35, 48]
      }
    ]
  },
  "tests": {
    "discovered_framework": "pytest",
    "total": 42,
    "passed": 42,
    "failed": 0,
    "statement_coverage_percent": 98.0,
    "missing_coverage_lines": []
  },
  "contracts_and_requirements": {
    "requirements_documents": ["requirements/CareHub_v2_4_Requirements.md"],
    "clauses": [
      {"id": "R001", "text": "Cancelled appointments must not generate reminder notifications."}
    ],
    "openapi_endpoints": [
      {"path": "/appointments/search", "method": "GET"}
    ]
  },
  "persistence_and_dependencies": {
    "migrations": ["migrations/001_initial_schema.sql"],
    "manifests": ["requirements.txt"]
  }
}
```

---

## 3. Strict Redaction & Privacy

Before dispatching the Evidence Pack to the AI provider, the **Secret Redaction Filter** (`shipsafe/core/evidence.py`) scrubs:
- High-entropy tokens, AWS keys (`AKIA...`), and bearer tokens.
- Password assignments (`password = "..."`).
- Connection strings (`postgres://user:pass@host/db`).
- Private certificates and RSA keys.
- Ignored file types: `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.sqlite`, `.git/*`.

---

## 4. Structured Output Contract

Every agent must return valid JSON strictly conforming to the `AgentOutput` Pydantic schema:

```json
{
  "agent": "security_agent",
  "findings": [
    {
      "finding_id": "SEC-001",
      "severity": "CRITICAL",
      "title": "Unsafe SQL String Concatenation",
      "description": "User input from query parameter 'status' is formatted directly into a raw SQL query string.",
      "file": "routes/appointments.py",
      "line_start": 38,
      "line_end": 42,
      "evidence": "query = f\"SELECT * FROM appointments WHERE status = '{status}'\"",
      "affected_components": ["COMP-SEARCH-API"],
      "recommendation": "Use parameterized query placeholders (?, :status) with query_db.",
      "confidence": 0.95
    }
  ],
  "summary": "Detected 1 critical SQL injection vulnerability in appointment search route.",
  "confidence": 0.95
}
```

---

## 5. Evidence Verification Gate

Before any finding is saved or surfaced:
1. `file` must exist in the target repository at the head commit.
2. `line_start` and `line_end` (if present) must fall within actual file line bounds.
3. The referenced `evidence` must match or be closely grounded in actual file content.
4. Findings failing verification are marked `UNVERIFIED` and barred from blocking the release gate.
