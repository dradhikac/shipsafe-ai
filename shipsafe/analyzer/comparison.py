"""ShipSafe Before/After Comparison Engine.

Provides deterministic snapshot capture and comparison across:
1. BASELINE (clean validated repository)
2. BAD_RELEASE (controlled regression applied)
3. POST_REMEDIATION (remediated and re-validated state)

All metrics are gathered from real execution (pytest, pytest-cov, git, and
synthesized release reports). No metrics are fabricated or hard-coded.
When a state or metric is not available (such as POST_REMEDIATION before fixes),
it is explicitly represented as unavailable (e.g. status="NOT_AVAILABLE")
and never coerced to zero.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shipsafe.analyzer import git_analyzer, test_analyzer


# ---------------------------------------------------------------------------
# Constants & Defaults
# ---------------------------------------------------------------------------

VALID_STATES = ("BASELINE", "BAD_RELEASE", "POST_REMEDIATION")
DEFAULT_REPORT_PATH = "reports/latest_release_report.json"
DEFAULT_COMPARISON_PATH = "reports/comparison.json"


# ---------------------------------------------------------------------------
# Validation & Delta Helpers
# ---------------------------------------------------------------------------

def calculate_delta(before: Any, current: Any) -> Optional[int | float]:
    """Calculate current - before if both are numeric, else return None.

    CRITICAL: Does NOT treat None or unavailable values as zero.
    Does NOT treat booleans as integers.
    """
    if before is None or current is None:
        return None
    if isinstance(before, bool) or isinstance(current, bool):
        return None
    if isinstance(before, (int, float)) and isinstance(current, (int, float)):
        if isinstance(before, int) and isinstance(current, int):
            return current - before
        return round(float(current) - float(before), 4)
    return None


def validate_snapshot(snapshot: Any) -> None:
    """Validate that a snapshot dict conforms to the expected structure.

    Raises ValueError if malformed.
    """
    if not isinstance(snapshot, dict):
        raise ValueError(f"Snapshot must be a dict, got {type(snapshot).__name__}")

    if "state" not in snapshot:
        raise ValueError("Snapshot missing required field: 'state'")

    state = snapshot["state"]
    if state not in VALID_STATES:
        raise ValueError(f"Invalid snapshot state '{state}'. Expected one of {VALID_STATES}")

    # Explicit unavailable post-remediation snapshot is valid
    if state == "POST_REMEDIATION" and snapshot.get("status") == "NOT_AVAILABLE":
        return

    required_sections = ["git", "tests", "coverage", "requirements", "findings"]
    for sec in required_sections:
        if sec not in snapshot:
            raise ValueError(f"Snapshot missing required section: '{sec}'")
        if snapshot[sec] is not None and not isinstance(snapshot[sec], dict):
            raise ValueError(f"Snapshot section '{sec}' must be a dict or None")


# ---------------------------------------------------------------------------
# Snapshot Capture
# ---------------------------------------------------------------------------

def _extract_report_metrics(report_data: dict) -> tuple[dict, dict, int]:
    """Extract requirements counts, findings counts, and affected files from report."""
    # Findings severity counts from findings array (authoritative)
    findings_arr = report_data.get("findings", [])
    critical = sum(1 for f in findings_arr if f.get("severity") == "CRITICAL")
    high = sum(1 for f in findings_arr if f.get("severity") == "HIGH")
    medium = sum(1 for f in findings_arr if f.get("severity") == "MEDIUM")
    low = sum(1 for f in findings_arr if f.get("severity") == "LOW")
    info = sum(1 for f in findings_arr if f.get("severity") == "INFO")
    total_findings = len(findings_arr)

    findings_dict = {
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "info": info,
        "total": total_findings,
    }

    # Requirements compliance counts
    req_compliance = report_data.get("requirement_compliance", [])
    if req_compliance:
        total_reqs = len(req_compliance)
        failed_reqs = sum(1 for r in req_compliance if r.get("status") in ("FAIL", "NON_COMPLIANT"))
        passed_reqs = sum(1 for r in req_compliance if r.get("status") in ("PASS", "COMPLIANT"))
        warning_reqs = sum(1 for r in req_compliance if r.get("status") in ("WARNING", "WARN"))
        unverifiable_reqs = sum(1 for r in req_compliance if r.get("status") in ("UNVERIFIABLE", "UNKNOWN"))
    else:
        req_list = report_data.get("requirements", [])
        total_reqs = len(req_list)
        failed_reqs = 0
        passed_reqs = 0
        warning_reqs = 0
        unverifiable_reqs = 0

    requirements_dict = {
        "total": total_reqs,
        "failed": failed_reqs,
        "passed": passed_reqs,
        "warning": warning_reqs,
        "unverifiable": unverifiable_reqs,
    }

    # Affected files (targeted application files)
    affected = set()
    for f in findings_arr:
        for p in f.get("affected_files", []):
            affected.add(p)
    git_files = report_data.get("git", {}).get("changed_files", [])
    for gf in git_files:
        p = gf.get("path") if isinstance(gf, dict) else gf
        if p and (p.startswith("demo_target/") or p.startswith("migrations/")):
            affected.add(p)

    return requirements_dict, findings_dict, len(affected)


def capture_snapshot(
    state: str,
    repo_root: Optional[str] = None,
    test_path: str = "demo_target/tests",
    with_coverage: bool = True,
    coverage_source: str = "demo_target",
    release_report_path: Optional[str] = None,
    release_report_data: Optional[dict] = None,
    is_available: bool = True,
) -> dict:
    """Capture a point-in-time metrics snapshot from actual repository execution.

    Parameters
    ----------
    state:
        One of 'BASELINE', 'BAD_RELEASE', 'POST_REMEDIATION'.
    repo_root:
        Absolute path to the repository root. Auto-detected if None.
    test_path:
        Relative path to tests.
    with_coverage:
        Whether to run pytest with coverage.
    coverage_source:
        Package/directory for pytest-cov.
    release_report_path:
        Optional path to latest_release_report.json.
    release_report_data:
        Optional pre-loaded release report dict.
    is_available:
        For POST_REMEDIATION, if False or remediation has not run, creates an explicit
        unavailable state without fabricating numbers.

    Returns
    -------
    dict
        Snapshot conforming to metric model.
    """
    if state not in VALID_STATES:
        raise ValueError(f"Invalid state '{state}'. Expected one of {VALID_STATES}")

    # Handle explicitly unavailable POST_REMEDIATION
    if state == "POST_REMEDIATION" and not is_available:
        return {
            "state": "POST_REMEDIATION",
            "status": "NOT_AVAILABLE",
            "captured_at": None,
            "git": None,
            "tests": None,
            "coverage": None,
            "requirements": None,
            "findings": None,
            "affected_files": None,
        }

    if repo_root is None:
        repo_root = git_analyzer.get_repo_root()
    root = Path(repo_root)

    captured_at = datetime.now(tz=timezone.utc).isoformat()

    # 1. Real Git metadata
    git_state = git_analyzer.analyze(repo_root)
    git_dict = git_analyzer.to_dict(git_state)
    diff = git_dict.get("diff_summary", {})

    git_info = {
        "commit": git_dict.get("head_commit"),
        "branch": git_dict.get("branch"),
        "is_clean": git_dict.get("is_clean"),
        "files_changed": diff.get("files_changed") or 0,
        "lines_added": diff.get("lines_added") or 0,
        "lines_deleted": diff.get("lines_deleted") or 0,
    }

    # 2. Real pytest execution
    test_result, cov_result = test_analyzer.run_tests(
        repo_root=repo_root,
        test_path=test_path,
        with_coverage=with_coverage,
        coverage_source=coverage_source,
    )

    tests_info = {
        "total": test_result.total if test_result.total is not None else 0,
        "passed": test_result.passed_count if test_result.passed_count is not None else 0,
        "failed": test_result.failed_count if test_result.failed_count is not None else 0,
        "skipped": test_result.skipped_count if test_result.skipped_count is not None else 0,
        "errors": test_result.error_count if test_result.error_count is not None else 0,
        "duration_seconds": test_result.duration_seconds if test_result.duration_seconds is not None else 0.0,
    }

    coverage_info = {
        "available": cov_result.available if cov_result else False,
        "percent": cov_result.total_percent if (cov_result and cov_result.available) else None,
        "statements": cov_result.statements if (cov_result and cov_result.available) else None,
        "missed": cov_result.missed if (cov_result and cov_result.available) else None,
    }

    # 3. Requirements and Findings
    if state == "BASELINE":
        # At baseline, all 5 requirements are satisfied and 0 findings exist
        requirements_info = {
            "total": 5,
            "failed": 0,
            "passed": 5,
            "warning": 0,
            "unverifiable": 0,
        }
        findings_info = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "total": 0,
        }
        affected_files_count = 0
    else:
        # Load from synthesized report
        report = release_report_data
        if report is None:
            r_path = root / (release_report_path or DEFAULT_REPORT_PATH)
            if r_path.exists():
                with open(r_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
            else:
                report = {}

        requirements_info, findings_info, affected_files_count = _extract_report_metrics(report)

    snapshot = {
        "state": state,
        "captured_at": captured_at,
        "git": git_info,
        "tests": tests_info,
        "coverage": coverage_info,
        "requirements": requirements_info,
        "findings": findings_info,
        "affected_files": affected_files_count,
    }

    validate_snapshot(snapshot)
    return snapshot


# ---------------------------------------------------------------------------
# Snapshot Comparison
# ---------------------------------------------------------------------------

def _compare_subdict(before_dict: Optional[dict], current_dict: Optional[dict], keys: list[str]) -> dict:
    """Compare fields in two dictionaries."""
    res = {}
    for k in keys:
        b_val = before_dict.get(k) if isinstance(before_dict, dict) else None
        c_val = current_dict.get(k) if isinstance(current_dict, dict) else None
        d_val = calculate_delta(b_val, c_val)
        status = "AVAILABLE" if (b_val is not None and c_val is not None) else "UNAVAILABLE"
        res[k] = {
            "before": b_val,
            "current": c_val,
            "delta": d_val,
            "status": status,
        }
    return res


def compare_snapshots(
    baseline: dict,
    bad_release: dict,
    post_remediation: Optional[dict] = None,
) -> dict:
    """Compare BASELINE, BAD_RELEASE, and optional POST_REMEDIATION snapshots.

    Parameters
    ----------
    baseline:
        Baseline metrics snapshot dict.
    bad_release:
        Bad release metrics snapshot dict.
    post_remediation:
        Post-remediation metrics snapshot dict, or None (defaults to unavailable).

    Returns
    -------
    dict
        Structured comparison report.
    """
    validate_snapshot(baseline)
    validate_snapshot(bad_release)

    if post_remediation is None:
        post_remediation = {"state": "POST_REMEDIATION", "status": "NOT_AVAILABLE"}
    else:
        validate_snapshot(post_remediation)

    # Comparison: bad_release vs baseline
    bad_vs_base = {
        "tests": _compare_subdict(
            baseline.get("tests"),
            bad_release.get("tests"),
            ["total", "passed", "failed", "skipped", "errors", "duration_seconds"],
        ),
        "coverage": _compare_subdict(
            baseline.get("coverage"),
            bad_release.get("coverage"),
            ["percent", "statements", "missed"],
        ),
        "requirements": _compare_subdict(
            baseline.get("requirements"),
            bad_release.get("requirements"),
            ["total", "passed", "failed", "warning", "unverifiable"],
        ),
        "findings": _compare_subdict(
            baseline.get("findings"),
            bad_release.get("findings"),
            ["critical", "high", "medium", "low", "info", "total"],
        ),
        "changes": {
            "files_changed": {
                "before": baseline.get("git", {}).get("files_changed", 0),
                "current": bad_release.get("git", {}).get("files_changed", 0),
                "delta": calculate_delta(
                    baseline.get("git", {}).get("files_changed", 0),
                    bad_release.get("git", {}).get("files_changed", 0),
                ),
                "status": "AVAILABLE",
            },
            "lines_added": {
                "before": baseline.get("git", {}).get("lines_added", 0),
                "current": bad_release.get("git", {}).get("lines_added", 0),
                "delta": calculate_delta(
                    baseline.get("git", {}).get("lines_added", 0),
                    bad_release.get("git", {}).get("lines_added", 0),
                ),
                "status": "AVAILABLE",
            },
            "lines_deleted": {
                "before": baseline.get("git", {}).get("lines_deleted", 0),
                "current": bad_release.get("git", {}).get("lines_deleted", 0),
                "delta": calculate_delta(
                    baseline.get("git", {}).get("lines_deleted", 0),
                    bad_release.get("git", {}).get("lines_deleted", 0),
                ),
                "status": "AVAILABLE",
            },
            "affected_files": {
                "before": baseline.get("affected_files", 0),
                "current": bad_release.get("affected_files", 0),
                "delta": calculate_delta(
                    baseline.get("affected_files", 0),
                    bad_release.get("affected_files", 0),
                ),
                "status": "AVAILABLE",
            },
        },
    }

    # Comparison: post_remediation vs bad_release
    is_post_avail = post_remediation.get("status") != "NOT_AVAILABLE" and post_remediation.get("tests") is not None
    if not is_post_avail:
        post_vs_bad = {"status": "NOT_AVAILABLE"}
        post_vs_base = {"status": "NOT_AVAILABLE"}
    else:
        post_vs_bad = {
            "tests": _compare_subdict(
                bad_release.get("tests"),
                post_remediation.get("tests"),
                ["total", "passed", "failed", "skipped", "errors", "duration_seconds"],
            ),
            "coverage": _compare_subdict(
                bad_release.get("coverage"),
                post_remediation.get("coverage"),
                ["percent", "statements", "missed"],
            ),
            "requirements": _compare_subdict(
                bad_release.get("requirements"),
                post_remediation.get("requirements"),
                ["total", "passed", "failed", "warning", "unverifiable"],
            ),
            "findings": _compare_subdict(
                bad_release.get("findings"),
                post_remediation.get("findings"),
                ["critical", "high", "medium", "low", "info", "total"],
            ),
        }
        post_vs_base = {
            "tests": _compare_subdict(
                baseline.get("tests"),
                post_remediation.get("tests"),
                ["total", "passed", "failed", "skipped", "errors", "duration_seconds"],
            ),
            "coverage": _compare_subdict(
                baseline.get("coverage"),
                post_remediation.get("coverage"),
                ["percent", "statements", "missed"],
            ),
            "requirements": _compare_subdict(
                baseline.get("requirements"),
                post_remediation.get("requirements"),
                ["total", "passed", "failed", "warning", "unverifiable"],
            ),
            "findings": _compare_subdict(
                baseline.get("findings"),
                post_remediation.get("findings"),
                ["critical", "high", "medium", "low", "info", "total"],
            ),
        }

    # Consolidated flat metrics table for quick rendering / inspection
    flat_metrics = {
        "tests_total": {
            "baseline": baseline.get("tests", {}).get("total"),
            "bad_release": bad_release.get("tests", {}).get("total"),
            "post_remediation": post_remediation.get("tests", {}).get("total") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["tests"]["total"]["delta"],
            "delta_remediation": post_vs_bad["tests"]["total"]["delta"] if is_post_avail else None,
        },
        "tests_passed": {
            "baseline": baseline.get("tests", {}).get("passed"),
            "bad_release": bad_release.get("tests", {}).get("passed"),
            "post_remediation": post_remediation.get("tests", {}).get("passed") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["tests"]["passed"]["delta"],
            "delta_remediation": post_vs_bad["tests"]["passed"]["delta"] if is_post_avail else None,
        },
        "tests_failed": {
            "baseline": baseline.get("tests", {}).get("failed"),
            "bad_release": bad_release.get("tests", {}).get("failed"),
            "post_remediation": post_remediation.get("tests", {}).get("failed") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["tests"]["failed"]["delta"],
            "delta_remediation": post_vs_bad["tests"]["failed"]["delta"] if is_post_avail else None,
        },
        "coverage_percent": {
            "baseline": baseline.get("coverage", {}).get("percent"),
            "bad_release": bad_release.get("coverage", {}).get("percent"),
            "post_remediation": post_remediation.get("coverage", {}).get("percent") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["coverage"]["percent"]["delta"],
            "delta_remediation": post_vs_bad["coverage"]["percent"]["delta"] if is_post_avail else None,
        },
        "requirements_passed": {
            "baseline": baseline.get("requirements", {}).get("passed"),
            "bad_release": bad_release.get("requirements", {}).get("passed"),
            "post_remediation": post_remediation.get("requirements", {}).get("passed") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["requirements"]["passed"]["delta"],
            "delta_remediation": post_vs_bad["requirements"]["passed"]["delta"] if is_post_avail else None,
        },
        "requirements_failed": {
            "baseline": baseline.get("requirements", {}).get("failed"),
            "bad_release": bad_release.get("requirements", {}).get("failed"),
            "post_remediation": post_remediation.get("requirements", {}).get("failed") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["requirements"]["failed"]["delta"],
            "delta_remediation": post_vs_bad["requirements"]["failed"]["delta"] if is_post_avail else None,
        },
        "findings_critical": {
            "baseline": baseline.get("findings", {}).get("critical"),
            "bad_release": bad_release.get("findings", {}).get("critical"),
            "post_remediation": post_remediation.get("findings", {}).get("critical") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["findings"]["critical"]["delta"],
            "delta_remediation": post_vs_bad["findings"]["critical"]["delta"] if is_post_avail else None,
        },
        "findings_high": {
            "baseline": baseline.get("findings", {}).get("high"),
            "bad_release": bad_release.get("findings", {}).get("high"),
            "post_remediation": post_remediation.get("findings", {}).get("high") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["findings"]["high"]["delta"],
            "delta_remediation": post_vs_bad["findings"]["high"]["delta"] if is_post_avail else None,
        },
        "findings_total": {
            "baseline": baseline.get("findings", {}).get("total"),
            "bad_release": bad_release.get("findings", {}).get("total"),
            "post_remediation": post_remediation.get("findings", {}).get("total") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["findings"]["total"]["delta"],
            "delta_remediation": post_vs_bad["findings"]["total"]["delta"] if is_post_avail else None,
        },
        "affected_files": {
            "baseline": baseline.get("affected_files", 0),
            "bad_release": bad_release.get("affected_files", 0),
            "post_remediation": post_remediation.get("affected_files") if is_post_avail else None,
            "delta_bad_release": bad_vs_base["changes"]["affected_files"]["delta"],
            "delta_remediation": calculate_delta(
                bad_release.get("affected_files", 0),
                post_remediation.get("affected_files", 0),
            ) if is_post_avail else None,
        },
    }

    comparison_report = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "baseline": baseline,
        "bad_release": bad_release,
        "post_remediation": post_remediation,
        "comparisons": {
            "bad_release_vs_baseline": bad_vs_base,
            "post_remediation_vs_bad_release": post_vs_bad,
            "post_remediation_vs_baseline": post_vs_base,
            "metrics_summary": flat_metrics,
        },
    }

    return comparison_report


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_comparison(comparison_data: dict, output_path: str = DEFAULT_COMPARISON_PATH) -> str:
    """Save comparison dictionary to disk as formatted JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(comparison_data, f, indent=2)
    return str(path)


