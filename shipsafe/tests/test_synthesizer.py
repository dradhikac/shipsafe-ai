"""Tests for shipsafe.analyzer.synthesizer.

Verifies:
1. All five historical Bob reports load.
2. source_agent values are validated.
3. Actual findings arrays determine counts (not stale metadata).
4. Contract evidence normalization works (dict-form to list-form).
5. remediation -> recommended_action normalization works.
6. Confirmed findings require concrete evidence.
7. Consolidated findings preserve original finding IDs.
8. R001 compliance is computed (FAIL).
9. R002 compliance is computed (FAIL).
10. R003 conflict between database and contract/impact is preserved.
11. R004 compliance is computed (FAIL).
12. R005 compliance is computed (FAIL).
13. Release status is derived from evidence (RELEASE_BLOCKED).
14. Synthesized report JSON can be saved and loaded round-trip.
15. Malformed reports fail clearly with SynthesizerError.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from shipsafe.analyzer import synthesizer
from shipsafe.analyzer.synthesizer import (
    SynthesizerError,
    load_agent_reports,
    normalize_finding,
    validate_normalized_finding,
    consolidate_findings,
    detect_conflicts,
    compute_requirement_compliance,
    compute_summary_and_status,
    synthesize_release,
)


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the repository root."""
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Test 1: Load all 5 Bob reports
# ---------------------------------------------------------------------------

def test_load_all_five_reports(repo_root: Path) -> None:
    reports = load_agent_reports(repo_root)
    assert len(reports) == 5
    assert set(reports.keys()) == {"impact", "test_gap", "security", "contract", "database"}
    for agent, rep in reports.items():
        assert rep["source_agent"] == agent
        assert "findings" in rep
        assert isinstance(rep["findings"], list)


# ---------------------------------------------------------------------------
# Test 2: source_agent validation
# ---------------------------------------------------------------------------

