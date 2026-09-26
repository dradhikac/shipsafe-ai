# ShipSafe AI — Deterministic Analysis Engine

This document describes the deterministic analysis engine built in `shipsafe/analyzer/`.

The engine provides the real-data infrastructure that the future five Bob analysis agents will use to make evidence-backed findings.

---

## What the Engine Does

The deterministic engine collects real, measurable information about the current state of a repository and a software change. It does not make judgements, invent findings, or call an AI API. Its job is to gather verifiable facts and structure them for downstream use.

Specifically, the engine:

1. Locates the Git repository root.
2. Reads the current branch, HEAD commit, and Git status.
3. Counts changed files, lines added, and lines deleted (from the actual diff).
4. Loads the release requirements from the canonical Markdown source.
5. Runs the test suite using a subprocess call to `pytest`.
6. Parses actual test output for pass/fail counts, duration, and coverage.
7. Assembles all findings into a structured JSON report.
8. Saves the report to `reports/latest_release_report.json`.

---

## Modules

### `shipsafe/analyzer/git_analyzer.py`

Reads the real Git repository state using the `git` executable via subprocess.

- **`analyze(start=None)`** — Full analysis entry point. Returns a `GitState` dataclass.
- **`get_repo_root(start=None)`** — Locates the repository root via `git rev-parse --show-toplevel`.
- **`get_branch(repo_root)`** — Returns the current branch name.
- **`get_head_commit(repo_root)`** — Returns `(sha, message)` for HEAD.
- **`get_changed_files(repo_root)`** — Returns a list of `FileChange` objects from `git status --porcelain=v1`.
- **`get_diff_summary(repo_root)`** — Returns aggregate `DiffSummary` (lines added/deleted, files changed) from `git diff --stat HEAD`.
- **`to_dict(state)`** — Serialises a `GitState` to a JSON-compatible dict.

All subprocess calls use explicit argument lists, capture stdout/stderr, check return codes, and never use `shell=True`.

### `shipsafe/analyzer/test_analyzer.py`

Executes the test suite via subprocess and returns structured, deterministic results.

- **`run_tests(repo_root, test_path, with_coverage, coverage_source)`** — Runs pytest and returns `(TestResult, CoverageResult | None)`.
- **`to_dict(result, coverage)`** — Serialises results to a JSON-compatible dict.

Values parsed from real pytest output:
- `total`, `passed_count`, `failed_count`, `skipped_count`, `error_count`, `duration_seconds`
- Coverage: `total_percent`, `statements`, `missed` (from pytest-cov TOTAL line)

If pytest-cov is unavailable, `CoverageResult.available` is set to `False` and the error is recorded. No coverage values are invented.

### `shipsafe/analyzer/requirements.py`

Loads release requirements from the canonical Markdown source file.

- **`load(requirements_file=None, repo_root=None)`** — Parses and validates requirements. Returns a list of `Requirement` dataclass instances.
- **`to_dict(requirements)`** — Serialises to JSON-compatible list.

**Canonical source:** `requirements/CareHub_v2_4_Requirements.md`

**PDF note:** `requirements/CareHub_v2_4_Requirements.pdf` is the human-facing document. It is intended as context for IBM Bob. This module does not parse the PDF — only the Markdown file is used for deterministic loading.

Validation enforced:
- All five IDs (R001–R005) must be present.
- No ID may be duplicated.
- Each requirement must have non-empty text.

Raises `RequirementsError` with an actionable message if any validation fails.

### `shipsafe/analyzer/evidence.py`

Defines the `Evidence` dataclass and helpers for constructing validated evidence records.

Evidence is the foundation of all findings. Every confirmed finding must trace to at least one concrete evidence record.

Evidence types:
- `CODE` — a specific code pattern at a known file/line
- `TEST_FAILURE` — a named test that failed, with its output
- `COMMAND_OUTPUT` — the stdout/stderr of a real command
- `FILE_PRESENCE` — presence or absence of a specific file
- `GIT_CHANGE` — a file identified in the Git diff
- `REQUIREMENT_GAP` — a gap between a requirement and implementation
- `SCHEMA_CHANGE` — a model/schema change with database evidence

**`build(...)`** validates the evidence record before returning it. Concrete evidence must have at least one locating attribute (`file_path`, `command`, or `test_name`). Generic or inferred evidence must be marked `is_concrete=False`.

### `shipsafe/analyzer/metrics.py`

Collects a deterministic metrics snapshot from Git and pytest output.

- **`collect(repo_root, test_path, with_coverage, coverage_source)`** — Full collection entry point. Returns a `Metrics` dataclass.
- **`to_dict(m)`** — Serialises to JSON-compatible dict.
- **`validate_no_placeholders(m)`** — Sanity check that returns warnings if suspicious sentinel values are detected.

No field defaults to a fabricated number. Fields that cannot be determined are `None`.

### `shipsafe/analyzer/report_builder.py`

Deterministic infrastructure for creating, populating, validating, merging, saving, and loading ShipSafe reports.

- **`create_empty(report_type, status)`** — Returns a valid empty report dict.
- **`add_finding(report, finding)`** — Validates and adds a finding in-place.
- **`set_metrics(report, metrics)`** — Attaches a metrics dict.
- **`validate(report)`** — Returns a list of structural error messages.
- **`merge(base, *fragments)`** — Merges report fragments; raises `DuplicateFindingError` on conflicting finding IDs.
- **`save(report, path)`** — Validates and saves to JSON.
- **`load(path)`** — Loads and validates from JSON.

