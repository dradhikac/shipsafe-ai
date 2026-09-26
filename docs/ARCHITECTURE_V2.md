# ShipSafe AI V2 — Architecture Specification

> **Continuous Release Safety Monitor**  
> *"Every time a monitored repository changes, ShipSafe investigates the change and determines what could break before it reaches production."*

---

## 1. System Vision & Paradigm Shift

ShipSafe AI V1 was a proof-of-concept release readiness system tightly coupled to a single sample application (`CareHub`) with static JSON report generation. 

**ShipSafe AI V2** transitions the system into an **event-driven, repository-independent continuous release safety platform**. It ingests live GitHub webhook events, performs deterministic codebase and evidence analysis, orchestrates five parallel Grok AI specialist agents, synthesizes actionable release determinations (`READY`, `ATTENTION`, `BLOCKED`), and presents an interactive enterprise DevSecOps console via Streamlit backed by a relational database (SQLite / PostgreSQL).

```
                                  GITHUB
                                     |
                          push / pull_request event
                                     |
                                     v
                       FASTAPI WEBHOOK ENGINE (:8000)
                       [Signature Verification, Deduplication]
                                     |
                                Enqueue Job
                                     v
                          PERSISTENT DATABASE
                       [SQLite / PostgreSQL (SQLAlchemy)]
                                     |
                              Claim Pending Job
                                     v
                           ANALYSIS WORKER
                   +-----------------+-----------------+
                   |                 |                 |
              Git Engine        Test Engine       Docs Engine
             (Diff/Symbols)    (Pytest/Jest)     (Reqs/OpenAPI)
                   |                 |                 |
                   +-----------------+-----------------+
                                     |
                              Evidence Pack
                       [Redacted, Concrete Snippets]
                                     |
                                     v
                        PARALLEL GROK AGENTS (grok-4.7)
        +---------------+---------------+---------------+---------------+
        |               |               |               |               |
     Impact          Test Gap        Security      Requirements    DB / Dependency
      Agent           Agent           Agent         & API Agent        Agent
        |               |               |               |               |
        +---------------+---------------+---------------+---------------+
                                     |
                            Structured Findings
                                     |
                                     v
                           RELEASE SYNTHESIZER
                     [Cross-Agent Conflict Resolution]
                                     |
                     +---------------+---------------+
                     |                               |
                Release Gate                Impact Simulation
           [READY/ATTENTION/BLOCKED]     [Regression Paths/Workflows]
                     |                               |
                     +---------------+---------------+
                                     |
                            Persisted Results
                                     |
                                     v
                       STREAMLIT CONSOLE (:8501)
               [Overview | Repos | Events | Runs | Findings |
                Impact Map | Requirements | Simulation | Remediation]
```

---

## 2. Architectural Principles

1. **Repository-Independent Core:**  
   The core analysis engines (`shipsafe/core/`) make zero assumptions about repository name, business domain, or file structure. The previous demo (`CareHub`) resides as an example in `examples/carehub/`.
2. **Event-Driven & Asynchronous:**  
   GitHub webhooks are acknowledged immediately (`HTTP 202 Accepted`). Long-running deterministic analysis and AI reasoning run asynchronously in worker processes.
3. **Deterministic First, AI Second:**  
   All objective repository facts (changed files, diff hunks, test results, statement coverage, schema constraints, OpenAPI endpoints) are extracted deterministically before LLM invocation. Grok is never asked to hallucinate file paths or line numbers.
4. **Concrete Evidence Packs & Strict Privacy:**  
   Agents receive curated evidence packs with strict redaction of credentials, API keys, tokens, `.env` files, and binaries.
5. **Parallel Multi-Agent Specialization:**  
   Five specialist agents run concurrently using thread/task concurrency for network-bound Grok invocations.
6. **Structured Output Contracts:**  
   Every agent emits strictly validated Pydantic JSON schemas.
7. **Strict Evidence Verification Gate:**  
   Before any agent finding is surfaced, ShipSafe validates that the referenced file exists in the repository, line numbers align, and the finding relates to the investigated commit. Unsupported claims are rejected.
8. **Relational Persistence:**  
   All events, runs, findings, and remediation proposals are persisted in a relational database with historical traceability.

---

## 3. Directory Layout & Module Responsibilities

