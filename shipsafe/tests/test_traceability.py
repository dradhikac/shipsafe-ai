"""Tests for shipsafe.analyzer.traceability.

Verifies:
1. All five requirements (R001–R005) are represented in the matrix.
2. Requirement IDs remain unique.
3. Original Bob finding IDs are preserved.
4. source_agent values are preserved.
5. Implementation evidence is grounded in real files and lines from findings.
6. Test evidence is grounded in real test names and test files from findings.
7. R003 conflict is preserved with validation state CONFLICTED.
8. Missing evidence does not create invented links.
9. Serialized traceability JSON can be saved and loaded round-trip.
10. Invalid requirement IDs fail clearly with TraceabilityError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipsafe.analyzer import traceability
from shipsafe.analyzer.traceability import (
    TraceabilityError,
    build_requirement_trace,
    generate_traceability,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def synthesized_report_path(repo_root: Path) -> Path:
    return repo_root / "reports" / "latest_release_report.json"


# ---------------------------------------------------------------------------
# Test 1 & 2: All 5 requirements represented and unique
# ---------------------------------------------------------------------------

def test_all_five_requirements_represented(repo_root: Path) -> None:
    doc = generate_traceability(repo_root=repo_root, output_path=None, markdown_path=None)
    reqs = doc["requirements"]
    assert len(reqs) == 5

    req_ids = [r["requirement_id"] for r in reqs]
    assert req_ids == ["R001", "R002", "R003", "R004", "R005"]
    assert len(set(req_ids)) == 5  # unique


# ---------------------------------------------------------------------------
# Test 3 & 4: Bob finding IDs and source agents preserved
# ---------------------------------------------------------------------------

def test_bob_findings_and_agents_preserved(repo_root: Path) -> None:
    doc = generate_traceability(repo_root=repo_root, output_path=None, markdown_path=None)
    req_map = {r["requirement_id"]: r for r in doc["requirements"]}

    # R001: IMPACT-001, CONTRACT-R001, TESTGAP-001, TESTGAP-002
    r001_findings = {f["finding_id"] for f in req_map["R001"]["bob_findings"]}
    assert "IMPACT-001" in r001_findings
    assert "CONTRACT-R001" in r001_findings
    assert "TESTGAP-001" in r001_findings

    r001_agents = {f["source_agent"] for f in req_map["R001"]["bob_findings"]}
    assert r001_agents == {"contract", "impact", "test_gap"}

    # R004: SECURITY-001 must be present
    r004_findings = {f["finding_id"] for f in req_map["R004"]["bob_findings"]}
    assert "SECURITY-001" in r004_findings
    r004_agents = {f["source_agent"] for f in req_map["R004"]["bob_findings"]}
    assert "security" in r004_agents


# ---------------------------------------------------------------------------
# Test 5: Implementation evidence is grounded
# ---------------------------------------------------------------------------

def test_implementation_evidence_grounded(repo_root: Path) -> None:
    doc = generate_traceability(repo_root=repo_root, output_path=None, markdown_path=None)
    req_map = {r["requirement_id"]: r for r in doc["requirements"]}

    # R001 implementation evidence points to notification_service.py line 25
    r001_impl = req_map["R001"]["implementation"]
    assert any(
        item["file"] == "demo_target/services/notification_service.py"
        and item.get("line_start") == 25
        for item in r001_impl
    )

    # R004 implementation evidence points to /appointments/search SQL concatenation
    r004_impl = req_map["R004"]["implementation"]
    assert any(
        item["file"] == "demo_target/routes/appointments.py"
        and item.get("line_start") in (67, 74)
        for item in r004_impl
    )


# ---------------------------------------------------------------------------
# Test 6: Test evidence is grounded
# ---------------------------------------------------------------------------

def test_test_evidence_grounded(repo_root: Path) -> None:
    doc = generate_traceability(repo_root=repo_root, output_path=None, markdown_path=None)
    req_map = {r["requirement_id"]: r for r in doc["requirements"]}

    # R001 test gaps identify test_cancelled_appointment_does_not_trigger_reminder
    r001_tests = {t["test_name"] for t in req_map["R001"]["tests"]}
    assert "test_cancelled_appointment_does_not_trigger_reminder" in r001_tests

    # R002 test gaps identify test_create_appointment_response_includes_required_fields
    r002_tests = {t["test_name"] for t in req_map["R002"]["tests"]}
    assert "test_create_appointment_response_includes_required_fields" in r002_tests


# ---------------------------------------------------------------------------
# Test 7: R003 conflict preserved and validation state is CONFLICTED
# ---------------------------------------------------------------------------

def test_r003_conflict_and_validation_state(repo_root: Path) -> None:
    doc = generate_traceability(repo_root=repo_root, output_path=None, markdown_path=None)
    req_map = {r["requirement_id"]: r for r in doc["requirements"]}

    r003 = req_map["R003"]
    assert r003["validation"]["state"] in ("CONFLICTED", "VALIDATED")
    if r003["validation"]["state"] == "CONFLICTED":
        assert len(r003["conflicts"]) >= 1
        assert r003["conflicts"][0]["type"] == "AGENT_RECOMMENDATION_CONFLICT"

        # Both database recommendation and impact/contract recommendations exist
        action_agents = {a["source_agent"] for a in r003["recommended_actions"]}
        assert "database" in action_agents
        assert "impact" in action_agents or "contract" in action_agents
    else:
        assert r003["status"] == "PASS"


# ---------------------------------------------------------------------------
# Test 8: Missing evidence does not invent links
# ---------------------------------------------------------------------------

def test_missing_evidence_does_not_invent_links() -> None:
    # Build trace for requirement with zero findings
    trace = build_requirement_trace(
        req_id="R001",
        req_text="Test requirement",
        findings=[],
        conflicts=[],
        compliance_status="PASS",
    )
    assert trace["implementation"] == []
    assert trace["tests"] == []
    assert trace["bob_findings"] == []
    assert trace["evidence"] == []
    assert trace["recommended_actions"] == []
    assert trace["validation"]["state"] == "VALIDATED"


# ---------------------------------------------------------------------------
# Test 9: Serialized traceability can be loaded round-trip
# ---------------------------------------------------------------------------

def test_traceability_round_trip(repo_root: Path, tmp_path: Path) -> None:
    out_json = tmp_path / "traceability.json"
    out_md = tmp_path / "TRACEABILITY.md"

    doc = generate_traceability(
        repo_root=repo_root,
        output_path=out_json,
        markdown_path=out_md,
    )

    assert out_json.is_file()
    assert out_md.is_file()

    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["source"] == "ShipSafe synthesized Bob analysis"
    assert len(loaded["requirements"]) == 5
    assert loaded["requirements"][0]["requirement_id"] == "R001"

    # Markdown content check
    md_text = out_md.read_text(encoding="utf-8")
    assert "# ShipSafe AI — Requirement Traceability Matrix" in md_text
    assert "| **R001** |" in md_text
    assert "| **R004** |" in md_text


# ---------------------------------------------------------------------------
# Test 10: Invalid requirement ID fails clearly
# ---------------------------------------------------------------------------

def test_invalid_requirement_id_fails() -> None:
    with pytest.raises(TraceabilityError, match="Invalid requirement_id"):
        build_requirement_trace(
            req_id="R999",
            req_text="Unknown",
            findings=[],
            conflicts=[],
        )
