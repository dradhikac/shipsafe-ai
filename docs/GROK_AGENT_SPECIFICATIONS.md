# Grok Agent Specifications — ShipSafe AI V2

## Overview
ShipSafe AI V2 uses **Grok-4.7** (via official xAI REST integration) to power five specialist release-guardian agents in parallel, followed by a Release Synthesizer.

Each agent receives a deterministically assembled **Evidence Pack** and answers one specific investigative question. Agents are strictly read-only and return structured JSON conforming to the ShipSafe agent schema.

---

## 1. Change Impact Agent

### Investigative Question
> *"What changed and what parts of the system can this change affect?"*

### Primary Responsibilities
- Maps changed files and symbols (functions, classes, routes) to downstream consumers.
- Identifies callers, imports, models, and shared utilities affected by the diff.
- Determines which user workflows, API contracts, or background tasks may experience behavior changes.
- Evaluates blast radius (Direct / Transitive / System-Wide).

### Input Focus
- `diff.files`, `diff.patch`
- `discovery.routes`, `discovery.models`, `discovery.services`
- Dependency call graphs / AST import maps

### Output Contract
```json
{
  "agent": "impact",
  "findings": [
    {
      "finding_id": "IMP-001",
      "severity": "HIGH|MEDIUM|LOW|INFO",
      "title": "Unbounded blast radius in patient authentication workflow",
      "description": "Modification of token verification alters downstream session validation across all authenticated endpoints.",
      "file": "services/auth_service.py",
      "line_start": 42,
      "line_end": 58,
      "evidence": "def verify_token(token): ...",
      "affected_components": ["AuthService", "UserRoutes", "AppointmentRoutes"],
      "recommendation": "Preserve legacy token fallback or version the authentication header signature.",
      "confidence": 0.95
    }
  ]
}
```

---

## 2. Test Gap Agent

### Investigative Question
> *"Did the change introduce behavior that is not adequately covered?"*

### Primary Responsibilities
- Correlates changed functions, branches, and edge cases with existing test suites.
- Flags modified code paths that have zero covering tests or missing failure-mode assertions.
- Identifies deleted tests, skipped tests, or weakened test fixtures.
- Pinpoints regression risks where previous invariants are no longer asserted.

### Input Focus
- `test_runner.summary`, `test_runner.failures`
- `test_runner.test_files`
- `diff.changed_functions`, `diff.deleted_lines`
- `evidence.code_snippets`

### Output Contract
```json
{
  "agent": "test_gap",
  "findings": [
    {
      "finding_id": "GAP-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Missing regression tests for modified discount validation logic",
      "description": "New branch handling negative discounts in calculate_total has no unit or integration tests.",
      "file": "services/billing.py",
      "line_start": 88,
      "line_end": 96,
      "evidence": "if discount < 0: return base_price",
      "affected_components": ["BillingService", "CheckoutController"],
      "recommendation": "Add pytest test cases covering discount < 0, discount == 0, and overflow values.",
      "confidence": 0.92
    }
  ]
}
```

---

## 3. Security Agent

### Investigative Question
> *"Did the change introduce a security weakness or vulnerability?"*

### Primary Responsibilities
- Analyzes diff and new logic for OWASP Top 10 vulnerabilities:
  - SQL injection (raw query concatenation, missing parameters)
  - Command injection (`subprocess`, `exec`, `os.system` with untrusted input)
  - Path traversal (`open`, `os.path.join` with user input)
  - Insecure deserialization / object injection
  - Broken authentication & authorization checks (missing role checks, bypassed guards)
  - Hard-coded secrets, tokens, or private keys
  - Insecure dependency additions or version downgrades

### Input Focus
- `diff.patch`
- `evidence.secrets_audit`
- `discovery.dependencies`
- `evidence.tainted_flows`

### Output Contract
```json
{
  "agent": "security",
  "findings": [
    {
      "finding_id": "SEC-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "SQL Injection vulnerability in patient search query",
      "description": "User input from query parameter 'filter' is formatted directly into a raw SQL query string without parameter binding.",
      "file": "routes/patients.py",
      "line_start": 112,
      "line_end": 115,
      "evidence": "query = f\"SELECT * FROM patients WHERE name LIKE '%{filter}%'\"",
      "affected_components": ["PatientRoutes", "DatabaseEngine"],
      "recommendation": "Use parameterized queries: cursor.execute(\"SELECT * FROM patients WHERE name LIKE ?\", (f'%{filter}%',))",
      "confidence": 0.99
    }
  ]
}
```