```
shipsafe-ai/
├── api/                           # FastAPI Webhook and REST API
│   ├── __init__.py
│   ├── app.py                    # App factory, CORS, exception handlers
│   ├── routes/
│   │   ├── health.py             # Health check endpoint
│   │   ├── webhooks.py           # GitHub webhook receiver (HMAC verification)
│   │   ├── repositories.py       # Repo registration & manual triggers
│   │   └── runs.py               # Analysis run inspection & remediation APIs
├── worker/                        # Background Analysis Engine
│   ├── __init__.py
│   └── worker.py                 # Job consumer, pipeline runner, lifecycle manager
├── shipsafe/
│   ├── core/                     # Deterministic Evidence Engine
│   │   ├── __init__.py
│   │   ├── repository.py         # Repo manager, local & remote clone handling
│   │   ├── git.py                # Git operations (commits, branches, log)
│   │   ├── diff.py               # AST/diff parser, symbol changes, hunk analysis
│   │   ├── discovery.py          # Auto-discovery (Python, Java, JS/TS, SQL)
│   │   ├── test_runner.py        # Framework runner (pytest, npm test, etc.)
│   │   ├── document_parser.py    # Markdown, PDF, OpenAPI, and README parser
│   │   └── evidence.py           # Evidence pack aggregator & secret redactor
│   ├── ai/                       # Grok AI Layer
│   │   ├── __init__.py
│   │   ├── provider.py           # Abstract AIProvider interface
│   │   ├── grok_client.py        # xAI Grok-4.7 integration (HTTP REST + SDK fallback)
│   │   └── schemas.py            # Pydantic schemas for agent inputs and outputs
│   ├── agents/                   # Five Specialist Agents + Synthesizer
│   │   ├── __init__.py
│   │   ├── impact_agent.py       # 1. Change Impact Agent
│   │   ├── test_gap_agent.py     # 2. Test Gap Agent
│   │   ├── security_agent.py     # 3. Security Agent (CWE checks)
│   │   ├── contract_agent.py     # 4. Requirements & API Agent
│   │   ├── database_agent.py     # 5. Database & Dependency Agent
│   │   └── synthesizer.py        # 6. Release Synthesizer & Release Gate
│   ├── database/                 # Persistence Layer
│   │   ├── __init__.py
│   │   ├── session.py            # SQLAlchemy engine, session maker
│   │   ├── models.py             # Repositories, Events, Runs, Findings, etc.
│   │   └── crud.py               # Data access helpers
│   └── remediation/              # Remediation Engine
│       ├── __init__.py
│       ├── patch_generator.py    # Generates unified diff patches
│       └── patch_applier.py      # Dry-run validation and atomic patch application
├── streamlit_app.py              # Streamlit Engineering Dashboard
├── scripts/                      # Local Stack & Simulation Tooling
│   ├── simulate_webhook.py       # Local push & PR event generator
│   ├── seed_demo.py              # Initial database seed script
│   └── run_local_stack.py        # Launches API, Worker, and Streamlit
├── examples/                     # Monitored Repositories
│   └── carehub/                  # CareHub Clinic Service (retained as example)
├── archive/                      # Historical IBM Bob 2.0 Reports & V1 Artifacts
├── docs/                         # Specifications & Product Docs
└── tests/                        # Comprehensive Pytest Suite
```

---

## 4. Deterministic Evidence Engine (`shipsafe/core/`)

The deterministic evidence engine discovers and extracts facts from arbitrary repositories:

1. **`repository.py`**: Resolves repository sources (local file path or remote Git URL). Manages working copies, checkout target commits (`base_sha` -> `head_sha`), and clean tear-down.
2. **`git.py`**: Interacts with Git CLI to retrieve commits, author metadata, tags, and branches.
3. **`diff.py`**: Computes two-way diffs between `base` and `head`. Categorizes changes into Added, Modified, Renamed, Deleted. Extracts hunk line numbers and identifies modified functions/classes using regex and AST where available.
4. **`discovery.py`**: Automatically identifies project languages (Python, JavaScript/TypeScript, Java, Go, SQL), framework types, test directories, package manifests (`requirements.txt`, `package.json`, `pom.xml`, `go.mod`), schema directories (`migrations/`, `sql/`, `schema.prisma`), and API specifications (`openapi.json`, `swagger.yaml`).
5. **`test_runner.py`**: Executes available test suites in isolated sandboxes and collects pass/fail counts, failure tracebacks, and statement coverage.
6. **`document_parser.py`**: Extracts requirement clauses from Markdown (`requirements/*.md`), PDF specifications, and OpenAPI route contracts.
7. **`evidence.py`**: Assembles a bounded, redacted **Evidence Pack** JSON:
   - Git diff summary and snippets
   - Changed symbols and caller references
   - Test execution results and missing coverage
   - Documented requirements and external contracts
   - Migration files and schema definitions
   - Strict redactor that scrubs API keys, bearer tokens, passwords, and private certificates.

---

## 5. Parallel Grok Specialist Agents (`shipsafe/agents/`)

Every agent queries Grok (`grok-4.7`) with a targeted prompt, the curated evidence pack, and an immutable JSON output schema.