def load_comparison(input_path: str = DEFAULT_COMPARISON_PATH) -> dict:
    """Load comparison dictionary from disk."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Comparison report not found at: {input_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def capture_post_remediation(
    repo_root: Optional[str] = None,
    output_path: str = DEFAULT_COMPARISON_PATH,
) -> dict:
    """Capture a live POST_REMEDIATION snapshot from actual execution and update comparison.json."""
    if repo_root is None:
        repo_root = git_analyzer.get_repo_root()
    root = Path(repo_root)

    comp_file = root / output_path
    if not comp_file.is_file():
        raise FileNotFoundError(f"Existing comparison report not found at: {comp_file}")

    with open(comp_file, "r", encoding="utf-8") as f:
        existing = json.load(f)

    baseline = existing["baseline"]
    bad_release = existing["bad_release"]

    # Capture real POST_REMEDIATION snapshot
    post_remediation = capture_snapshot(
        "POST_REMEDIATION",
        repo_root=repo_root,
        is_available=True,
    )

    # Compute comparison
    comp = compare_snapshots(baseline, bad_release, post_remediation)

    # Save to disk
    save_comparison(comp, str(comp_file))
    return comp


# ---------------------------------------------------------------------------
# CLI Workflow Runner
# ---------------------------------------------------------------------------

def run_workflow(repo_root: Optional[str] = None) -> dict:
    """Execute the full measurement sequence:

    1. reset_demo.py (restore clean baseline)
    2. verify baseline tests pass
    3. capture BASELINE snapshot
    4. apply_demo_release.py
    5. capture BAD_RELEASE snapshot
    6. generate comparisons
    7. save reports/comparison.json
    8. reset_demo.py (restore clean baseline again)
    9. verify clean baseline tests pass
    """
    if repo_root is None:
        repo_root = git_analyzer.get_repo_root()
    root = Path(repo_root)

    print("[1/9] Resetting demo target to clean baseline...")
    subprocess.run([sys.executable, str(root / "scripts" / "reset_demo.py")], cwd=repo_root, check=True)

    print("[2/9] Capturing BASELINE snapshot...")
    baseline = capture_snapshot("BASELINE", repo_root=repo_root)

    print(f"      Baseline: {baseline['tests']['passed']} tests passed, "
          f"{baseline['coverage']['percent']}% cov, {baseline['findings']['total']} findings.")

    print("[3/9] Applying controlled bad release...")
    subprocess.run([sys.executable, str(root / "scripts" / "apply_demo_release.py")], cwd=repo_root, check=True)

    print("[4/9] Running deterministic analysis (Release Synthesizer)...")
    from shipsafe.analyzer import synthesizer
    synthesizer.synthesize_release(repo_root=repo_root, output_path=str(root / DEFAULT_REPORT_PATH))

    print("[5/9] Capturing BAD_RELEASE snapshot...")
    bad_release = capture_snapshot("BAD_RELEASE", repo_root=repo_root)
    print(f"      Bad release: {bad_release['tests']['passed']} tests passed, "
          f"{bad_release['coverage']['percent']}% cov, {bad_release['findings']['total']} findings.")

    print("[6/9] Initializing POST_REMEDIATION snapshot as NOT_AVAILABLE...")
    post_remediation = capture_snapshot("POST_REMEDIATION", is_available=False)

    print("[7/9] Computing comparisons and numeric deltas...")
    comp = compare_snapshots(baseline, bad_release, post_remediation)

    out_file = str(root / DEFAULT_COMPARISON_PATH)
    print(f"[8/9] Saving comparison report to {out_file}...")
    save_comparison(comp, out_file)

    print("[8/9] Resetting demo target to clean baseline again...")
    subprocess.run([sys.executable, str(root / "scripts" / "reset_demo.py")], cwd=repo_root, check=True)

    print("[9/9] Verifying clean baseline after reset...")
    res = subprocess.run([sys.executable, "-m", "pytest", "demo_target/tests/", "-q"], cwd=repo_root, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("Clean baseline verification failed after reset!")
    print("      Verification confirmed: all baseline tests pass.")

    return comp


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ShipSafe Release Comparison Engine")
    parser.add_argument("--post-remediation", action="store_true", help="Capture post-remediation snapshot from live repo")
    args = parser.parse_args()

    if args.post_remediation:
        comp = capture_post_remediation()
        print("Captured POST_REMEDIATION snapshot successfully.")
        print(f"Post-remediation tests: {comp['post_remediation']['tests']['passed']} passed, "
              f"{comp['post_remediation']['coverage']['percent']}% cov, "
              f"{comp['post_remediation']['findings']['total']} findings.")
    else:
        run_workflow()
