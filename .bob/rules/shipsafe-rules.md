# ShipSafe AI — Persistent Bob Rules

These rules are active for every Bob task in the ShipSafe AI repository. They enforce the integrity of the agentic analysis workflow and prevent common failure modes such as invented findings, premature release decisions, and uncontrolled source edits.

---

## Rule 1 — Evidence Before Conclusion

A finding must not be reported as confirmed unless it is supported by concrete repository evidence. Acceptable evidence includes:

- A specific file path and line number
- A function or class name in changed code
- A test name and its actual failure output
- A requirement ID with a traceable gap in the implementation
- Actual command output (test runner, coverage tool, linter, migration tool)
- Database schema or migration file content

An LLM opinion, a plausible inference, or a general pattern is not evidence. It must be clearly marked as "unconfirmed" if it cannot be traced to the repository.

---

## Rule 2 — No Invented Numbers

Do not report any numeric metric that was not measured from actual tool execution. This includes:

- Test pass/fail counts
- Code coverage percentages
- Number of affected files
- Number of migrations present or missing
- Risk scores

If a metric cannot be measured in the current task, state that it was not measured. Do not estimate or extrapolate.

---

## Rule 3 — No Invented Test Results

Do not describe a test as passing or failing unless the test suite was executed and its output was observed. Do not assume tests pass because code looks correct. Do not describe test coverage without running a coverage tool.

---

## Rule 4 — No Invented Security Findings

Do not report a security vulnerability unless it was found by reading actual code in the repository. Every security finding must cite the file, the function, and the specific code pattern that constitutes the risk. Do not generate generic security checklists and present them as confirmed findings.

---

## Rule 5 — No Invented Affected Components

Do not list files, modules, services, or APIs as affected by a change unless they were identified by reading the repository. Impact must be derived from actual imports, call chains, route registrations, or schema references visible in the code.

---

## Rule 6 — No Source Edits During Analysis Workstreams

During the analysis phase (Phase 1 — Discover through Phase 2 — Parallel Analysis), no agent and no Bob task may modify application source code. Analysis is strictly read-only. The five analysis agents must produce reports only; they must not write application code, test code, migration files, or configuration files.

---

## Rule 7 — Analysis Reports Remain Isolated

Each analysis agent owns exactly one report file:

| Agent | Report |
|---|---|
| Impact Analyst | `reports/agents/impact_report.json` |
| Test Gap Analyst | `reports/agents/test_gap_report.json` |
| Security Analyst | `reports/agents/security_report.json` |
| Contract & Documentation Analyst | `reports/agents/contract_report.json` |
| Database Analyst | `reports/agents/database_report.json` |

An agent must not write to another agent's report. An agent must not write to `reports/latest_release_report.json`. That file is the exclusive output of the Release Synthesizer.

---

## Rule 8 — Remediation Only After Synthesis

No remediation task may begin until the Release Synthesizer has produced `reports/latest_release_report.json` containing confirmed findings. Remediation must be based on the synthesized report, not on individual agent reports or on speculation.

---

## Rule 9 — Every Remediation Must Be Validated

After each remediation action, a validation step must follow. Validation means:

- The relevant tests are executed and their output is observed.
- Coverage is measured where applicable.
- The specific finding that triggered the remediation is re-checked.
- The agent report for the affected workstream is regenerated.

A remediation is not complete until its validation step has passed.

---

## Rule 10 — Confirmed Bug Fixes Must Have Regression Tests

When a confirmed bug is fixed, a regression test covering that specific behavior must be added or updated before the fix is considered complete. This applies wherever a test can be written for the affected behavior. The test must reference the originating requirement where one exists.

---

## Rule 11 — Small, Controlled Edits

When making changes to the codebase:

- Change only the files directly required by the current task.
- Make the minimum change that satisfies the requirement.
- Do not refactor, reformat, or reorganize unrelated code.
- Do not rename or move files not required by the task.
- Do not add features beyond what was requested.

---

## Rule 12 — No Unrelated Refactoring

Bob must not clean up, reorganize, or improve code that is not directly related to the confirmed finding or the current task. If a refactoring opportunity is noticed, it may be noted in a comment or report but must not be applied without explicit instruction.

---

## Rule 13 — Real Repository State Is Authoritative

The actual state of the repository — its files, their contents, test results, and migration history — is the single source of truth. Bob must not substitute prior assumptions, prior task results, or general knowledge about similar codebases when the actual repository state can be inspected.

At the start of each new task, read the relevant files and current test output rather than relying on memory from a previous session.

---

## Rule 14 — Requirements and Implementation Must Be Traceable

Every release requirement (R001, R002, R003, R004, R005 and any future requirements) must be traceable to:

- The code that implements it (or fails to implement it)
- The tests that verify it (or the gap where tests are missing)
- The finding in the agent reports that references it

Remediation tasks must reference the requirement ID they address. Final release reports must state the compliance status of each requirement explicitly.

---

## Rule 15 — Final Release Status Must Be Based on Actual Validation

The release status field in `reports/latest_release_report.json` must only take the value `RELEASE READY` when:

- All confirmed findings have been remediated.
- All regression tests for confirmed fixes are present and passing.
- Validation has been executed and its output has been observed.
- No critical or high-severity unresolved findings remain.

A release status of `RELEASE BLOCKED` or `NEEDS ATTENTION` must be preserved until the above conditions are met. Do not upgrade release status on the basis of a plan to fix issues.

---

## Five-Agent Model

ShipSafe AI uses five independent analysis agents, each with a narrow, isolated mission:

### Agent 1 — Impact Analyst

**Mission:** Determine which files, modules, services, APIs, and tests are affected by the current change.

**Output:** `reports/agents/impact_report.json`

**Evidence required:** Actual changed files from Git diff, import/call graph tracing within the repository.

---

### Agent 2 — Test Gap Analyst

**Mission:** Compare changed behavior against existing tests and identify missing regression scenarios.

**Output:** `reports/agents/test_gap_report.json`

**Evidence required:** Existing test files, test names, changed functions/routes, coverage data where available.

---

### Agent 3 — Security Analyst

**Mission:** Inspect changed code for security risks, especially unsafe input handling, SQL construction, secrets exposure, and authorization gaps.

**Output:** `reports/agents/security_report.json`

**Evidence required:** Specific code patterns in changed files, with file path, function, and line reference.

---

### Agent 4 — Contract & Documentation Analyst

**Mission:** Compare the implementation against release requirements and API contract expectations.

**Output:** `reports/agents/contract_report.json`

**Evidence required:** Requirement definitions (R001–R005), API response structures in actual code, route handler implementations.

---

### Agent 5 — Database Analyst

**Mission:** Determine whether model or schema changes require migrations, whether migrations are present, and whether they are consistent with the current schema.

**Output:** `reports/agents/database_report.json`

**Evidence required:** Model definitions, schema files, migration directory contents, migration version history.

---

## Release Synthesizer Role

The Release Synthesizer is not an analysis agent. It reads the five agent reports after the parallel analysis phase is complete and performs the following:

1. Reads all five agent reports from `reports/agents/`.
2. Deduplicates findings that appear across multiple reports.
3. Preserves all evidence references.
4. Assigns evidence-backed severity levels (Critical / High / Medium / Low / Info).
5. Determines compliance status for each release requirement.
6. Generates `reports/latest_release_report.json`.
7. Sets the initial release status (`RELEASE READY`, `NEEDS ATTENTION`, or `RELEASE BLOCKED`).

The Release Synthesizer must never treat an LLM opinion as proof. Every entry in the synthesized report must trace to evidence in one or more agent reports.
