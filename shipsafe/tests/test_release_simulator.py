"""Tests for shipsafe.analyzer.release_simulator.

Verifies:
1. Report inputs load correctly.
2. Affected components are grounded in evidence.
3. Affected workflows are grounded in evidence.
4. Regression paths preserve requirement IDs (R001–R005).
5. No unsupported workflow is created.
6. Highest-risk component selection is deterministic (Appointment Search / SQL injection).
7. Required actions derive from findings.
8. No probabilistic scores are generated (transparent metric counts only).
9. Simulation JSON and Markdown artifacts can be saved and loaded.
10. Missing input reports fail clearly with SimulationError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipsafe.analyzer import release_simulator
from shipsafe.analyzer.release_simulator import (
    SimulationError,
    identify_affected_components,
    derive_affected_workflows,
    construct_regression_paths,
    select_highest_risk_component,
    derive_required_actions,
    simulate_release_impact,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Test 1 & 9: Report loading & round-trip persistence
# ---------------------------------------------------------------------------

def test_simulate_release_impact_loads_and_saves(repo_root: Path, tmp_path: Path) -> None:
    out_json = tmp_path / "release_simulation.json"
    out_md = tmp_path / "RELEASE_IMPACT_SIMULATION.md"

    sim = simulate_release_impact(
        repo_root=repo_root,
        output_path=out_json,
        markdown_path=out_md,
    )

    assert sim["simulation_type"] == "evidence_based_release_impact"
    assert sim["release_status"] == "RELEASE_BLOCKED"
    assert out_json.is_file()
    assert out_md.is_file()

    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["simulation_type"] == "evidence_based_release_impact"
    assert loaded["metrics"]["affected_components"] == len(sim["affected_components"])
    assert loaded["metrics"]["affected_workflows"] == len(sim["affected_workflows"])


# ---------------------------------------------------------------------------
# Test 2: Affected components are evidence-backed
# ---------------------------------------------------------------------------

def test_affected_components_are_evidence_backed(repo_root: Path) -> None:
    sim = simulate_release_impact(repo_root=repo_root, output_path=None, markdown_path=None)
    comps = sim["affected_components"]
    assert len(comps) >= 5

    comp_names = {c["component_name"] for c in comps}
    assert "Appointment Search & Query Path" in comp_names
    assert "Notification Service" in comp_names
    assert "Domain Models & Serialization" in comp_names
    assert "Database Schema & Migrations" in comp_names
    assert "Regression Test Harness" in comp_names

    # Check evidence grounding
    for c in comps:
        assert len(c["related_findings"]) > 0
        assert len(c["supporting_agents"]) > 0


# ---------------------------------------------------------------------------
# Test 3 & 5: Affected workflows are evidence-backed; no unsupported workflows
# ---------------------------------------------------------------------------

def test_affected_workflows_evidence_backed(repo_root: Path) -> None:
    sim = simulate_release_impact(repo_root=repo_root, output_path=None, markdown_path=None)
    wfs = sim["affected_workflows"]
    assert len(wfs) == 6

    wf_ids = {w["workflow_id"] for w in wfs}
    assert "WF-REMINDER" in wf_ids
    assert "WF-API-SERIALIZATION" in wf_ids
    assert "WF-PRIORITY-PERSISTENCE" in wf_ids
    assert "WF-SEARCH" in wf_ids
    assert "WF-CANCELLATION" in wf_ids
    assert "WF-REGRESSION-HARNESS" in wf_ids

    # Every workflow has confirmed findings
    for w in wfs:
        assert len(w["findings"]) > 0
        assert w["status"] == "AFFECTED"


# ---------------------------------------------------------------------------
# Test 4: Regression paths preserve requirement IDs
# ---------------------------------------------------------------------------

def test_regression_paths_preserve_requirement_ids(repo_root: Path) -> None:
    sim = simulate_release_impact(repo_root=repo_root, output_path=None, markdown_path=None)
    paths = sim["regression_paths"]
    assert len(paths) == 5

    req_ids_in_paths = {p["requirement_id"] for p in paths}
    assert req_ids_in_paths == {"R001", "R002", "R003", "R004", "R005"}

    for p in paths:
        assert len(p["chain"]) >= 3
        assert len(p["supporting_findings"]) > 0


# ---------------------------------------------------------------------------
# Test 6: Highest-risk component selection is deterministic
# ---------------------------------------------------------------------------

def test_highest_risk_component_deterministic(repo_root: Path) -> None:
    sim = simulate_release_impact(repo_root=repo_root, output_path=None, markdown_path=None)
    hr = sim["highest_risk_component"]

    # Appointment Search & Query Path ranks highest due to CRITICAL CWE-89 injection
    assert hr["component_name"] == "Appointment Search & Query Path"
    assert "SECURITY-001" in hr["related_findings"]
    assert hr["critical_findings"] == 1
    assert "CWE-89" in hr["rationale"] or "SQL injection" in hr["rationale"]


# ---------------------------------------------------------------------------
# Test 7: Required actions derive from findings
# ---------------------------------------------------------------------------

def test_required_actions_derived_from_findings(repo_root: Path) -> None:
    sim = simulate_release_impact(repo_root=repo_root, output_path=None, markdown_path=None)
    actions = sim["required_actions"]
    assert len(actions) >= 5

    # Check for presence of required actions across R001 to R005
    act_reqs = {a["requirement_id"] for a in actions}
    assert {"R001", "R002", "R003", "R004", "R005"}.issubset(act_reqs)


# ---------------------------------------------------------------------------
# Test 8: No probabilistic score generated (transparent metrics only)
# ---------------------------------------------------------------------------

def test_no_probabilistic_score(repo_root: Path) -> None:
    sim = simulate_release_impact(repo_root=repo_root, output_path=None, markdown_path=None)
    m = sim["metrics"]

    # Must be transparent counts
    assert isinstance(m["affected_components"], int)
    assert isinstance(m["affected_workflows"], int)
    assert isinstance(m["regression_paths"], int)
    assert m["critical_findings"] == 1
    assert m["high_findings"] == 19
    assert m["missing_regression_tests"] == 7

    # Ensure no float probabilities or percentages in metrics
    for k, v in m.items():
        assert isinstance(v, int), f"Metric '{k}' should be an integer count, got {type(v)}"


# ---------------------------------------------------------------------------
# Test 10: Missing input reports fail clearly
# ---------------------------------------------------------------------------

def test_missing_report_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(SimulationError, match="report missing"):
        simulate_release_impact(repo_root=tmp_path)