| Agent | Focus Question | Key Inputs | Key Outputs |
|---|---|---|---|
| **Impact Agent** | *What changed and what parts of the system can this change affect?* | Git diff, changed symbols, caller references, dependency graph | Changed components, affected components, impacted workflows |
| **Test Gap Agent** | *Did the change introduce behavior that is not adequately covered?* | Modified code lines, test list, coverage gap lines, test deletions | Missing regression paths, untested edge cases, missing test files |
| **Security Agent** | *Did the change introduce a security weakness?* | Changed code hunks, dependency manifest changes, route parameters | CWE findings (SQLi, Command Injection, Path Traversal, Auth bypass, Hardcoded secrets) |
| **Contract Agent** | *Does the implementation still match requirements and external contracts?* | Requirements documents, OpenAPI definitions, route handler changes | Requirement conflicts, API contract breaking changes, schema mismatches |
| **Database Agent** | *Are persistence and dependencies still consistent with the change?* | Models, ORM schemas, migration scripts, package manifests | Unmigrated schema changes, constraint drifts, breaking dependency upgrades |

### Agent Output Contract

```json
{
  "agent": "security_agent",
  "findings": [
    {
      "finding_id": "SEC-001",
      "severity": "CRITICAL",
      "title": "Unsafe SQL Query Concatenation",
      "description": "User-supplied status parameter is concatenated directly into SQL statement.",
      "file": "demo_target/routes/appointments.py",
      "line_start": 38,
      "line_end": 42,
      "evidence": "query = f\"SELECT * FROM appointments WHERE status = '{status}'\"",
      "affected_components": ["COMP-SEARCH-API"],
      "recommendation": "Use parameterized query placeholders (?, :status).",
      "confidence": 0.98
    }
  ]
}
```

---

## 6. Release Gate & Synthesizer

The **Release Synthesizer** consumes only the verified outputs from the five agents:
1. **Deduplication:** Aggregates related findings from multiple agents into unified issues.
2. **Conflict Detection:** Identifies contradictory agent recommendations (e.g. Database Analyst advising migration for a column that the Contract Analyst identifies as unauthorized).
3. **Release Gate Determination:**
   - **`BLOCKED`**: Any confirmed `CRITICAL` finding, any failing test on changed code, any confirmed blocking requirement violation, or confirmed unmigrated schema drift.
   - **`ATTENTION`**: Any unresolved `HIGH` severity finding, meaningful test gaps, or non-critical API/requirement warnings.
   - **`READY`**: Zero critical or high blockers, all required tests pass, all requirements validated.
4. **Release Blast Radius Simulation:** Deterministically traces potential failure chains:
   `Commit → Changed File → Component → API → Database → Affected Workflow → Impacted Users`.

---

## 7. Streamlit DevSecOps Console (`streamlit_app.py`)

A clean, light/graphite enterprise software console for release engineers:
1. **Overview:** Monitored repositories, active release gates (`READY`/`ATTENTION`/`BLOCKED`), open blocker counts.
2. **Repositories:** Repository registry, branch tracking, manual trigger buttons.
3. **Live Events:** Real-time stream of incoming GitHub webhook events with delivery IDs, payload metadata, and processing stages.
4. **Release Runs:** Historical log of analysis runs with duration, commits, and summary statistics.
5. **Findings:** Filterable table of all detected findings with severity badges, evidence drawers, and file/line links.
6. **Impact Map:** Interactive visual flowchart tracing changes through the application stack.
7. **Requirements:** Matrix linking requirements directly to verified implementation files and test results.
8. **Release Simulation:** Blast radius visualization detailing affected customer workflows.
9. **Remediation:** Patch inspection, unified diff preview, `[ APPLY PATCH ]` button, test re-runner, and before/after verification.
10. **Settings:** Provider configuration (`AI_PROVIDER`, `XAI_MODEL`), webhook secrets, database connection string.

---

## 8. Development & Implementation Roadmap

```
PHASE 0: Git safety baseline (shipsafe-v1-archive branch created)
PHASE 1: Architecture & product specifications (docs/ARCHITECTURE_V2.md, docs/PRODUCT_SPEC_V2.md)
PHASE 2: Deterministic Evidence Engine (shipsafe/core/*)
PHASE 3: GitHub Webhook Ingestion & API (api/*)
PHASE 4: Persistent Database & Analysis Job Queue (shipsafe/database/*, worker/*)
PHASE 5: Grok Provider & 5 Specialist Agents (shipsafe/ai/*, shipsafe/agents/*)
PHASE 6: Release Synthesizer, Gate & Simulation Engine
PHASE 7: Streamlit DevSecOps Console (streamlit_app.py)
PHASE 8: Remediation & Recheck Engine (shipsafe/remediation/*)
PHASE 9: Local Simulation Tooling (scripts/*)
PHASE 10: Complete Test Suite & End-to-End Validation
PHASE 11: Deployment Configuration (PostgreSQL, Docker, Streamlit Cloud)
PHASE 12: Final Quality Audit & Single Final Git Commit
```
