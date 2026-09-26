# ShipSafe AI — Release Synthesis Documentation

**System:** ShipSafe AI (Agentic Release & Regression Guardian)  
**Component:** Deterministic Release Synthesizer (`shipsafe/analyzer/synthesizer.py`)  
**Specification Reference:** Phase 2 Synthesis Architecture  
**Date:** 2026-09-26  

---

## 1. Executive Summary & Attribution

ShipSafe AI couples specialized multi-agent AI analysis with deterministic local synthesis and evidence-backed governance.

### Clear System Attribution:
- **IBM Bob 2.0:** Orchestrated the five specialized analysis subagents during the development and analysis phase:
  1. *Impact Analyst* (`reports/agents/impact_report.json`)
  2. *Test Gap Analyst* (`reports/agents/test_gap_report.json`)
  3. *Security Analyst* (`reports/agents/security_report.json`)
  4. *Contract & Documentation Analyst* (`reports/agents/contract_report.json`)
  5. *Database Analyst* (`reports/agents/database_report.json`)
  These five reports capture findings across code blast radius, missing tests, SQL injection risks, API contract breaches, and database schema drift.
- **Local ShipSafe Engine:** Implements the deterministic release synthesizer in `shipsafe/analyzer/synthesizer.py`. It ingests, validates, normalizes, and groups the Bob analysis artifacts, detects recommendation conflicts, computes requirement compliance, derives the release status, and publishes `reports/latest_release_report.json`.

ShipSafe does **not** claim to have performed the agentic analysis workstreams executed by IBM Bob 2.0. Rather, ShipSafe provides the authoritative, deterministic layer that turns those distributed agent findings into an executable release-readiness determination.

---

## 2. Why the Five Bob Reports Are Immutable Historical Evidence

The five reports in `reports/agents/` are treated as **strictly read-only artifacts**:

1. **Audit Trail Integrity:** In regulated or critical release environments, analysis outputs must remain immutable records of what individual agents observed at inspection time.
2. **Preventing Agent Cascading Bias:** If one agent could overwrite or tamper with another agent's report, cross-validation would be compromised.
3. **Reproducibility:** A release audit must always be able to trace a synthesized decision back to the exact JSON file produced by each agent.
4. **No In-Place Mutation:** The synthesizer loads reports using read-only operations and performs all schema transformations and normalizations in-memory before assembling the final synthesized report.

---

## 3. Normalization Layer Architecture

The Phase 1 audit revealed that while all five reports conform to the general conceptual model, slight structural variations existed:

1. **Object-Form vs. List-Form Evidence:**
   - `contract_report.json` provided evidence as nested dictionaries (`{"file": ..., "symbol": ..., "lines": ...}` or multi-file keys `file_1`, `file_2`).
   - The synthesizer extracts these keys, parses line ranges (e.g. `"25-29"` into `line_start=25, line_end=29`), identifies symbols and missing tests, and maps them into the standard list of concrete `evidence_item` objects.
2. **Remediation vs. Recommended Action:**
   - `security_report.json` utilized `remediation` instead of `recommended_action`, and `start_line`/`end_line` instead of `line_start`/`line_end`.
   - The normalization adapter standardizes these fields into `recommended_action` and `line_start`/`line_end` without losing information.
3. **Authoritative Findings Array:**
   - In `impact_report.json`, the summary header listed `total_findings: 7`, but the actual findings array contained 8 items (`IMPACT-001` through `IMPACT-008`).
   - The synthesizer treats the `findings` array as authoritative and derives all summary counts directly from the normalized findings (totaling 22 findings across the 5 agents).
4. **Normalization Notes:**
   - Any adaptation performed during ingestion is recorded in the top-level `normalization_notes` array in `reports/latest_release_report.json`.

---

## 4. Handling Duplicates & Cross-Agent Confirmation

Rather than deduplicating findings by discarding records, ShipSafe recognizes that multiple agents reporting the same defect represents **valuable cross-stream confirmation**:

- **Underlying Findings Preserved:** All 22 original Bob findings remain in the `findings` array with their original IDs (`IMPACT-xxx`, `TESTGAP-xxx`, `SECURITY-xxx`, `CONTRACT-xxx`, `DATABASE-xxx`).
- **Consolidated Findings (`SYN-R001` through `SYN-R005`):**
  - When findings relate to the same requirement, the synthesizer groups them into consolidated findings.
  - Each consolidated finding specifies:
    - `finding_id`: e.g. `SYN-R001`
    - `requirement_id`: e.g. `R001`
    - `source_agents`: list of all agents confirming the issue (e.g. `["contract", "impact", "test_gap"]`)
    - `supporting_findings`: list of underlying Bob finding IDs
    - `severity`: maximum severity among supporting findings (e.g., `CRITICAL` for `SYN-R004`)
    - `affected_files`: union of affected paths
    - `evidence`: unified, traceable evidence list

