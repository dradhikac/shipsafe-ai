"""Tests for shipsafe.analyzer.metrics.

Verifies:
- Metrics structure is valid and has expected fields
- No placeholder values are introduced
- Metrics can be serialised to JSON
- validate_no_placeholders catches suspicious values
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from shipsafe.analyzer import metrics as metrics_module
from shipsafe.analyzer.metrics import Metrics, validate_no_placeholders, to_dict


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_metrics_dataclass_exists():
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    assert isinstance(m, Metrics)


def test_metrics_has_timestamp():
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    assert m.timestamp == "2025-01-01T00:00:00+00:00"


def test_metrics_defaults_are_none_or_false():
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    assert m.git_branch is None
    assert m.git_commit is None
    assert m.tests_total is None
    assert m.tests_passed is None
    assert m.coverage_available is False
    assert m.coverage_percent is None


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def test_to_dict_returns_dict():
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    d = to_dict(m)
    assert isinstance(d, dict)


def test_to_dict_has_all_expected_keys():
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    d = to_dict(m)
    for key in ("timestamp", "git_branch", "git_commit", "is_clean",
                "files_changed", "lines_added", "lines_deleted",
                "tests_total", "tests_passed", "tests_failed",
                "tests_skipped", "tests_errors", "test_duration_seconds",
                "coverage_available", "coverage_percent",
                "coverage_statements", "coverage_missed"):
        assert key in d, f"Missing key in to_dict output: {key}"


def test_to_dict_is_json_serialisable():
    m = Metrics(
        timestamp="2025-01-01T00:00:00+00:00",
        git_branch="main",
        tests_total=38,
        tests_passed=38,
        tests_failed=0,
        coverage_available=True,
        coverage_percent=98.0,
    )
    serialised = json.dumps(to_dict(m))
    assert isinstance(serialised, str)


# ---------------------------------------------------------------------------
# validate_no_placeholders
# ---------------------------------------------------------------------------

def test_validate_no_placeholders_clean_metrics():
    m = Metrics(
        timestamp="2025-01-01T00:00:00+00:00",
        git_branch="main",
        tests_total=38,
        tests_passed=38,
        tests_failed=0,
        coverage_available=True,
        coverage_percent=98.0,
        coverage_statements=434,
    )
    warnings = validate_no_placeholders(m)
    assert warnings == []


def test_validate_no_placeholders_detects_suspicious_int():
    m = Metrics(
        timestamp="2025-01-01T00:00:00+00:00",
        tests_total=999,   # suspicious sentinel
    )
    warnings = validate_no_placeholders(m)
    assert any("tests_total" in w for w in warnings)


def test_validate_no_placeholders_detects_zero_coverage():
    m = Metrics(
        timestamp="2025-01-01T00:00:00+00:00",
        coverage_percent=0.0,
    )
    warnings = validate_no_placeholders(m)
    assert any("coverage_percent" in w for w in warnings)


def test_validate_no_placeholders_allows_none():
    """None values are acceptable — they mean not measured."""
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    warnings = validate_no_placeholders(m)
    assert warnings == []


# ---------------------------------------------------------------------------
# No placeholder values policy
# ---------------------------------------------------------------------------

def test_metrics_never_has_minus_one_default():
    """Ensure no field defaults to -1 (a common placeholder sentinel)."""
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    d = to_dict(m)
    for key, value in d.items():
        assert value != -1, (
            f"Field '{key}' has placeholder value -1."
        )


def test_metrics_never_has_9999_default():
    m = Metrics(timestamp="2025-01-01T00:00:00+00:00")
    d = to_dict(m)
    for key, value in d.items():
        assert value != 9999, (
            f"Field '{key}' has placeholder value 9999."
        )


# ---------------------------------------------------------------------------
# Timestamp format
# ---------------------------------------------------------------------------

def test_timestamp_is_iso_format():
    ts = datetime.now(tz=timezone.utc).isoformat()
    m = Metrics(timestamp=ts)
    # Should be parseable by datetime.fromisoformat (Python 3.7+)
    parsed = datetime.fromisoformat(m.timestamp)
    assert parsed is not None
