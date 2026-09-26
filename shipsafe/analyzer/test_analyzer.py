"""ShipSafe test analyzer.

Executes the repository test suite via subprocess and returns structured,
deterministic results.  All values come from real pytest output.

No values are invented or hard-coded.

Coverage execution:
    Uses ``pytest --cov=demo_target --cov-report=term-missing``.
    If pytest-cov is unavailable the coverage fields are set to
    ``coverage_available=False`` rather than inventing numbers.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    """Structured result from a pytest run."""
    command: list[str]
    exit_code: int
    passed: bool            # True only when exit_code == 0 and no failures

    # Counts parsed from pytest output (None = could not parse)
    total: Optional[int] = None
    passed_count: Optional[int] = None
    failed_count: Optional[int] = None
    skipped_count: Optional[int] = None
    error_count: Optional[int] = None
    duration_seconds: Optional[float] = None

    # Raw output
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None  # set when pytest could not run at all


@dataclass
class CoverageResult:
    """Coverage information parsed from pytest-cov output."""
    available: bool
    total_percent: Optional[float] = None       # e.g. 98.0
    statements: Optional[int] = None
    missed: Optional[int] = None
    raw_output: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# "38 passed in 3.59s"
# "1 failed, 37 passed in 3.59s"
# "2 passed, 1 skipped in 1.22s"
_SUMMARY_RE = re.compile(
    r"(?:(\d+) failed)?[,\s]*"
    r"(?:(\d+) passed)?[,\s]*"
    r"(?:(\d+) skipped)?[,\s]*"
    r"(?:(\d+) error)?[,\s]*"
    r"in ([\d.]+)s",
    re.IGNORECASE,
)

# "TOTAL   434  10  98%"
_COVERAGE_TOTAL_RE = re.compile(
    r"^TOTAL\s+(\d+)\s+(\d+)\s+([\d.]+)%",
    re.MULTILINE,
)


def _parse_test_summary(output: str) -> dict:
    """Parse a pytest summary line and return a dict of counts."""
    result: dict[str, Optional[int | float]] = {
        "total": None,
        "passed": None,
        "failed": None,
        "skipped": None,
        "error": None,
        "duration_seconds": None,
    }

    # Look for the final summary line (last line containing "passed" or "failed")
    for line in reversed(output.splitlines()):
        m = _SUMMARY_RE.search(line)
        if m:
            failed = int(m.group(1)) if m.group(1) else 0
            passed = int(m.group(2)) if m.group(2) else 0
            skipped = int(m.group(3)) if m.group(3) else 0
            errors = int(m.group(4)) if m.group(4) else 0
            duration = float(m.group(5)) if m.group(5) else None

            result["failed"] = failed
            result["passed"] = passed
            result["skipped"] = skipped
            result["error"] = errors
            result["total"] = passed + failed + skipped + errors
            result["duration_seconds"] = duration
            break

    return result


def _parse_coverage(output: str) -> CoverageResult:
    """Parse pytest-cov TOTAL line from combined stdout."""
    m = _COVERAGE_TOTAL_RE.search(output)
    if not m:
        # pytest-cov not active or output format changed
        if "No module named pytest_cov" in output or "no module named" in output.lower():
            return CoverageResult(available=False,
                                  error="pytest-cov not installed",
                                  raw_output=output)
        return CoverageResult(available=False,
                              error="Coverage data not found in output",
                              raw_output=output)

    statements = int(m.group(1))
    missed = int(m.group(2))
    percent = float(m.group(3))
    return CoverageResult(
        available=True,
        total_percent=percent,
        statements=statements,
        missed=missed,
        raw_output=output,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_pytest_command(test_path: str,
                          with_coverage: bool,
                          coverage_source: str) -> list[str]:
    cmd = [sys.executable, "-m", "pytest", test_path, "-q"]
    if with_coverage:
        cmd += [f"--cov={coverage_source}", "--cov-report=term-missing"]
    return cmd


def run_tests(
    repo_root: str,
    test_path: str = "demo_target/tests",
    with_coverage: bool = False,
    coverage_source: str = "demo_target",
) -> tuple[TestResult, Optional[CoverageResult]]:
    """Execute the test suite and return structured results.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root (tests are run from here).
    test_path:
        Path to the test directory, relative to ``repo_root``.
    with_coverage:
        If True, pass ``--cov`` flags to pytest.
    coverage_source:
        The source directory/package to measure coverage for.

    Returns
    -------
    (TestResult, CoverageResult | None)
        CoverageResult is None when ``with_coverage=False``.
    """
    cmd = _build_pytest_command(test_path, with_coverage, coverage_source)

    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        result = TestResult(
            command=cmd,
            exit_code=-1,
            passed=False,
            error=f"pytest executable not found: {exc}",
        )
        return result, None
    except Exception as exc:  # noqa: BLE001
        result = TestResult(
            command=cmd,
            exit_code=-1,
            passed=False,
            error=str(exc),
        )
        return result, None

    combined = proc.stdout + proc.stderr
    counts = _parse_test_summary(combined)

    test_result = TestResult(
        command=cmd,
        exit_code=proc.returncode,
        passed=proc.returncode == 0,
        total=counts["total"],
        passed_count=counts["passed"],
        failed_count=counts["failed"],
        skipped_count=counts["skipped"],
        error_count=counts["error"],
        duration_seconds=counts["duration_seconds"],
        stdout=proc.stdout,
        stderr=proc.stderr,
    )

    cov_result = None
    if with_coverage:
        cov_result = _parse_coverage(combined)

    return test_result, cov_result


def to_dict(result: TestResult,
            coverage: Optional[CoverageResult] = None) -> dict:
    """Serialise test results to a JSON-compatible dict."""
    d: dict = {
        "command": result.command,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "total": result.total,
        "passed_count": result.passed_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "error_count": result.error_count,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
    }
    if coverage is not None:
        d["coverage"] = {
            "available": coverage.available,
            "total_percent": coverage.total_percent,
            "statements": coverage.statements,
            "missed": coverage.missed,
            "error": coverage.error,
        }
    return d