Rules enforced:
- `CONFIRMED` findings must have at least one evidence record.
- Severity must be one of: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`.
- Finding status must be one of: `CONFIRMED`, `WARNING`, `INFORMATIONAL`.
- Duplicate finding IDs during merge raise `DuplicateFindingError` rather than silently choosing one.

### `shipsafe/analyzer/runner.py`

Single orchestration entry point for the engine.

- **`run_analysis(...)`** — Runs all analysis steps and returns the report dict.

Can be invoked as:

```
python -m shipsafe.analyzer.runner
```

Optional arguments:
- `--repo-root PATH` — explicit repository root
- `--test-path PATH` — relative path to test directory
- `--no-coverage` — skip coverage measurement
- `--report PATH` — output report path

---

## Evidence Philosophy

Evidence is not an annotation. It is a concrete, traceable pointer to something real in the repository or from real command execution.

A finding without evidence must not be marked `CONFIRMED`. The `report_builder` enforces this rule at write time: any attempt to add a `CONFIRMED` finding with an empty evidence list raises `ReportError`.

Examples of acceptable evidence:
- `file_path: "demo_target/routes/appointments.py"`, `line_start: 45`, `symbol: "cancel"` — a code location
- `test_name: "test_cancelled_appointment_does_not_trigger_reminder"`, `output: "FAILED..."` — a test failure
- `command: ["pytest", "-q"]`, `output: "1 failed in 3.5s"` — command output
- `requirement_id: "R001"`, `description: "Cancellation check missing from notification_service.py"` — requirement gap with file evidence

Examples that are NOT acceptable as concrete evidence:
- "This file might be affected"
- "SQL injection is common in Flask apps"
- "Coverage might be low"

---

## How Git Analysis Works

1. `get_repo_root()` calls `git rev-parse --show-toplevel` to find the repository root from any subdirectory.
2. `get_branch()` calls `git rev-parse --abbrev-ref HEAD`.
3. `get_head_commit()` calls `git log -1 --format=%H%n%s`.
4. `get_changed_files()` calls `git status --porcelain=v1 --untracked-files=all` and parses the stable machine-readable output format.
5. `get_diff_summary()` calls `git diff --stat HEAD` and parses the aggregate summary line.

No Git output is invented or hard-coded.

---

## How Test Analysis Works

1. `run_tests()` builds a `pytest` command with explicit arguments and runs it via `subprocess.run()` with `stdout=PIPE, stderr=PIPE, text=True`.
2. The combined output is parsed for the pytest summary line (e.g. `"38 passed in 4.55s"`).
3. If `with_coverage=True`, pytest-cov flags are added and the `TOTAL` line is parsed for the coverage percentage.
4. If pytest is not installed, the error is captured in `TestResult.error` — the engine does not install dependencies.
5. If pytest-cov is not installed, `CoverageResult.available` is `False` — no coverage percentage is invented.

---

## How Requirements Are Loaded

1. The Markdown file `requirements/CareHub_v2_4_Requirements.md` is read.
2. Requirement headings (`## R001`, etc.) are located by regex.
3. The text between headings is extracted and normalised.
4. All five IDs (R001–R005) are validated as present, non-duplicate, and non-empty.
5. Requirements are returned as `Requirement` dataclass instances with `requirement_id`, `requirement_text`, and `source_file`.

---

## Report Structure

The report written to `reports/latest_release_report.json` conforms to `shipsafe/schemas/report_schema.json`.

Top-level fields:

| Field | Description |
|---|---|
| `report_type` | `"base_analysis"` for this engine |
| `generated_at` | ISO-8601 UTC timestamp |
| `status` | `"ANALYSIS_ONLY"` at baseline (no agents run yet) |
| `summary` | Finding count by severity |
| `findings` | Empty list at baseline |
| `metrics` | Measured Git and test metrics |
| `repository` | Repo root, branch, HEAD commit, is_clean |
| `git` | Changed files, diff summary |
| `requirements` | Loaded requirements (R001–R005) |
| `test_analysis` | Test results and coverage |
| `git_evidence` | GIT_CHANGE evidence for changed files |

---

## How to Execute the Engine

From the repository root:

```bash
python -m shipsafe.analyzer.runner
```

With options:

```bash
python -m shipsafe.analyzer.runner --no-coverage
python -m shipsafe.analyzer.runner --test-path demo_target/tests --report reports/my_report.json
```

Output is printed to stdout and the report is saved to `reports/latest_release_report.json`.

---

## What the Engine Does NOT Do Yet

The deterministic engine intentionally does not:

- Make AI-based analysis decisions
- Call external APIs or LLM services
- Add findings to the report (the `findings` array is empty at this stage)
- Run the five Bob analysis agents
- Perform remediation
- Determine release status beyond `ANALYSIS_ONLY`
- Inspect individual lines of code for vulnerabilities
- Compare API response shapes to expected contracts
- Check migration files against model definitions

These are the responsibilities of the five Bob analysis agents that will be built in the next phase.

---

## How This Engine Will Support the Five Bob Analysis Agents

The deterministic engine provides the shared infrastructure that each agent will use:

| Agent | Engine support used |
|---|---|
| Impact Analyst | `git_analyzer.get_changed_files()`, `git_analyzer.to_dict()` |
| Test Gap Analyst | `test_analyzer.run_tests()`, changed file list |
| Security Analyst | `git_analyzer.get_changed_files()`, file content reading |
| Contract & Documentation Analyst | `requirements.load()`, changed route/service files |
| Database Analyst | `git_analyzer.get_changed_files()`, migration directory inspection |
| Release Synthesizer | `report_builder.merge()`, `report_builder.save()` |

Each agent will:
1. Read the base analysis report produced by this engine.
2. Use the `evidence` module to construct concrete evidence records.
3. Use the `report_builder` module to create and save its isolated agent report.
4. Not edit application source code during analysis.
