"""Tests for shipsafe.analyzer.report_builder.

Verifies:
- empty report is structurally valid
- findings can be added
- duplicate IDs are detected loudly
- JSON can be saved and loaded round-trip
- CONFIRMED finding without evidence is rejected
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from shipsafe.analyzer import report_builder
from shipsafe.analyzer.report_builder import (
    ReportError,
    DuplicateFindingError,
    create_empty,
    add_finding,
    validate,
    save,
    load,
    merge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_finding(finding_id: str = "TEST-001",
                     status: str = "INFORMATIONAL",
                     severity: str = "INFO") -> dict:
    return {
        "finding_id": finding_id,
        "severity": severity,
        "finding_status": status,
        "title": "Test finding",
        "description": "A test finding.",
        "source_agent": "test",
        "affected_files": [],
        "evidence": [],
        "requirement_id": None,
        "recommended_action": "None",
    }


def _confirmed_finding_with_evidence(finding_id: str = "TEST-002") -> dict:
    return {
        "finding_id": finding_id,
        "severity": "HIGH",
        "finding_status": "CONFIRMED",
        "title": "Confirmed finding with evidence",
        "description": "Has evidence.",
        "source_agent": "test",
        "affected_files": ["some/file.py"],
        "evidence": [
            {
                "evidence_type": "CODE",
                "description": "Dangerous pattern in file.",
                "file_path": "some/file.py",
                "is_concrete": True,
            }
        ],
        "requirement_id": "R001",
        "recommended_action": "Fix it.",
    }


# ---------------------------------------------------------------------------
# Empty report
# ---------------------------------------------------------------------------

def test_create_empty_returns_dict():
    report = create_empty()
    assert isinstance(report, dict)


def test_create_empty_has_required_fields():
    report = create_empty()
    for field in ("report_type", "generated_at", "status",
                  "summary", "findings", "metrics"):
        assert field in report, f"Missing field: {field}"


def test_create_empty_findings_is_empty_list():
    report = create_empty()
    assert report["findings"] == []


def test_create_empty_status_is_analysis_only():
    report = create_empty()
    assert report["status"] == "ANALYSIS_ONLY"


def test_create_empty_is_valid():
    report = create_empty()
    errors = validate(report)
    assert errors == [], f"Unexpected validation errors: {errors}"


def test_create_empty_invalid_status_raises():
    with pytest.raises(ReportError, match="Invalid status"):
        create_empty(status="INVALID_STATUS")


# ---------------------------------------------------------------------------
# Adding findings
# ---------------------------------------------------------------------------

def test_add_informational_finding_succeeds():
    report = create_empty()
    add_finding(report, _minimal_finding())
    assert len(report["findings"]) == 1


def test_add_finding_updates_summary_count():
    report = create_empty()
    add_finding(report, _minimal_finding(severity="HIGH", status="WARNING",
                                          finding_id="TEST-HIGH"))
    assert report["summary"]["high_count"] == 1
    assert report["summary"]["total_findings"] == 1


def test_add_finding_with_evidence():
    report = create_empty()
    add_finding(report, _confirmed_finding_with_evidence())
    assert len(report["findings"]) == 1


# ---------------------------------------------------------------------------
# Duplicate IDs
# ---------------------------------------------------------------------------

def test_duplicate_finding_id_raises():
    report = create_empty()
    add_finding(report, _minimal_finding("DUPE-001"))
    with pytest.raises(DuplicateFindingError, match="DUPE-001"):
        add_finding(report, _minimal_finding("DUPE-001"))


def test_duplicate_id_does_not_add_finding():
    report = create_empty()
    add_finding(report, _minimal_finding("DUPE-002"))
    try:
        add_finding(report, _minimal_finding("DUPE-002"))
    except DuplicateFindingError:
        pass
    assert len(report["findings"]) == 1


# ---------------------------------------------------------------------------
# CONFIRMED finding without evidence is rejected
# ---------------------------------------------------------------------------

def test_confirmed_finding_without_evidence_raises():
    report = create_empty()
    confirmed_no_evidence = _minimal_finding(status="CONFIRMED",
                                              severity="CRITICAL",
                                              finding_id="CONF-001")
    confirmed_no_evidence["evidence"] = []
    with pytest.raises(ReportError, match="CONFIRMED"):
        add_finding(report, confirmed_no_evidence)


def test_confirmed_finding_with_evidence_is_accepted():
    report = create_empty()
    add_finding(report, _confirmed_finding_with_evidence("CONF-002"))
    assert len(report["findings"]) == 1


# ---------------------------------------------------------------------------
# Invalid severity / finding_status
# ---------------------------------------------------------------------------

def test_invalid_severity_raises():
    report = create_empty()
    bad = _minimal_finding()
    bad["severity"] = "CATASTROPHIC"
    with pytest.raises(ReportError, match="severity"):
        add_finding(report, bad)


def test_invalid_finding_status_raises():
    report = create_empty()
    bad = _minimal_finding()
    bad["finding_status"] = "MAYBE"
    with pytest.raises(ReportError, match="finding_status"):
        add_finding(report, bad)


# ---------------------------------------------------------------------------
# JSON save / load round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_round_trip(tmp_path):
    report = create_empty()
    add_finding(report, _confirmed_finding_with_evidence())
    path = str(tmp_path / "test_report.json")
    save(report, path)
    loaded = load(path)
    assert loaded["findings"][0]["finding_id"] == "TEST-002"


def test_save_creates_parent_directories(tmp_path):
    report = create_empty()
    nested = str(tmp_path / "sub" / "dir" / "report.json")
    save(report, nested)
    assert Path(nested).exists()


def test_load_nonexistent_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(str(tmp_path / "nonexistent.json"))


def test_load_invalid_json_raises(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load(str(bad_file))


def test_saved_file_is_valid_json(tmp_path):
    report = create_empty()
    path = str(tmp_path / "report.json")
    save(report, path)
    text = Path(path).read_text(encoding="utf-8")
    parsed = json.loads(text)
    assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def test_merge_empty_fragments_returns_copy():
    base = create_empty()
    merged = merge(base)
    assert merged["findings"] == []


def test_merge_adds_findings_from_fragment():
    base = create_empty()
    fragment = create_empty()
    add_finding(fragment, _minimal_finding("MERGE-001"))
    merged = merge(base, fragment)
    assert len(merged["findings"]) == 1


def test_merge_identical_finding_is_idempotent():
    base = create_empty()
    add_finding(base, _minimal_finding("SAME-001"))
    fragment = create_empty()
    add_finding(fragment, _minimal_finding("SAME-001"))
    # Same content — should not raise
    merged = merge(base, fragment)
    assert len(merged["findings"]) == 1


def test_merge_conflicting_finding_raises():
    base = create_empty()
    add_finding(base, _minimal_finding("CONFLICT-001"))
    fragment = create_empty()
    different = _minimal_finding("CONFLICT-001")
    different["title"] = "Different title"
    add_finding(fragment, different)
    with pytest.raises(DuplicateFindingError, match="CONFLICT-001"):
        merge(base, fragment)


def test_merge_does_not_mutate_base():
    base = create_empty()
    fragment = create_empty()
    add_finding(fragment, _minimal_finding("MUTATE-001"))
    merge(base, fragment)
    assert len(base["findings"]) == 0