---

## 4. Requirements and API Agent

### Investigative Question
> *"Does the implementation still match requirements and external contracts?"*

### Primary Responsibilities
- Compares changed endpoints, request/response structures, and behavior against:
  - Markdown requirement specifications (e.g., `requirements/*.md`)
  - PDF specifications (parsed via `document_parser.py`)
  - OpenAPI/Swagger definitions (`openapi.json`, `swagger.yaml`)
  - Route decorators and API contracts
- Detects broken semantic contracts, changed status codes, missing mandatory fields, or altered requirement IDs (e.g., R001–R005).

### Input Focus
- `discovery.requirements` (parsed text, IDs, acceptance criteria)
- `discovery.apis` (OpenAPI paths, parameters, schemas)
- `diff.files`, `diff.patch`

### Output Contract
```json
{
  "agent": "contract",
  "findings": [
    {
      "finding_id": "REQ-001",
      "severity": "HIGH|MEDIUM|LOW|INFO",
      "title": "Breaking change in GET /api/v1/orders response schema violating R003",
      "description": "Field 'created_timestamp' renamed to 'created_at', breaking downstream client contract defined in R003.",
      "file": "routes/orders.py",
      "line_start": 45,
      "line_end": 50,
      "evidence": "return {'id': order.id, 'created_at': order.created}",
      "affected_components": ["OrderRoutes", "ClientSDK"],
      "recommendation": "Retain 'created_timestamp' or deprecate with backward compatibility alias.",
      "confidence": 0.96
    }
  ]
}
```

---

## 5. Database and Dependency Agent

### Investigative Question
> *"Are persistence and dependencies still consistent with the change?"*

### Primary Responsibilities
- Analyzes database models, ORM entities, SQL migrations, and schema files.
- Checks if model changes have corresponding forward and backward migrations.
- Detects non-backward-compatible column renames, drops, or NOT NULL additions without defaults.
- Evaluates newly added or updated package dependencies in `requirements.txt`, `package.json`, `pom.xml`, etc., for known vulnerability risks or license conflicts.

### Input Focus
- `discovery.migrations` (SQL, alembic, flyway, etc.)
- `discovery.models`
- `discovery.dependencies` (`requirements.txt`, `package.json`)
- `diff.patch`

### Output Contract
```json
{
  "agent": "database",
  "findings": [
    {
      "finding_id": "DB-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Unmigrated schema change: new NOT NULL column without default",
      "description": "Model 'User' added column 'phone_number' with nullable=False, but no migration file was provided.",
      "file": "models/user.py",
      "line_start": 28,
      "line_end": 30,
      "evidence": "phone_number = db.Column(db.String(20), nullable=False)",
      "affected_components": ["UserModel", "DatabaseSchema"],
      "recommendation": "Generate a migration adding 'phone_number' as nullable or provide a server-default value.",
      "confidence": 0.94
    }
  ]
}
```

---

## 6. Release Synthesizer

### Investigative Question
> *"Given all evidence and specialist findings, what is the verified release readiness gate status and blast radius?"*

### Primary Responsibilities
- Consumes findings from all 5 specialist agents.
- Performs deterministic cross-validation (verifies every file, line, and code snippet against the checked-out commit).
- Discards or flags unverified findings.
- Resolves conflicts between agents and aggregates affected workflows.
- Applies the deterministic **Release Gate Decision Matrix** (READY / ATTENTION / BLOCKED).
- Computes simulation impact graph and blast radius.

---

## Agent Invocation & Concurrency Model
1. The analysis worker prepares an `EvidencePack` dictionary.
2. An `asyncio.gather` pipeline sends the pack to all 5 specialist agents concurrently.
3. Network calls use `httpx.AsyncClient` with timeouts and retry exponential backoff.
4. If an agent fails to respond or returns invalid JSON, a fallback retry is executed with explicit JSON correction instructions.
5. All 5 completed reports are handed off to the Release Synthesizer.
