"""ShipSafe metrics module.

Collects deterministic metrics from real sources:
- Git (branch, commit, diff statistics)
- pytest (test counts, pass/fail, duration)
- pytest-cov (coverage percentage)

No placeholder values are used.  All fields that cannot be determined are
set to None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from shipsafe.analyzer import git_analyzer, test_analyzer


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class Metrics:
    """Point-in-time metrics snapshot for a ShipSafe analysis run."""

    # When this snapshot was taken
    timestamp: str            # ISO-8601 UTC

    # Git metadata
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    is_clean: Optional[bool] = None

    # Diff statistics
    files_changed: Optional[int] = None
    lines_added: Optional[int] = None
    lines_deleted: Optional[int] = None

    # Test counts (None = not measured)
    tests_total: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    tests_skipped: Optional[int] = None
    tests_errors: Optional[int] = None
    test_duration_seconds: Optional[float] = None

    # Coverage
    coverage_available: bool = False
    coverage_percent: Optional[float] = None
    coverage_statements: Optional[int] = None
    coverage_missed: Optional[int] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect(
    repo_root: str,
    test_path: str = "demo_target/tests",
    with_coverage: bool = True,
    coverage_source: str = "demo_target",
) -> Metrics:
    """Collect a full metrics snapshot.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    test_path:
        Relative path to the test directory (passed to pytest).
    with_coverage:
        Whether to collect coverage metrics.
    coverage_source:
        Coverage source package/directory.

    Returns
    -------
    Metrics
        Populated with real values; fields that could not be determined are
        None — never fabricated.
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # Git
    git_state = git_analyzer.analyze(repo_root)
    git_dict = git_analyzer.to_dict(git_state)
    diff = git_dict["diff_summary"]

    # Tests
    test_result, cov_result = test_analyzer.run_tests(
        repo_root=repo_root,
        test_path=test_path,
        with_coverage=with_coverage,
        coverage_source=coverage_source,
    )

    metrics = Metrics(
        timestamp=timestamp,
        git_branch=git_dict["branch"],
        git_commit=git_dict["head_commit"],
        is_clean=git_dict["is_clean"],
        files_changed=diff["files_changed"] or None,
        lines_added=diff["lines_added"] or None,
        lines_deleted=diff["lines_deleted"] or None,
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
    return metrics


def to_dict(m: Metrics) -> dict:
    """Serialise a :class:`Metrics` snapshot to a JSON-compatible dict."""
    return {
        "timestamp": m.timestamp,
        "git_branch": m.git_branch,
        "git_commit": m.git_commit,
        "is_clean": m.is_clean,
        "files_changed": m.files_changed,
        "lines_added": m.lines_added,
        "lines_deleted": m.lines_deleted,
        "tests_total": m.tests_total,
        "tests_passed": m.tests_passed,
        "tests_failed": m.tests_failed,
        "tests_skipped": m.tests_skipped,
        "tests_errors": m.tests_errors,
        "test_duration_seconds": m.test_duration_seconds,
        "coverage_available": m.coverage_available,
        "coverage_percent": m.coverage_percent,
        "coverage_statements": m.coverage_statements,
        "coverage_missed": m.coverage_missed,
    }


def validate_no_placeholders(m: Metrics) -> list[str]:
    """Return a list of warnings if any metrics look like fabricated values.

    This is a sanity check — it cannot guarantee correctness, but it can
    detect obviously wrong sentinel values (e.g. exactly -1, 999, 0 when
    the Git state is not clean).

    Returns an empty list when no suspicious values are detected.
    """
    warnings: list[str] = []
    suspicious_ints = {-1, 999, 9999, 12345}

    for name in ("tests_total", "tests_passed", "tests_failed",
                 "coverage_statements"):
        val = getattr(m, name)
        if val in suspicious_ints:
            warnings.append(
                f"Metric '{name}' has suspicious value {val} — "
                "verify this came from real execution."
            )
    if m.coverage_percent is not None and m.coverage_percent in {0.0, 100.0}:
        warnings.append(
            f"coverage_percent is exactly {m.coverage_percent}% — "
            "verify this came from real execution."
        )
    return warnings
