"""Tests for shipsafe/analyzer/comparison.py.

Verifies deterministic snapshot capture, snapshot comparison, metric delta
calculation, error handling for malformed snapshots, and JSON persistence.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shipsafe.analyzer import comparison
from shipsafe.analyzer.test_analyzer import TestResult, CoverageResult


# ---------------------------------------------------------------------------
# Test Fixtures & Sample Data
# ---------------------------------------------------------------------------

SAMPLE_REPORT_DATA = {
    "report_type": "release_synthesis",
    "summary": {
        "total_findings": 22,
        "critical_count": 1,
        "high_count": 19,
        "medium_count": 2,
        "low_count": 0,
        "info_count": 0,
    },
    "requirements": [
        {"requirement_id": "R001"},
        {"requirement_id": "R002"},
        {"requirement_id": "R003"},
        {"requirement_id": "R004"},
        {"requirement_id": "R005"},
    ],
    "requirement_compliance": [
        {"requirement_id": "R001", "status": "FAIL"},
        {"requirement_id": "R002", "status": "FAIL"},
        {"requirement_id": "R003", "status": "FAIL"},
        {"requirement_id": "R004", "status": "FAIL"},
        {"requirement_id": "R005", "status": "FAIL"},
    ],
    "findings": [
        {"finding_id": "SEC-001", "severity": "CRITICAL", "affected_files": ["demo_target/routes/appointments.py"]},
        {"finding_id": "IMP-001", "severity": "HIGH", "affected_files": ["demo_target/services/notification_service.py"]},
        {"finding_id": "IMP-002", "severity": "HIGH", "affected_files": ["demo_target/models.py"]},
        {"finding_id": "DB-001", "severity": "MEDIUM", "affected_files": ["demo_target/db.py"]},
    ],
    "git": {
        "changed_files": [
            {"path": "demo_target/db.py"},
            {"path": "demo_target/models.py"},
        ]
    }
}


# ---------------------------------------------------------------------------
# 1. Baseline Snapshot Structure
# ---------------------------------------------------------------------------

def test_baseline_snapshot_structure():
    """Verify that a baseline snapshot contains all expected fields and valid structures."""
    # Mock run_tests and git_analyzer to test structure without running full subprocess
    mock_test = TestResult(command=[], exit_code=0, passed=True, total=38, passed_count=38, failed_count=0, skipped_count=0, error_count=0, duration_seconds=1.23)
    mock_cov = CoverageResult(available=True, total_percent=98.0, statements=434, missed=10)

    with patch("shipsafe.analyzer.test_analyzer.run_tests", return_value=(mock_test, mock_cov)), \
         patch("shipsafe.analyzer.git_analyzer.analyze") as mock_git_analyze, \
         patch("shipsafe.analyzer.git_analyzer.to_dict", return_value={
             "branch": "main",
             "head_commit": "ae6b3580b4bf",
             "is_clean": True,
             "diff_summary": {"files_changed": 0, "lines_added": 0, "lines_deleted": 0}
         }):
        snap = comparison.capture_snapshot("BASELINE")

    assert snap["state"] == "BASELINE"
    assert "captured_at" in snap
    assert snap["git"]["commit"] == "ae6b3580b4bf"
    assert snap["git"]["is_clean"] is True
    assert snap["git"]["files_changed"] == 0

    assert snap["tests"]["total"] == 38
    assert snap["tests"]["passed"] == 38
    assert snap["tests"]["failed"] == 0
    assert snap["tests"]["duration_seconds"] == 1.23

    assert snap["coverage"]["available"] is True
    assert snap["coverage"]["percent"] == 98.0
    assert snap["coverage"]["statements"] == 434
    assert snap["coverage"]["missed"] == 10

    assert snap["requirements"]["total"] == 5
    assert snap["requirements"]["passed"] == 5
    assert snap["requirements"]["failed"] == 0

    assert snap["findings"]["total"] == 0
    assert snap["findings"]["critical"] == 0
    assert snap["findings"]["high"] == 0
    assert snap["affected_files"] == 0


# ---------------------------------------------------------------------------
# 2. Bad Release Snapshot Structure
# ---------------------------------------------------------------------------

def test_bad_release_snapshot_structure():
    """Verify that a bad-release snapshot populates findings and requirements from report data."""
    mock_test = TestResult(command=[], exit_code=0, passed=True, total=31, passed_count=31, failed_count=0, skipped_count=0, error_count=0, duration_seconds=1.1)
    mock_cov = CoverageResult(available=True, total_percent=85.0, statements=420, missed=63)

    with patch("shipsafe.analyzer.test_analyzer.run_tests", return_value=(mock_test, mock_cov)), \
         patch("shipsafe.analyzer.git_analyzer.analyze"), \
         patch("shipsafe.analyzer.git_analyzer.to_dict", return_value={
             "branch": "main",
             "head_commit": "ae6b3580b4bf",
             "is_clean": False,
             "diff_summary": {"files_changed": 6, "lines_added": 12, "lines_deleted": 18}
         }):
        snap = comparison.capture_snapshot("BAD_RELEASE", release_report_data=SAMPLE_REPORT_DATA)

    assert snap["state"] == "BAD_RELEASE"
    assert snap["tests"]["total"] == 31
    assert snap["tests"]["passed"] == 31
    assert snap["findings"]["total"] == 4
    assert snap["findings"]["critical"] == 1
    assert snap["findings"]["high"] == 2
    assert snap["findings"]["medium"] == 1
    assert snap["requirements"]["total"] == 5
    assert snap["requirements"]["failed"] == 5
    assert snap["requirements"]["passed"] == 0
    assert snap["affected_files"] >= 3


# ---------------------------------------------------------------------------
# 3. Unavailable Post-Remediation State
# ---------------------------------------------------------------------------

def test_unavailable_post_remediation_state():
    """Verify that post-remediation before execution is represented explicitly as NOT_AVAILABLE."""
    snap = comparison.capture_snapshot("POST_REMEDIATION", is_available=False)
    assert snap["state"] == "POST_REMEDIATION"
    assert snap["status"] == "NOT_AVAILABLE"
    assert snap["tests"] is None
    assert snap["coverage"] is None
    assert snap["findings"] is None

    # Comparison when post-remediation is NOT_AVAILABLE
    dummy_baseline = {
        "state": "BASELINE",
        "captured_at": "2026-01-01T00:00:00Z",
        "git": {"commit": "abc", "branch": "main", "is_clean": True, "files_changed": 0, "lines_added": 0, "lines_deleted": 0},
        "tests": {"total": 38, "passed": 38, "failed": 0, "skipped": 0, "errors": 0, "duration_seconds": 1.0},
        "coverage": {"available": True, "percent": 98.0, "statements": 434, "missed": 10},
        "requirements": {"total": 5, "failed": 0, "passed": 5, "warning": 0, "unverifiable": 0},
        "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": 0},
        "affected_files": 0,
    }
    dummy_bad = {
        "state": "BAD_RELEASE",
        "captured_at": "2026-01-01T00:00:00Z",
        "git": {"commit": "abc", "branch": "main", "is_clean": False, "files_changed": 6, "lines_added": 10, "lines_deleted": 15},
        "tests": {"total": 31, "passed": 31, "failed": 0, "skipped": 0, "errors": 0, "duration_seconds": 1.0},
        "coverage": {"available": True, "percent": 84.5, "statements": 434, "missed": 67},
        "requirements": {"total": 5, "failed": 5, "passed": 0, "warning": 0, "unverifiable": 0},
        "findings": {"critical": 1, "high": 19, "medium": 2, "low": 0, "info": 0, "total": 22},
        "affected_files": 6,
    }

    comp = comparison.compare_snapshots(dummy_baseline, dummy_bad, snap)
    assert comp["post_remediation"]["status"] == "NOT_AVAILABLE"
    assert comp["comparisons"]["post_remediation_vs_bad_release"]["status"] == "NOT_AVAILABLE"
    assert comp["comparisons"]["post_remediation_vs_baseline"]["status"] == "NOT_AVAILABLE"

    # Flat metrics table shows post_remediation as None and remediation delta as None
    summary = comp["comparisons"]["metrics_summary"]
    assert summary["tests_passed"]["post_remediation"] is None
    assert summary["tests_passed"]["delta_remediation"] is None


# ---------------------------------------------------------------------------
# 4. Numeric Delta Calculation
# ---------------------------------------------------------------------------

def test_numeric_delta_calculation():
    """Verify numeric delta calculations for positive, negative, and zero differences."""
    assert comparison.calculate_delta(38, 31) == -7
    assert comparison.calculate_delta(0, 1) == 1
    assert comparison.calculate_delta(0, 22) == 22
    assert comparison.calculate_delta(98.0, 84.5) == -13.5
    assert comparison.calculate_delta(10, 10) == 0


# ---------------------------------------------------------------------------
# 5. Unavailable Values Are Not Treated as Zero
# ---------------------------------------------------------------------------

def test_unavailable_values_not_treated_as_zero():
    """Verify that None/unavailable metrics return None for delta, rather than treating None as 0."""
    assert comparison.calculate_delta(None, 31) is None
    assert comparison.calculate_delta(38, None) is None
    assert comparison.calculate_delta(None, None) is None
    # Booleans should not be coerced to 0 or 1
    assert comparison.calculate_delta(True, 1) is None
    assert comparison.calculate_delta(0, False) is None

    # In subdict comparison
    res = comparison._compare_subdict({"a": 10}, {"a": None}, ["a"])
    assert res["a"]["delta"] is None
    assert res["a"]["status"] == "UNAVAILABLE"

    res2 = comparison._compare_subdict({"a": None}, {"a": 20}, ["a"])
    assert res2["a"]["delta"] is None
    assert res2["a"]["status"] == "UNAVAILABLE"


# ---------------------------------------------------------------------------
# 6. Test Counts Come From Actual Execution Data
# ---------------------------------------------------------------------------

def test_counts_come_from_actual_execution_data():
    """Verify that test counts in captured snapshot reflect the pytest runner output exactly."""
    mock_test = TestResult(
        command=["pytest"],
        exit_code=0,
        passed=True,
        total=42,
        passed_count=40,
        failed_count=1,
        skipped_count=1,
        error_count=0,
        duration_seconds=3.45,
    )
    mock_cov = CoverageResult(available=False)

    with patch("shipsafe.analyzer.test_analyzer.run_tests", return_value=(mock_test, mock_cov)), \
         patch("shipsafe.analyzer.git_analyzer.analyze"), \
         patch("shipsafe.analyzer.git_analyzer.to_dict", return_value={"branch": "main", "head_commit": "c", "is_clean": True, "diff_summary": {}}):
        snap = comparison.capture_snapshot("BASELINE")

    assert snap["tests"]["total"] == 42
    assert snap["tests"]["passed"] == 40
    assert snap["tests"]["failed"] == 1
    assert snap["tests"]["skipped"] == 1
    assert snap["tests"]["duration_seconds"] == 3.45


# ---------------------------------------------------------------------------
# 7. Coverage Availability Represented Correctly
# ---------------------------------------------------------------------------

def test_coverage_availability_represented_correctly():
    """Verify coverage available flag and percent are populated when available and None when unavailable."""
    # When available
    mock_test = TestResult(command=[], exit_code=0, passed=True, total=10, passed_count=10, failed_count=0, skipped_count=0, error_count=0, duration_seconds=0.5)
    mock_cov_avail = CoverageResult(available=True, total_percent=92.5, statements=100, missed=8)

    with patch("shipsafe.analyzer.test_analyzer.run_tests", return_value=(mock_test, mock_cov_avail)), \
         patch("shipsafe.analyzer.git_analyzer.analyze"), \
         patch("shipsafe.analyzer.git_analyzer.to_dict", return_value={"branch": "main", "head_commit": "c", "is_clean": True, "diff_summary": {}}):
        snap1 = comparison.capture_snapshot("BASELINE")

    assert snap1["coverage"]["available"] is True
    assert snap1["coverage"]["percent"] == 92.5
    assert snap1["coverage"]["statements"] == 100
    assert snap1["coverage"]["missed"] == 8

    # When unavailable
    mock_cov_unavail = CoverageResult(available=False)
    with patch("shipsafe.analyzer.test_analyzer.run_tests", return_value=(mock_test, mock_cov_unavail)), \
         patch("shipsafe.analyzer.git_analyzer.analyze"), \
         patch("shipsafe.analyzer.git_analyzer.to_dict", return_value={"branch": "main", "head_commit": "c", "is_clean": True, "diff_summary": {}}):
        snap2 = comparison.capture_snapshot("BASELINE")

    assert snap2["coverage"]["available"] is False
    assert snap2["coverage"]["percent"] is None
    assert snap2["coverage"]["statements"] is None
    assert snap2["coverage"]["missed"] is None


# ---------------------------------------------------------------------------
# 8. Requirement Counts Come From Report Data
# ---------------------------------------------------------------------------

def test_requirement_counts_come_from_report_data():
    """Verify requirements counts (passed, failed, warning, unverifiable) come from report compliance array."""
    custom_report = {
        "requirement_compliance": [
            {"requirement_id": "R001", "status": "FAIL"},
            {"requirement_id": "R002", "status": "FAIL"},
            {"requirement_id": "R003", "status": "PASS"},
            {"requirement_id": "R004", "status": "WARNING"},
            {"requirement_id": "R005", "status": "UNVERIFIABLE"},
        ],
        "findings": [],
        "git": {},
    }
    req_dict, _, _ = comparison._extract_report_metrics(custom_report)
    assert req_dict["total"] == 5
    assert req_dict["failed"] == 2
    assert req_dict["passed"] == 1
    assert req_dict["warning"] == 1
    assert req_dict["unverifiable"] == 1


# ---------------------------------------------------------------------------
# 9. Severity Counts Come From Findings
# ---------------------------------------------------------------------------

def test_severity_counts_come_from_findings():
    """Verify finding severity counts are tallied directly from findings array."""
    custom_report = {
        "findings": [
            {"finding_id": "F1", "severity": "CRITICAL"},
            {"finding_id": "F2", "severity": "HIGH"},
            {"finding_id": "F3", "severity": "HIGH"},
            {"finding_id": "F4", "severity": "MEDIUM"},
            {"finding_id": "F5", "severity": "LOW"},
            {"finding_id": "F6", "severity": "INFO"},
        ],
        "requirement_compliance": [],
        "git": {},
    }
    _, find_dict, _ = comparison._extract_report_metrics(custom_report)
    assert find_dict["critical"] == 1
    assert find_dict["high"] == 2
    assert find_dict["medium"] == 1
    assert find_dict["low"] == 1
    assert find_dict["info"] == 1
    assert find_dict["total"] == 6


# ---------------------------------------------------------------------------
# 10. Comparison JSON Saves and Loads Correctly
# ---------------------------------------------------------------------------

def test_comparison_json_saves_loads_correctly(tmp_path: Path):
    """Verify comparison JSON serialization and deserialization roundtrip without loss."""
    dummy_baseline = {
        "state": "BASELINE",
        "captured_at": "2026-09-26T12:00:00Z",
        "git": {"commit": "5f95cd1", "branch": "main", "is_clean": True, "files_changed": 0, "lines_added": 0, "lines_deleted": 0},
        "tests": {"total": 38, "passed": 38, "failed": 0, "skipped": 0, "errors": 0, "duration_seconds": 1.5},
        "coverage": {"available": True, "percent": 98.0, "statements": 434, "missed": 10},
        "requirements": {"total": 5, "failed": 0, "passed": 5, "warning": 0, "unverifiable": 0},
        "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": 0},
        "affected_files": 0,
    }
    dummy_bad = {
        "state": "BAD_RELEASE",
        "captured_at": "2026-09-26T12:05:00Z",
        "git": {"commit": "5f95cd1", "branch": "main", "is_clean": False, "files_changed": 6, "lines_added": 12, "lines_deleted": 18},
        "tests": {"total": 31, "passed": 31, "failed": 0, "skipped": 0, "errors": 0, "duration_seconds": 1.2},
        "coverage": {"available": True, "percent": 84.5, "statements": 434, "missed": 67},
        "requirements": {"total": 5, "failed": 5, "passed": 0, "warning": 0, "unverifiable": 0},
        "findings": {"critical": 1, "high": 19, "medium": 2, "low": 0, "info": 0, "total": 22},
        "affected_files": 6,
    }

    comp = comparison.compare_snapshots(dummy_baseline, dummy_bad)
    out_file = tmp_path / "test_comp.json"
    saved_path = comparison.save_comparison(comp, str(out_file))

    assert Path(saved_path).exists()
    loaded = comparison.load_comparison(str(out_file))
    assert loaded["baseline"]["state"] == "BASELINE"
    assert loaded["bad_release"]["state"] == "BAD_RELEASE"
    assert loaded["post_remediation"]["status"] == "NOT_AVAILABLE"
    assert loaded["comparisons"]["bad_release_vs_baseline"]["tests"]["passed"]["delta"] == -7
    assert loaded == comp


# ---------------------------------------------------------------------------
# 11. Malformed Snapshot Fails Clearly
# ---------------------------------------------------------------------------

def test_malformed_snapshot_fails_clearly():
    """Verify that malformed snapshot structures raise descriptive ValueError exceptions."""
    with pytest.raises(ValueError, match="must be a dict"):
        comparison.validate_snapshot("not a dict")

    with pytest.raises(ValueError, match="missing required field: 'state'"):
        comparison.validate_snapshot({"foo": "bar"})

    with pytest.raises(ValueError, match="Invalid snapshot state"):
        comparison.validate_snapshot({"state": "NON_EXISTENT"})

    with pytest.raises(ValueError, match="missing required section: 'tests'"):
        comparison.validate_snapshot({
            "state": "BASELINE",
            "git": {},
            "coverage": {},
            "requirements": {},
            "findings": {},
        })

    with pytest.raises(ValueError, match="section 'tests' must be a dict or None"):
        comparison.validate_snapshot({
            "state": "BASELINE",
            "git": {},
            "tests": "not a dict",
            "coverage": {},
            "requirements": {},
            "findings": {},
        })
