# ShipSafe AI V2

> **Continuous Release Safety Monitor**
> *"Every time a monitored repository changes, ShipSafe investigates the change and determines what could break before it reaches production."*

ShipSafe AI V2 is an event-driven, repository-independent continuous release safety platform. It transforms release validation from a subjective, last-minute manual checklist into an automated, evidence-backed guardian. Powered by **Grok-4.7** specialist agents and a deterministic repository engine, ShipSafe monitors GitHub commits and pull requests, uncovers hidden regressions, security flaws, test gaps, and schema drifts, and provides verified remediation before bad code hits production.

---

## The Problem

Modern software teams ship frequently, but standard CI/CD and pull request reviews regularly miss high-risk, cross-cutting failures:
- **Test Gap Masking**: Deleted or weakened tests turn failing CI pipelines green without testing new business logic paths.
- **Contract & API Drift**: Unversioned endpoint changes break mobile or third-party client contracts.
- **Silent Security Regressions**: Query parameter formatting introduces SQL injection (CWE-89) or path traversal vulnerabilities.
- **Unmigrated Schema & Persistence Conflicts**: ORM models add non-nullable fields or new domain states without database migration scripts.
- **Sample Bias & Hard-Coded Gates**: Legacy validation tools rely on sample app conventions or arbitrary statistical scores instead of deterministic code evidence.

---

## The Product: Continuous Release Safety Monitor

ShipSafe AI V2 is built for **arbitrary repositories** across multiple languages (Python, JavaScript/TypeScript, Java, SQL, and mixed stacks).

### Key Features
- **Event-Driven Continuous Monitoring**: GitHub Webhook listener (`push`, `pull_request.opened`, `pull_request.synchronize`) with cryptographic HMAC validation and delivery deduplication.
- **Deterministic Evidence Engine**: Extracts real git diffs, changed symbols, AST call graphs, test execution outputs, OpenAPI specs, database schemas, and requirement documents. Never asks an LLM to hallucinate repository facts.
- **Five Parallel Grok Specialist Agents**: Concurrent deep-investigation agents (Impact, Test Gap, Security, Requirement/API, Database/Dependency) driven by Grok-4.7.
- **Deterministic Release Gate**: An authoritative decision matrix calculating **READY**, **ATTENTION**, or **BLOCKED** based strictly on verified code evidence.
- **Release Impact Simulation**: Maps commit changes to affected files, components, APIs, database tables, and user workflows.
- **Verified Remediation & Recheck**: Generates concrete code patches, applies them in a safe sandbox, re-runs tests, and proves the fix resolves blockers.
- **Enterprise Streamlit Console**: High-density engineering dashboard featuring live event streams, release run histories, impact graphs, and patch inspection.

---

## Runtime Architecture

```
                    GITHUB
                       │
              push / pull request
                       │
                       ▼
               FASTAPI WEBHOOK
              /webhooks/github
                       │ (HMAC Verify, Deduplicate, Enqueue)
                       ▼
               ANALYSIS WORKER
              worker/worker.py
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
     Git Engine   Test Runner   Docs/Schema
         └─────────────┬─────────────┘
                       ▼
                 Evidence Pack (Deterministic)
                       │
                       ▼
             PARALLEL GROK AGENTS (grok-4.7)
         ┌──────┬──────┼──────┬──────┐
         ▼      ▼      ▼      ▼      ▼
       Impact  Test  Security Req/  DB/Dep
               Gap            API
         └──────┴──────┼──────┴──────┘
                       ▼
              RELEASE SYNTHESIZER
            (READY / ATTENTION / BLOCKED)
                       │
                       ▼
           SQLite / PostgreSQL Store
                       │
                       ▼
              STREAMLIT CONSOLE
             (streamlit_app.py)
```

---

## Truthful Hackathon Attribution: IBM Bob 2.0 & Grok

This project was built for the **IBM Bob 2.0 Hackathon**. We maintain strict technical integrity regarding tooling roles:
- **IBM Bob 2.0**: Used as the **development and orchestration environment**. Bob's Agent mode, parallel subagents, and document understanding drove the architectural transition, design constraints, and rule enforcement. Historical Bob analysis artifacts are preserved in `archive/reports/` and `.bob/` for complete auditability.
- **Grok (xAI)**: Powers the **live continuous runtime AI agents** (`grok-4.7`). When GitHub sends a webhook, the worker dispatches concurrent investigative tasks to Grok.
- *Full details: See [`docs/BOB_USAGE.md`](docs/BOB_USAGE.md).*

