"""Tests for shipsafe.analyzer.remediation.

Verifies:
1. All confirmed findings generate plan items across R001–R005.
2. Every remediation item contains concrete supporting evidence.
3. Requirement IDs are valid.
4. Affected files exist in the repository or target application.
5. Validation commands are specified for each remediation item.
6. R003 chooses requirement-compliant remediation (reverts 'critical').
7. R003 does not recommend creating a migration for the unauthorized 'critical' priority.
8. R004 requires parameterized SQL queries to eliminate SQL injection.
9. R005 specifies restoring the 7 deleted regression tests.
10. Remediation plan JSON and Markdown artifacts serialize and deserialize cleanly.
11. Malformed or missing inputs fail clearly with RemediationPlanError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipsafe.analyzer import remediation
from shipsafe.analyzer.remediation import (
    RemediationPlanError,
    generate_remediation_plan,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Test 1 & 3: All requirements have plan items and IDs are valid
# ---------------------------------------------------------------------------

def test_all_requirements_have_valid_plan_items(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    items = plan["remediation_items"]
    assert len(items) == 5

    req_ids = [item["requirement_id"] for item in items]
    assert set(req_ids) == {"R001", "R002", "R003", "R004", "R005"}


# ---------------------------------------------------------------------------
# Test 2: Every item has concrete evidence
# ---------------------------------------------------------------------------

def test_every_item_has_concrete_evidence(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    for item in plan["remediation_items"]:
        assert len(item["evidence"]) > 0, f"Item {item['remediation_id']} lacks evidence."
        assert len(item["finding_ids"]) > 0


# ---------------------------------------------------------------------------
# Test 4: Affected files are real repository paths
# ---------------------------------------------------------------------------

def test_affected_files_are_real(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    for item in plan["remediation_items"]:
        for f in item["affected_files"]:
            file_path = repo_root / f
            assert file_path.is_file(), f"Affected file '{f}' in {item['remediation_id']} not found."


# ---------------------------------------------------------------------------
# Test 5: Validation commands are present
# ---------------------------------------------------------------------------

def test_validation_commands_present(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    for item in plan["remediation_items"]:
        assert len(item["validation_commands"]) > 0
        assert any("pytest" in cmd for cmd in item["validation_commands"])


# ---------------------------------------------------------------------------
# Test 6 & 7: R003 requirement compliance & rejects migration for 'critical'
# ---------------------------------------------------------------------------

def test_r003_conflict_resolution(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    r003_item = next(item for item in plan["remediation_items"] if item["requirement_id"] == "R003")

    # Verify R003 chooses removal of 'critical'
    assert "critical" in r003_item["root_cause"].lower()
    assert "revert valid_priorities" in r003_item["required_change"].lower() or "remove" in r003_item["required_change"].lower()

    # Verify that it explicitly rejects creating a migration for 'critical'
    assert "do not create" in r003_item["required_change"].lower() or "rejected" in r003_item["conflict_resolution"].lower()
    assert "001_initial_schema.sql" in r003_item["required_change"]

    # Verify required tests assert rejection of 'critical'
    test_names = [t["test_name"] for t in r003_item["required_tests"]]
    assert any("critical" in t for t in test_names)
    assert any("normal" in t for t in test_names)


# ---------------------------------------------------------------------------
# Test 8: R004 requires parameterized SQL
# ---------------------------------------------------------------------------

def test_r004_requires_parameterized_sql(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    r004_item = next(item for item in plan["remediation_items"] if item["requirement_id"] == "R004")

    assert r004_item["priority"] == "CRITICAL"
    assert "parameterized" in r004_item["required_change"].lower()
    assert "?" in r004_item["required_change"]
    assert "CWE-89" in r004_item["current_problem"] or "injection" in r004_item["current_problem"]


# ---------------------------------------------------------------------------
# Test 9: R005 specifies regression tests
# ---------------------------------------------------------------------------

def test_r005_specifies_regression_tests(repo_root: Path) -> None:
    plan = generate_remediation_plan(repo_root=repo_root, output_path=None, markdown_path=None)
    r005_item = next(item for item in plan["remediation_items"] if item["requirement_id"] == "R005")

    # 7 regression tests specified
    assert len(r005_item["required_tests"]) == 7
    test_names = {t["test_name"] for t in r005_item["required_tests"]}
    assert "test_cancelled_appointment_does_not_trigger_reminder" in test_names
    assert "test_create_appointment_response_includes_required_fields" in test_names
    assert "test_appointment_priority_persisted_normal" in test_names


# ---------------------------------------------------------------------------
# Test 10: Serialization round-trip
# ---------------------------------------------------------------------------

def test_plan_serialization(repo_root: Path, tmp_path: Path) -> None:
    out_json = tmp_path / "remediation_plan.json"
    out_md = tmp_path / "REMEDIATION_PLAN.md"

    plan = generate_remediation_plan(
        repo_root=repo_root,
        output_path=out_json,
        markdown_path=out_md,
    )

    assert out_json.is_file()
    assert out_md.is_file()

    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["plan_type"] == "evidence_backed_remediation_plan"
    assert len(loaded["remediation_items"]) == 5
    assert loaded["execution_order"] == [
        "REM-R004", "REM-R001", "REM-R002", "REM-R003", "REM-R005"
    ]

    md_text = out_md.read_text(encoding="utf-8")
    assert "# ShipSafe AI — Remediation Plan" in md_text
    assert "## Safe Execution Order" in md_text
    assert "REM-R004" in md_text


# ---------------------------------------------------------------------------
# Test 11: Missing input fails clearly
# ---------------------------------------------------------------------------

def test_missing_report_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(RemediationPlanError, match="report missing"):
        generate_remediation_plan(repo_root=tmp_path)
