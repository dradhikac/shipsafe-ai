# ShipSafe AI — Product Specification

---

## Product

**ShipSafe AI**

## Tagline

**Agentic Release & Regression Guardian**

---

## Problem

A small software change can create hidden regressions across code, tests, requirements, APIs, security, and databases. Developers often perform this validation manually — checking test output, reviewing diffs, cross-referencing requirements documents, and inspecting migration history one step at a time. This process is slow, error-prone, and easy to skip under release pressure.

Manual validation frequently misses:

- Changed behavior that breaks an unrelated module through an import chain
- API response fields removed or renamed that violate a contract
- Database model changes committed without a corresponding migration
- User-controlled input passed directly into SQL queries
- Regression scenarios that existed in tests for old behavior but were not updated for new behavior

The result is releases that pass a quick check but fail in production, or require immediate hotfixes after deployment.

---

## Solution

ShipSafe AI is an agentic workflow that coordinates five independent analysis workstreams across a software change, synthesizes evidence-backed findings, supports controlled remediation, validates the result through actual test execution, and produces a final evidence-based release-readiness determination.

The developer does not need to know which workstream to run or in what order. ShipSafe orchestrates the investigation, synthesizes the findings, and presents a structured release report with concrete evidence for every finding.

---

## Primary User

A software developer preparing a change for release. Solo developer or small team. Does not require a separate QA team or release manager.

---

## Primary Input

A repository in a known state plus a current change or release candidate. The change is represented as a Git diff. Release requirements are provided as structured requirement definitions in the `requirements/` directory.

---

## Primary Output

An evidence-backed release-readiness report containing:

- Which files and modules are affected
- Which tests are missing or failing
- Which security risks are present with code evidence
- Which release requirements are satisfied or violated
- Whether required database migrations are present
- A final release status: `RELEASE READY`, `NEEDS ATTENTION`, or `RELEASE BLOCKED`

---

## Core Capabilities

### 1. Change Impact Analysis

Determines which files, modules, services, APIs, and tests are affected by the current change. Traces dependency chains within the repository. Does not invent affected components.

### 2. Test Gap Analysis

Compares changed behavior against existing tests. Identifies specific regression scenarios that are not covered. Maps gaps to release requirements.

### 3. Security Analysis

Inspects changed code for unsafe input handling, raw SQL construction with user-controlled data, hardcoded secrets, and missing authorization. Reports only findings traceable to specific code patterns in the changed files.

### 4. Contract / Requirements Analysis

Compares the implementation against the release requirement definitions. Identifies each requirement as Compliant, Non-Compliant, or Unverifiable. API contract checks inspect actual route handlers and response structures.

### 5. Database Migration Analysis

Identifies model and schema changes in the diff. Compares against the migration history. Reports schema changes that have no corresponding migration file.

### 6. Release Synthesis

Reads all five agent reports, deduplicates findings, preserves evidence, assigns severity, determines per-requirement compliance, and generates the master release report. Sets the initial release status.

### 7. Remediation

Fixes confirmed findings with the minimum required change. Adds regression tests for confirmed bug fixes. Creates required migration files. Applies security fixes to the specific code patterns identified in the security report.

### 8. Validation

Executes the test suite and measures actual coverage. Verifies that remediated scenarios now pass. Regenerates affected agent reports. Updates the release report.

### 9. Traceability

Every finding references the requirement it relates to. Every remediation references the originating finding. Every regression test references the requirement it covers. The complete chain from requirement to code to test is documented.

### 10. Release Simulation

The demo scenario provides a controlled simulation of a release that introduces known problems (R001–R005). ShipSafe detects, reports, remediates, validates, and issues a final release determination. The before/after comparison demonstrates the measurable value of the workflow.

---

## Outcomes

- Reduce manual investigation effort before release
- Reduce missed regressions that reach production
- Reduce rework caused by missed requirements
- Improve traceability between requirements, code, and tests
- Shorten release-validation cycles for solo developers and small teams

---

## Non-Goals

ShipSafe AI is intentionally scoped. The following are not goals of this project:

- Replacing a complete CI/CD platform
- Production monitoring or alerting
- Full cloud infrastructure deployment
- Multi-user SaaS product
- GitHub OAuth or external identity providers
- Enterprise authentication and authorization
- Kubernetes, container orchestration, or service meshes
- Redis, message queues, or distributed caching
- Complex frontend frameworks (React, Vue, Angular)
- Generic conversational chatbot unrelated to release analysis
- Automated deployment to production

---

## Technical Constraints

| Constraint | Detail |
|---|---|
| Application language | Python |
| Application framework | Flask |
| Database | SQLite |
| Test framework | pytest |
| Dashboard templating | Jinja |
| Dashboard frontend | Vanilla JavaScript, local CSS |
| Architecture style | Compact, solo-developer friendly |
| External services | None required for core prototype |
| Frontend framework | None — no React, no Vue |
| Infrastructure | Local only for prototype |

---

## IBM Bob Role

IBM Bob 2.0 is the central orchestration environment for the ShipSafe AI development workflow and agentic analysis. Bob is not a decorative add-on. It:

- Executes the five analysis workstreams as focused, independent tasks
- Enforces the project rules defined in `.bob/rules/shipsafe-rules.md`
- Uses the `shipsafe-release` skill to guide the six-phase release workflow
- Reads `AGENTS.md` as the authoritative project contract for every task
- Provides the agentic coordination layer that makes ShipSafe a genuinely agentic system rather than a collection of scripts

Without Bob's orchestration, ShipSafe is a set of analysis tools. With Bob as the orchestrator, it becomes an agentic release guardian that can reason about evidence, coordinate workstreams, and enforce rules across the development process.

---

## Success Criteria

The prototype must demonstrate all six of the following:

1. **Multiple independent analysis workstreams** — at least five distinct agents investigating the change in parallel, each producing an isolated report.

2. **Evidence-backed findings** — every finding in the release report traces to a specific file, function, requirement, or test with observable evidence. No invented findings.

3. **Requirement-to-code traceability** — each of R001–R005 is explicitly evaluated against the implementation and marked Compliant, Non-Compliant, or Unverifiable.

4. **Remediation** — confirmed findings are addressed with targeted code changes and regression tests, not general rewrites.

5. **Actual test execution** — the test suite is run and its real output (pass/fail counts, coverage percentage) is recorded and displayed.

6. **Before/after measurement** — the release report shows quantitative before/after comparison of test results, coverage, and finding counts based on actual tool output.

7. **Final release-status determination** — the system issues a final `RELEASE READY`, `NEEDS ATTENTION`, or `RELEASE BLOCKED` verdict supported by the evidence in the report.
