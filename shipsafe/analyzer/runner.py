"""ShipSafe deterministic analysis runner.

Orchestrates the full deterministic analysis pipeline:

1. Locate the repository
2. Inspect Git state
3. Load release requirements
4. Run test analysis (with coverage)
5. Collect metrics
6. Construct a base analysis report
7. Save report to reports/latest_release_report.json

Run from the repository root:

    python -m shipsafe.analyzer.runner

All displayed values come from real execution.  No values are invented.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from shipsafe.analyzer import (
    git_analyzer,
    test_analyzer,
    requirements as req_loader,
    metrics as metrics_module,
    report_builder,
    evidence,
)


# Default paths (relative to repo root)
DEFAULT_TEST_PATH = "demo_target/tests"
DEFAULT_COVERAGE_SOURCE = "demo_target"
DEFAULT_REPORT_PATH = "reports/latest_release_report.json"
DEFAULT_REQUIREMENTS_DIR = "requirements"


def run_analysis(
    repo_root: str | None = None,
    test_path: str = DEFAULT_TEST_PATH,
    coverage_source: str = DEFAULT_COVERAGE_SOURCE,
    report_path: str = DEFAULT_REPORT_PATH,
    with_coverage: bool = True,
) -> dict:
    """Run a complete deterministic analysis and return the report dict.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.  Auto-detected if None.
    test_path:
        Path to the test directory, relative to ``repo_root``.
    coverage_source:
        Coverage source package/directory.
    report_path:
        Output path for the generated report (relative to ``repo_root``).
    with_coverage:
        Whether to collect coverage metrics.

    Returns
    -------
    dict
        The generated report.  Also saved to ``report_path``.
    """
    # Step 1 — Locate repository
    if repo_root is None:
        repo_root = git_analyzer.get_repo_root()

    root = Path(repo_root)

    # Step 2 — Git state
    git_state = git_analyzer.analyze(repo_root)
    git_dict = git_analyzer.to_dict(git_state)

    # Step 3 — Requirements
    req_file = str(root / DEFAULT_REQUIREMENTS_DIR / "CareHub_v2_4_Requirements.md")
    requirements_error: str | None = None
    loaded_reqs: list[dict] = []
    try:
        reqs = req_loader.load(req_file)
        loaded_reqs = req_loader.to_dict(reqs)
    except (FileNotFoundError, req_loader.RequirementsError) as exc:
        requirements_error = str(exc)

    # Step 4 — Test analysis
    test_result, cov_result = test_analyzer.run_tests(
        repo_root=repo_root,
        test_path=test_path,
        with_coverage=with_coverage,
        coverage_source=coverage_source,
    )
    test_dict = test_analyzer.to_dict(test_result, cov_result)

    # Step 5 — Metrics
    m = metrics_module.Metrics(
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        git_branch=git_dict["branch"],
        git_commit=git_dict["head_commit"],
        is_clean=git_dict["is_clean"],
        files_changed=git_dict["diff_summary"]["files_changed"] or None,
        lines_added=git_dict["diff_summary"]["lines_added"] or None,
        lines_deleted=git_dict["diff_summary"]["lines_deleted"] or None,
        tests_total=test_result.total,
        tests_passed=test_result.passed_count,
        tests_failed=test_result.failed_count,
        tests_skipped=test_result.skipped_count,
        tests_errors=test_result.error_count,
        test_duration_seconds=test_result.duration_seconds,
        coverage_available=cov_result.available if cov_result else False,
        coverage_percent=cov_result.total_percent if cov_result else None,
        coverage_statements=cov_result.statements if cov_result else None,
        coverage_missed=cov_result.missed if cov_result else None,
    )
    metrics_dict = metrics_module.to_dict(m)

    # Step 6 — Build report
    report = report_builder.create_empty(
        report_type="base_analysis",
        status="ANALYSIS_ONLY",
    )
    report["repository"] = {
        "repo_root": git_dict["repo_root"],
        "branch": git_dict["branch"],
        "head_commit": git_dict["head_commit"],
        "head_message": git_dict["head_message"],
        "is_clean": git_dict["is_clean"],
        "error": git_dict["error"],
    }
    report["git"] = {
        "changed_files": git_dict["changed_files"],
        "untracked_files": git_dict["untracked_files"],
        "diff_summary": git_dict["diff_summary"],
    }
    report["requirements"] = loaded_reqs
    if requirements_error:
        report["requirements_error"] = requirements_error
    report["test_analysis"] = test_dict
    report_builder.set_metrics(report, metrics_dict)

    # Attach GIT_CHANGE evidence for each untracked/modified file
    # (informational — not findings; the analysis agents will add findings)
    git_evidence = []
    for fc in git_state.changed_files:
        ev = evidence.from_git_change(fc.path, fc.status)
        git_evidence.append(evidence.to_dict(ev))
    report["git_evidence"] = git_evidence

    # Step 7 — Save report
    abs_report_path = str(root / report_path)
    report_builder.save(report, abs_report_path)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_summary(report: dict, report_path: str) -> None:
    repo = report.get("repository", {})
    git_info = report.get("git", {})
    test_info = report.get("test_analysis", {})
    metrics = report.get("metrics", {})
    reqs = report.get("requirements", [])
    cov = test_info.get("coverage", {})

    changed = git_info.get("diff_summary", {}).get("files_changed", 0) or 0
    untracked = len(git_info.get("untracked_files", []))

    total = test_info.get("total")
    passed = test_info.get("passed_count")
    failed = test_info.get("failed_count")
    duration = test_info.get("duration_seconds")

    cov_str = "not measured"
    if cov and cov.get("available"):
        cov_str = f"{cov['total_percent']}% ({cov['statements']} stmts, {cov['missed']} missed)"
    elif cov and cov.get("error"):
        cov_str = f"unavailable — {cov['error']}"

    test_str = "not run"
    if total is not None:
        test_str = (
            f"{total} collected, {passed} passed, {failed} failed"
            + (f" — {duration:.2f}s" if duration else "")
        )

    print()
    print("=" * 60)
    print("  ShipSafe Deterministic Analysis")
    print("=" * 60)
    print(f"  Repository : {repo.get('repo_root', 'unknown')}")
    print(f"  Branch     : {repo.get('branch', 'unknown')}")
    print(f"  Commit     : {repo.get('head_commit', 'unknown')[:12]}")
    print(f"  Clean      : {repo.get('is_clean', 'unknown')}")
    print(f"  Changed    : {changed} files tracked, {untracked} untracked")
    print(f"  Tests      : {test_str}")
    print(f"  Coverage   : {cov_str}")
    print(f"  Requirements loaded : {len(reqs)}")
    print(f"  Findings   : {len(report.get('findings', []))} (analysis only — no agents run yet)")
    print(f"  Status     : {report.get('status')}")
    print(f"  Report     : {report_path}")
    print("=" * 60)
    print()

    if report.get("requirements_error"):
        print(f"  WARNING — Requirements error: {report['requirements_error']}")
    if repo.get("error"):
        print(f"  WARNING — Git error: {repo['error']}")
    if not test_info.get("passed"):
        print("  WARNING — Tests did not all pass.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ShipSafe deterministic analysis engine"
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (auto-detected if omitted)",
    )
    parser.add_argument(
        "--test-path",
        default=DEFAULT_TEST_PATH,
        help=f"Path to test directory (default: {DEFAULT_TEST_PATH})",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage measurement",
    )
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT_PATH,
        help=f"Output report path (default: {DEFAULT_REPORT_PATH})",
    )
    args = parser.parse_args(argv)

    try:
        report = run_analysis(
            repo_root=args.repo_root,
            test_path=args.test_path,
            report_path=args.report,
            with_coverage=not args.no_coverage,
        )
        report_path = str(
            (Path(args.repo_root or git_analyzer.get_repo_root()) / args.report)
        )
        _print_summary(report, report_path)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
