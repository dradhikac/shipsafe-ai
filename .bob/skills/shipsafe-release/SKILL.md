---
name: shipsafe-release
description: >
  Reusable ShipSafe release-analysis workflow. Activates the full six-phase
  agentic release-readiness process: Discover → Parallel Analysis → Synthesis
  → Remediation → Validation → Final Release Decision. Use when the user wants
  to run, resume, or understand the ShipSafe release workflow for a change.
---

# ShipSafe Release Analysis Skill

This skill defines the canonical six-phase workflow for ShipSafe AI release analysis. Every phase must be completed in sequence. Phases must not be skipped or merged. Evidence gathered in earlier phases drives decisions in later phases.

**Fundamental rule:** This skill must never treat an LLM opinion as proof. Every finding, metric, compliance status, and release determination must trace to observable evidence from the repository or from executed tools.

---

## PHASE 1 — Discover

**Goal:** Establish the scope of the current release before any analysis begins.

### Steps

1. **Inspect repository state**
   - Read `AGENTS.md` and `.bob/rules/shipsafe-rules.md` to load the project contract.
   - Read `docs/ARCHITECTURE.md` and `docs/PRODUCT_SPEC.md` for system context.
   - Do not re-derive architecture from scratch; use the project documentation.

2. **Inspect Git changes**
   - Obtain the current Git diff (staged, unstaged, or between commits as appropriate).
   - List all changed files and classify each as: source, test, migration, configuration, or documentation.
   - Do not infer changed files; read them directly from Git output.

3. **Establish release scope**
   - Identify the entry points affected by the change (routes, service functions, models, schemas).
   - Note which modules import or depend on changed files.
   - Record the scope as a structured list of affected files with their change classification.

4. **Load release requirements**
   - Read the requirements directory for the active requirement set.
   - Map each requirement (R001, R002, …) to its description and acceptance criteria.
   - Note which requirements are potentially affected by the change scope identified in step 3.

**Phase 1 output:** A documented release scope and a requirement map. No findings are reported yet.

---

## PHASE 2 — Parallel Analysis

**Goal:** Five independent agents investigate the change from their assigned perspective and each writes its isolated report.

The five workstreams may be executed in any order or in parallel. Each workstream is strictly read-only with respect to application source code.

---

### Workstream 2.1 — Impact Analyst

**Mission:** Determine which files, modules, services, APIs, and tests are affected by the change.

**Process:**
1. Read each changed source file from the Git diff.
2. Trace imports and call dependencies within the repository.
3. Identify which API routes, service functions, and database models are touched.
4. Identify which existing tests exercise the affected code.
5. Note any affected files that have no corresponding tests.

**Evidence required for each affected item:** File path, the specific changed symbol or route, the dependency chain that connects it to the change.

**Output:** `reports/agents/impact_report.json`

**Must not:** Edit any source file. Must not write to any other report file.

---

### Workstream 2.2 — Test Gap Analyst

**Mission:** Compare changed behavior against existing tests and identify missing regression scenarios.

**Process:**
1. Read the test files identified by the Impact Analyst scope (or independently discover them).
2. For each changed function or route, list the test cases that cover it.
3. Identify behaviors introduced or changed that are not covered by any existing test.
4. Identify requirements (R001–R005) whose acceptance criteria are not verified by any test.
5. List specific missing test scenario descriptions with the requirement ID they should cover.

**Evidence required for each gap:** Changed function/route name, what behavior is missing, which requirement it relates to, which test file should contain the coverage.

**Output:** `reports/agents/test_gap_report.json`

**Must not:** Write or modify test files during this phase. Must not write to any other report file.

---

### Workstream 2.3 — Security Analyst

**Mission:** Inspect changed code for security risks, especially unsafe input handling, SQL construction, secrets exposure, and authorization gaps.

**Process:**
1. Read each changed source file.
2. Inspect database query construction for raw string interpolation or concatenation with user input.
3. Inspect input validation and sanitization for user-controlled parameters.
4. Inspect for hardcoded secrets, credentials, or tokens.
5. Inspect for missing authorization checks on sensitive routes.
6. Record only findings that are traceable to specific code patterns in the changed files.

**Evidence required for each finding:** File path, function name, line reference, the specific code pattern that constitutes the risk, and the class of vulnerability (e.g., SQL injection, missing auth).

**Output:** `reports/agents/security_report.json`

**Must not:** Patch any code. Must not generate a generic checklist and present it as findings. Must not write to any other report file.

---

### Workstream 2.4 — Contract & Documentation Analyst

**Mission:** Compare the implementation against release requirements and API contract expectations.

**Process:**
1. Read each release requirement (R001–R005) from the requirements directory.
2. For each requirement, locate the relevant code in the changed files.
3. Determine whether the implementation satisfies the acceptance criteria.
4. For API requirements, read the actual route handler and verify the response structure matches the contract.
5. Record any gap between the requirement and the implementation as a finding with the requirement ID.

**Evidence required for each finding:** Requirement ID and text, the route handler or function being evaluated, the specific implementation gap (e.g., field missing from response, condition not checked).

**Output:** `reports/agents/contract_report.json`

**Must not:** Edit routes, models, or documentation. Must not write to any other report file.

---

### Workstream 2.5 — Database Analyst

**Mission:** Determine whether model or schema changes require migrations, whether migrations are present, and whether they are consistent with the current schema.

**Process:**
1. Read all changed model or schema files from the Git diff.
2. List all new columns, tables, relationships, or index changes introduced.
3. Inspect the migrations directory and list existing migration files with their version identifiers.
4. For each schema change, determine whether a corresponding migration exists and whether it is correct.
5. Identify schema changes with no corresponding migration.