---

## 5. R003 Agent Recommendation Conflict Handling

Requirement R003 specifies:
> *"The field must accept values: `normal`, `high`, `emergency`. A versioned migration file must exist in the `migrations/` directory that introduces the `priority` column."*

During analysis, two agents reached differing remediation recommendations:
- **Database Analyst (`DATABASE-001`):** Saw that SQLite schema had diverged from migrations and recommended adding migration `migrations/002_add_priority_critical.sql` to support `'critical'` in the database.
- **Contract Analyst (`CONTRACT-R003`) & Impact Analyst (`IMPACT-003`):** Identified that `'critical'` is not an approved value in R003 and recommended removing `'critical'` from `db.py` and `models.py`.

### Synthesizer Resolution:
The synthesizer **does not edit code** or prematurely pick a remediation strategy. Instead, it records this nuance as an explicit conflict in `conflicts`:
```json
{
  "requirement_id": "R003",
  "type": "AGENT_RECOMMENDATION_CONFLICT",
  "agents": ["contract", "database", "impact"],
  "description": "Agent recommendation conflict on R003 priority definition...",
  "evidence": [...]
}
```
Compliance status is evaluated directly against the acceptance criteria of R003, leading to `status: FAIL`. The actual architectural remediation choice is deferred to the dedicated Remediation phase.

---

## 6. Deterministic Requirement Compliance Calculation

Requirement compliance for R001–R005 is computed strictly from concrete evidence:

| Requirement | Evaluated Status | Contributing Agents | Consolidated Severity | Key Evidence |
|---|---|---|---|---|
| **R001** | `FAIL` | `contract`, `impact`, `test_gap` | `HIGH` | Guard in `send_reminder()` lines 25-29 removed; tests deleted from `test_notifications.py`. |
| **R002** | `FAIL` | `contract`, `impact`, `test_gap` | `HIGH` | `eta_minutes` missing from `appointment_row_to_dict()` in `models.py`; response tests deleted. |
| **R003** | `FAIL` | `contract`, `database`, `impact`, `test_gap` | `HIGH` | Unapproved `'critical'` priority added to `models.py` and `db.py` without compliant migration; tests deleted. |
| **R004** | `FAIL` | `contract`, `impact`, `security`, `test_gap` | `CRITICAL` | SQL injection in `/appointments/search` (lines 74–77); 0 tests in test suite. |
| **R005** | `FAIL` | `contract`, `impact`, `test_gap` | `HIGH` | Systematic removal of 7 regression tests covering R001, R002, R003. |

### Evaluation Rules:
- If any confirmed finding has `CRITICAL` or `HIGH` severity: status = `FAIL`.
- If findings have `MEDIUM` or `LOW` severity only: status = `WARNING`.
- If no violation findings exist and evidence demonstrates compliance: status = `PASS`.
- If evidence is absent: status = `UNVERIFIABLE`.

---

## 7. Derivation of Release Status

The final release status is derived strictly from executable findings and compliance:

```text
Are there CONFIRMED CRITICAL or HIGH findings, or does any requirement FAIL?
├── YES ──> RELEASE_BLOCKED
└── NO  ──> Are there MEDIUM or LOW findings, or WARNING requirements?
            ├── YES ──> NEEDS_ATTENTION
            └── NO  ──> Have all requirements PASSED?
                        ├── YES ──> RELEASE_READY
                        └── NO  ──> ANALYSIS_ONLY
```

With **1 CRITICAL** finding, **19 HIGH** findings, and **5/5 requirements FAILING**, the synthesizer deterministically and correctly concludes:
**`status: RELEASE_BLOCKED`**.

---

## 8. Report Structure & Artifacts

The synthesizer outputs the consolidated report to:
`reports/latest_release_report.json`

The document adheres to the following top-level schema:
```json
{
  "report_type": "release_synthesis",
  "generated_at": "<ISO-8601 UTC>",
  "status": "RELEASE_BLOCKED",
  "summary": {
    "total_findings": 22,
    "critical_count": 1,
    "high_count": 19,
    "medium_count": 2,
    "low_count": 0,
    "info_count": 0,
    "requirements_compliant": 0,
    "requirements_non_compliant": 5,
    "requirements_unverifiable": 0
  },
  "repository": { ... },
  "git": { ... },
  "requirements": [ ... ],
  "requirement_compliance": [ ... ],
  "agent_reports": [ ... ],
  "findings": [ ... ],
  "consolidated_findings": [ ... ],
  "conflicts": [ ... ],
  "metrics": { ... },
  "normalization_notes": [ ... ]
}
```