---

## Monitored Repositories & The CareHub Example

ShipSafe AI is **repository-independent**. It does not assume any particular repository structure, model name, or test framework.

To demonstrate its capabilities, the repository includes a complete standalone healthcare application in:
```
examples/carehub/
```
The CareHub appointment service contains realistic routes, SQLite persistence, and pytest suites. In the Streamlit UI, it is exposed as **"Example Repository"** and undergoes the exact same deterministic analysis, agent investigations, and remediation flows as any production codebase.

---

## Directory Structure

```
shipsafe-ai/
├── api/                    # FastAPI Webhook and REST API
│   ├── app.py              # Application entrypoint
│   └── routes/             # Webhooks, repositories, analysis runs, remediation
├── shipsafe/
│   ├── core/               # Deterministic Evidence Engine
│   │   ├── repository.py   # Target repository abstraction
│   │   ├── git.py          # Git history, diffs, branch inspection
│   │   ├── discovery.py    # Auto-detection of languages, frameworks, APIs, schemas
│   │   ├── test_runner.py  # Deterministic test runner (pytest, npm, maven)
│   │   ├── document_parser.py # Markdown, PDF, OpenAPI requirement parser
│   │   ├── secrets.py      # Secret detection & redaction filter
│   │   └── evidence.py     # Deterministic evidence pack generator & validator
│   ├── ai/                 # Grok AI Provider
│   │   ├── provider.py     # Base abstract AI provider
│   │   ├── grok_client.py  # xAI REST API integration (grok-4.7)
│   │   └── schemas.py      # Pydantic schemas for agent JSON outputs
│   ├── agents/             # Five specialist agents & synthesizer
│   │   ├── impact_agent.py
│   │   ├── test_gap_agent.py
│   │   ├── security_agent.py
│   │   ├── contract_agent.py
│   │   ├── database_agent.py
│   │   └── synthesizer.py
│   └── database/           # SQLAlchemy models & database migrations
│       ├── models.py       # Repositories, WebhookEvents, AnalysisRuns, Findings
│       └── session.py      # DB session management (SQLite / Postgres)
├── worker/
│   └── worker.py           # Background job worker
├── streamlit_app.py        # Streamlit DevSecOps engineering console
├── examples/
│   └── carehub/            # Standalone CareHub example application
├── scripts/                # Local simulation & seeding tooling
│   ├── simulate_webhook.py # Local GitHub webhook simulator
│   ├── seed_demo.py        # Initial demo database populator
│   └── run_local_stack.py  # One-command stack runner
├── tests/                  # Pytest test suite for core, API, agents, gate
├── docs/                   # Comprehensive technical documentation
├── archive/                # Historical IBM Bob 2.0 analysis reports
├── requirements.txt
└── .env.example
```

---

## Local Setup & Quickstart

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Environment Setup
```bash
git clone https://github.com/dradhikac/shipsafe-ai.git
cd shipsafe-ai

python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 3. Launching the Local Stack

You can launch the components individually or using the convenience runner:

#### Option A: One-Command Stack
```bash
python scripts/run_local_stack.py
```

#### Option B: Component by Component
Terminal 1 (FastAPI Webhook & REST API):
```bash
uvicorn api.app:app --reload --port 8000
```

Terminal 2 (Analysis Worker):
```bash
python -m worker.worker
```

Terminal 3 (Streamlit DevSecOps Console):
```bash
streamlit run streamlit_app.py --server.port 8501
```

### 4. Simulating a GitHub Event
To test without configuring a public GitHub URL, use the local event simulator:
```bash
python scripts/simulate_webhook.py --event push --repo examples/carehub --branch feature/billing-v2
```

---

## Security & Secrets Policy

ShipSafe AI adheres to zero-trust data privacy:
- **Strict Redaction**: Deterministic filters purge API keys, bearer tokens, private keys, database passwords, and connection strings before any evidence pack is transmitted to Grok.
- **Ignored Files**: `.env`, `.env.*`, `node_modules`, `.git`, virtual environments, and binary executables are strictly ignored.
- **HMAC Signature Check**: Webhooks without a valid `X-Hub-Signature-256` matching `GITHUB_WEBHOOK_SECRET` are immediately rejected with `401 Unauthorized`.