def test_source_agent_validation(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports" / "agents"
    reports_dir.mkdir(parents=True)

    # Valid impact report
    valid_data = {"source_agent": "impact", "findings": []}
    (reports_dir / "impact_report.json").write_text(json.dumps(valid_data), encoding="utf-8")

    # Corrupt database report with wrong agent
    wrong_data = {"source_agent": "wrong_agent", "findings": []}
    (reports_dir / "database_report.json").write_text(json.dumps(wrong_data), encoding="utf-8")

    custom_map = {
        "impact": "reports/agents/impact_report.json",
        "database": "reports/agents/database_report.json",
    }
    with pytest.raises(SynthesizerError, match="invalid source_agent"):
        load_agent_reports(tmp_path, agent_map=custom_map)


# ---------------------------------------------------------------------------
# Test 3: Actual findings array determines counts
# ---------------------------------------------------------------------------

def test_authoritative_findings_counts(repo_root: Path) -> None:
    reports = load_agent_reports(repo_root)
    impact_rep = reports["impact"]

    # In impact report, summary metadata claimed 7, but findings array has 8
    claimed = impact_rep.get("summary", {}).get("total_findings")
    actual = len(impact_rep["findings"])
    assert actual == 8
    # When synthesized, total count is derived from actual findings (22 total)
    synth = synthesize_release(repo_root, output_path=None, verify_live_repo=False)
    assert synth["summary"]["total_findings"] == 22
    assert synth["summary"]["high_count"] == 19
    assert synth["summary"]["critical_count"] == 1
    assert synth["summary"]["medium_count"] == 2


# ---------------------------------------------------------------------------
# Test 4: Contract evidence normalization (dict-form to list-form)
# ---------------------------------------------------------------------------

def test_contract_evidence_normalization() -> None:
    notes: list[str] = []
    raw_finding = {
        "finding_id": "CONTRACT-R001",
        "severity": "HIGH",
        "finding_status": "CONFIRMED",
        "title": "Guard check failure",
        "description": "Guard does not block cancelled appointments.",
        "evidence": {
            "file": "demo_target/services/notification_service.py",
            "symbol": "send_reminder",
            "lines": "25-29",
            "code_snippet": "if row['status'] == 'completed': ...",
            "analysis": "Guard checks only completed.",
        },
        "requirement_id": "R001",
        "recommended_action": "Restore cancelled check.",
    }
    norm = normalize_finding(raw_finding, "contract", notes)
    assert isinstance(norm["evidence"], list)
    assert len(norm["evidence"]) == 1
    ev = norm["evidence"][0]
    assert ev["file_path"] == "demo_target/services/notification_service.py"
    assert ev["line_start"] == 25
    assert ev["line_end"] == 29
    assert ev["symbol"] == "send_reminder"
    assert ev["is_concrete"] is True


def test_contract_multi_file_evidence_normalization() -> None:
    notes: list[str] = []
    raw_finding = {
        "finding_id": "CONTRACT-R003",
        "severity": "HIGH",
        "finding_status": "CONFIRMED",
        "title": "Multi file finding",
        "evidence": {
            "file_1": "demo_target/db.py",
            "lines_1": "48-49",
            "symbol_1": "SCHEMA",
            "file_2": "demo_target/models.py",
            "lines_2": "41",
            "symbol_2": "VALID_PRIORITIES",
            "analysis": "Discrepancy found.",
        },
        "requirement_id": "R003",
        "recommended_action": "Align models.",
    }
    norm = normalize_finding(raw_finding, "contract", notes)
    assert isinstance(norm["evidence"], list)
    assert len(norm["evidence"]) == 2
    assert norm["evidence"][0]["file_path"] == "demo_target/db.py"
    assert norm["evidence"][0]["line_start"] == 48
    assert norm["evidence"][0]["line_end"] == 49
    assert norm["evidence"][1]["file_path"] == "demo_target/models.py"


# ---------------------------------------------------------------------------
# Test 5: remediation -> recommended_action normalization
# ---------------------------------------------------------------------------

def test_remediation_field_normalization() -> None:
    notes: list[str] = []
    raw_finding = {
        "finding_id": "SECURITY-001",
        "severity": "CRITICAL",
        "finding_status": "CONFIRMED",
        "title": "SQLi",
        "description": "SQL injection.",
        "remediation": "Use parameterized queries.",
        "evidence": [
            {
                "evidence_type": "CODE",
                "file_path": "demo_target/routes/appointments.py",
                "start_line": 74,
                "end_line": 77,
                "description": "Raw string concatenation",
            }
        ],
        "requirement_id": "R004",
    }
    norm = normalize_finding(raw_finding, "security", notes)
    assert norm["recommended_action"] == "Use parameterized queries."
    assert norm["evidence"][0]["line_start"] == 74
    assert norm["evidence"][0]["line_end"] == 77
    assert any("remediation" in n for n in notes)


# ---------------------------------------------------------------------------
# Test 6: Confirmed findings require evidence
# ---------------------------------------------------------------------------

def test_confirmed_finding_requires_evidence() -> None:
    invalid_finding = {
        "finding_id": "FAKE-001",
        "severity": "HIGH",
        "finding_status": "CONFIRMED",
        "title": "Fake finding",
        "source_agent": "impact",
        "evidence": [],
    }
    with pytest.raises(SynthesizerError, match="contains no evidence"):
        validate_normalized_finding(invalid_finding)


# ---------------------------------------------------------------------------
# Test 7: Consolidated findings preserve original IDs
# ---------------------------------------------------------------------------

def test_consolidate_findings_preserves_source_ids(repo_root: Path) -> None:
    synth = synthesize_release(repo_root, output_path=None, verify_live_repo=False)
    consolidated = synth["consolidated_findings"]
    assert len(consolidated) == 5

    syn_r001 = next(c for c in consolidated if c["finding_id"] == "SYN-R001")
    assert syn_r001["requirement_id"] == "R001"
    assert "IMPACT-001" in syn_r001["supporting_findings"]
    assert "CONTRACT-R001" in syn_r001["supporting_findings"]
    assert "TESTGAP-001" in syn_r001["supporting_findings"]
    assert set(syn_r001["source_agents"]) == {"contract", "impact", "test_gap"}

    # Underling Bob findings still exist
    all_fids = {f["finding_id"] for f in synth["findings"]}
    assert "IMPACT-001" in all_fids
    assert "CONTRACT-R001" in all_fids
    assert "SECURITY-001" in all_fids


# ---------------------------------------------------------------------------
# Tests 8-12: Requirement compliance computation (R001-R005)
# ---------------------------------------------------------------------------

def test_requirement_compliance_computation(repo_root: Path) -> None:
    synth = synthesize_release(repo_root, output_path=None, verify_live_repo=False)
    comp = {c["requirement_id"]: c for c in synth["requirement_compliance"]}

    assert set(comp.keys()) == {"R001", "R002", "R003", "R004", "R005"}

    # All five requirements fail due to concrete confirmed violations
    assert comp["R001"]["status"] == "FAIL"
    assert "IMPACT-001" in comp["R001"]["supporting_findings"]

    assert comp["R002"]["status"] == "FAIL"
    assert "IMPACT-002" in comp["R002"]["supporting_findings"]

    assert comp["R003"]["status"] == "FAIL"
    assert "DATABASE-001" in comp["R003"]["supporting_findings"]

    assert comp["R004"]["status"] == "FAIL"
    assert "SECURITY-001" in comp["R004"]["supporting_findings"]
    assert comp["R004"]["severity"] == "CRITICAL"

    assert comp["R005"]["status"] == "FAIL"
    assert "TESTGAP-007" in comp["R005"]["supporting_findings"]


# ---------------------------------------------------------------------------
# Test 10: R003 conflict preservation
# ---------------------------------------------------------------------------

def test_r003_conflict_preserved(repo_root: Path) -> None:
    synth = synthesize_release(repo_root, output_path=None, verify_live_repo=False)
    conflicts = synth["conflicts"]
    assert len(conflicts) >= 1

    r003_conflict = next(c for c in conflicts if c["requirement_id"] == "R003")
    assert r003_conflict["type"] == "AGENT_RECOMMENDATION_CONFLICT"
    assert set(r003_conflict["agents"]) == {"database", "contract", "impact"}
    assert len(r003_conflict["evidence"]) == 5
    # Check that recommendations from each agent are captured
    agents_in_ev = {item["source_agent"] for item in r003_conflict["evidence"]}
    assert agents_in_ev == {"database", "contract", "impact"}


# ---------------------------------------------------------------------------
# Test 13: Release status is evidence-derived
# ---------------------------------------------------------------------------

def test_release_status_is_blocked(repo_root: Path) -> None:
    synth = synthesize_release(repo_root, output_path=None, verify_live_repo=False)
    assert synth["status"] == "RELEASE_BLOCKED"


# ---------------------------------------------------------------------------
# Test 14: Save and load round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_round_trip(repo_root: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "latest_release_report.json"
    synth = synthesize_release(repo_root, output_path=str(out_file), verify_live_repo=False)
    assert out_file.is_file()

    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["report_type"] == "release_synthesis"
    assert loaded["status"] == "RELEASE_BLOCKED"
    assert len(loaded["findings"]) == 22
    assert len(loaded["consolidated_findings"]) == 5
    assert len(loaded["conflicts"]) == 1


# ---------------------------------------------------------------------------
# Test 15: Malformed report failure
# ---------------------------------------------------------------------------

def test_malformed_report_failure(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")

    custom_map = {
        "impact": "bad.json",
        "test_gap": "bad.json",
        "security": "bad.json",
        "contract": "bad.json",
        "database": "bad.json",
    }
    with pytest.raises(SynthesizerError, match="not valid JSON"):
        load_agent_reports(tmp_path, agent_map=custom_map)
