# ShipSafe AI — 3-Minute Hackathon Demonstration Script

**System:** ShipSafe AI (Agentic Release & Regression Guardian)  
**Target Application:** CareHub Appointment Service  
**Total Duration:** Exactly 3 Minutes (180 Seconds)  

---

## Demonstration Timeline & Narrative

### 0:00 – 0:20 | The Problem: Hidden Regressions in Fast-Moving Releases

> *"In modern software releases, small pull requests routinely introduce subtle, cross-cutting bugs that pass CI tests. A developer might change an API response, introduce an unparameterized SQL query, or silently delete failing regression tests to make the build turn green. Because traditional code review is fragmented across security, database, and API boundaries, release blockers slip through undetected."*

- **Visual / Action:**
  - Show the candidate release diff (`scripts/apply_demo_release.py`) where 7 tests were deleted, SQL concatenation was introduced, and `eta_minutes` was dropped.

---

### 0:20 – 0:45 | Introducing ShipSafe AI

> *"ShipSafe AI is an Agentic Release & Regression Guardian. Instead of relying on manual checklists or single-model guesswork, ShipSafe orchestrates independent, specialized analysis workstreams that investigate code impact, test gaps, security, API contracts, and database migrations before any code is deployed."*

- **Visual / Action:**
  - Open the ShipSafe Guardian Dashboard at `http://127.0.0.1:5000`.
  - Highlight the core DevSecOps interface and navigation header.

---

### 0:45 – 1:15 | Five Specialized IBM Bob 2.0 Analysis Agents

> *"Here in the dashboard, we see the five specialized analysis agents orchestrated by IBM Bob 2.0. Each agent operated independently and in read-only mode during investigation:*
> 1. *Impact Analyst detected 8 modified symbols across call paths.*
> 2. *Test Gap Analyst uncovered 7 deleted regression tests.*
> 3. *Security Analyst flagged a critical CWE-89 SQL injection vulnerability.*
> 4. *Contract Analyst discovered API response contract drift.*
> 5. *Database Analyst identified unmigrated SQLite table constraints.*
> *All five original reports are preserved as immutable evidence under `reports/agents/`."*

- **Visual / Action:**
  - Scroll to the **"IBM Bob 2.0 Analysis Agents"** section on the dashboard.
  - Click on the agent cards to display the concrete evidence paths and findings counts.

---

### 1:15 – 1:40 | Deterministic Synthesis: 22 Findings & 5 Failed Requirements

> *"Next, the ShipSafe Release Synthesizer ingests the agent reports, normalizes evidence, deduplicates overlapping issues, and evaluates requirement compliance. In the bad release candidate, ShipSafe synthesized 22 total findings—including 1 Critical and 19 High severity defects—and determined that all 5 release requirements failed. The release status was immediately derived as RELEASE BLOCKED."*

- **Visual / Action:**
  - Show the **Executive Status Banner** showing `RELEASE BLOCKED`.
  - Show the **Requirement Traceability Matrix** where R001 through R005 show `FAIL`.
  - Show the **Release Impact Simulation** displaying the 5 concrete regression paths (`REG-PATH-001` through `REG-PATH-005`).

---

### 1:40 – 1:55 | Surfacing the R003 Architectural Conflict

> *"ShipSafe doesn't sweep architectural disagreements under the rug. In requirement R003, the Database Analyst recommended creating an unapproved migration `002_add_priority_critical.sql` to support a new 'critical' priority, while the Contract and Impact Analysts correctly identified that 'critical' violates the business specification. ShipSafe flagged this as an explicit AGENT RECOMMENDATION CONFLICT and resolved it under requirement authority: reject the unauthorized value rather than formalizing it."*

- **Visual / Action:**
  - Highlight the amber **R003 CONFLICTED** alert card in the Traceability section showing the conflicting agent evidence side-by-side.

---

### 1:55 – 2:20 | Prioritized Remediation Plan

> *"ShipSafe then generated an evidence-backed remediation plan ordered strictly by severity:
> - P1: Parameterize the unsafe search SQL query.
> - P2: Restore the cancelled appointment reminder guard.
> - P3: Re-introduce the `eta_minutes` field in API responses.
> - P4: Harmonize the schema and models back to the allowed priorities.
> - P5: Restore all 7 deleted regression tests.
> Each item includes exact files, reproduction commands, and rollback safety guidance."*

- **Visual / Action:**
  - Scroll to the **Prioritized Remediation Plan** table (items REM-R004 through REM-R005).

---

### 2:20 – 2:40 | Post-Remediation Verification: 42 Tests & 98% Coverage

> *"We executed the remediation plan and validated every fix with real tests. In our release measurement panel, we see the complete 3-way progression:
> - Baseline: 38 tests, 98% coverage, 0 findings.
> - Bad Release: 31 tests, 96% coverage, 22 findings.
> - Post-Remediation: 42 tests, 98% statement coverage, and 0 active findings.
> All 7 deleted tests plus a new SQL injection defense test were executed and passed."*

- **Visual / Action:**
  - Show the **Release Measurement** comparison cards side-by-side: `BASELINE (38 / 98%)` → `BAD RELEASE (31 / 96%)` → `POST-REMEDIATION (42 / 98%)`.
  - Point out that statement coverage was restored to 98% with 478 statements executed.

---

### 2:40 – 3:00 | Verifying RELEASE READY

> *"With all 42 application tests and all 172 workspace tests passing, zero critical or high findings remaining, all 5 requirements marked VALIDATED, and zero active regression paths, ShipSafe AI automatically updates the release determination to RELEASE READY. ShipSafe provides verifiable proof that your release is safe to ship."*

- **Visual / Action:**
  - Refresh the dashboard to show the bright green **RELEASE READY** status badge, 5/5 requirements compliant, and zero active regression risks.