**Evidence required for each finding:** Model file and the specific field or table change, the migration directory listing, the specific migration that is missing or incorrect.

**Output:** `reports/agents/database_report.json`

**Must not:** Create or modify migration files. Must not write to any other report file.

---

## PHASE 3 — Synthesis

**Goal:** Produce a single, deduplicated, evidence-backed release report from the five agent reports.

### Steps

1. **Read all five agent reports** from `reports/agents/`.

2. **Deduplicate findings** — if the same gap or risk is reported by multiple agents, consolidate into one finding and preserve all evidence references.

3. **Preserve all evidence** — every finding in the synthesized report must retain the file path, function, requirement ID, and other evidence provided by the originating agent report.

4. **Assign evidence-backed severity** — assign severity (Critical / High / Medium / Low / Info) based only on the evidence present. Do not escalate severity beyond what the evidence supports.
   - Critical: directly exploitable security vulnerability or data loss risk with code evidence
   - High: confirmed requirement gap or missing migration with clear evidence
   - Medium: test gap or contract inconsistency with evidence
   - Low: documentation gap or minor deviation
   - Info: observation with no confirmed impact

5. **Determine requirement compliance** — for each requirement (R001–R005), state whether the implementation is Compliant, Non-Compliant, or Unverifiable, with a reference to the supporting finding.

6. **Generate `reports/latest_release_report.json`** — the report must include:
   - `release_scope`: list of changed files
   - `findings`: deduplicated, evidence-backed finding list
   - `requirement_compliance`: per-requirement status
   - `release_status`: one of `RELEASE READY`, `NEEDS ATTENTION`, `RELEASE BLOCKED`
   - `synthesis_timestamp`: when the report was generated
   - `evidence_summary`: references to the source agent reports

7. **Set initial release status:**
   - `RELEASE BLOCKED` if any Critical or High finding is present.
   - `NEEDS ATTENTION` if any Medium finding is present and no Critical/High findings remain.
   - `RELEASE READY` only if no Critical, High, or Medium findings are present and all requirements are Compliant.

**The synthesizer must never treat an LLM opinion as proof.** Every entry must trace to evidence in the agent reports.

---

## PHASE 4 — Remediation

**Goal:** Fix confirmed findings from the synthesized report, one at a time, with supporting tests.

### Sequence

For each confirmed finding in `reports/latest_release_report.json` (highest severity first):

1. **Read the finding** — note the requirement ID, evidence, and file references.
2. **Make the minimum change** — edit only the files required to address the confirmed finding. Do not refactor unrelated code.
3. **Add or update a regression test** — write a test that verifies the specific behavior that was broken. The test must reference the requirement ID in a comment or docstring.
4. **Do not move to the next finding** until the current one is validated (see Phase 5).

### Remediation constraints

- Fix only confirmed findings. Do not fix findings marked as unconfirmed or informational during remediation.
- Do not introduce new dependencies without explicit approval.
- Do not change API contracts beyond what is required to satisfy a confirmed finding.
- Security fixes (SQL injection, missing auth) must address the specific code pattern identified in the security report, not a generalized rewrite.
- Migration files must follow the project's existing versioning convention.

---

## PHASE 5 — Validation

**Goal:** Verify that each remediation actually resolves the finding it addressed, using real execution.

### Steps

1. **Execute the test suite** — run `pytest` (or the project's configured test command) and record the full output.
2. **Measure coverage** — run coverage tooling and record the actual percentage and uncovered lines.
3. **Verify changed behavior** — confirm that the specific scenario from the finding is now covered and passing.
4. **Regenerate affected agent reports** — re-run the relevant analysis workstream(s) for the remediated findings and update the agent reports.
5. **Update `reports/latest_release_report.json`** — mark remediated findings as resolved with a reference to the test that now covers them.

### Validation constraints

- Do not mark a finding as resolved without executing the test that covers it.
- Do not report coverage without running the coverage tool.
- If a regression test fails, the remediation is not complete — return to Phase 4.

---

## PHASE 6 — Final Release Decision

**Goal:** Determine the final release status from actual validation results and produce the final release report.

### Steps

1. **Compare before/after metrics** — record test pass counts, coverage percentages, and finding counts before and after remediation. These numbers must come from actual tool execution in Phase 5.

2. **Verify remaining findings** — review `reports/latest_release_report.json` for any unresolved findings. Each must be explicitly accounted for (resolved, deferred with justification, or still open).

3. **Check requirement compliance** — verify that each requirement (R001–R005) is now marked Compliant with evidence.

4. **Determine final release status:**
   - `RELEASE READY` — all Critical/High/Medium findings resolved, all requirements Compliant, regression tests present and passing, validation executed.
   - `NEEDS ATTENTION` — remaining Low/Info findings with no blocking issues; release may proceed with awareness.
   - `RELEASE BLOCKED` — any unresolved Critical or High finding remains; release must not proceed.

5. **Generate the final release report** — update `reports/latest_release_report.json` with:
   - Final `release_status`
   - `before_metrics` and `after_metrics` (from actual tool output)
   - `resolved_findings` list with evidence
   - `unresolved_findings` list with status
   - `requirement_compliance` final state
   - `validation_timestamp`

### Final decision constraints

- Do not set `release_status` to `RELEASE READY` based on a plan or intention to fix. Only set it after validation has been executed and observed.
- Do not suppress unresolved findings from the final report. If a finding is being deferred, record it as deferred with an explicit justification.
- The final release report is the authoritative output of the ShipSafe workflow and must be reproducible from the evidence it contains.
