"""Integration tests for Remediation Engine and Before/After verification."""

import pytest
from shipsafe.database import SessionLocal, init_db, Repository, AnalysisRun, Finding, RemediationAction
from shipsafe.remediation.patch_engine import RemediationEngine


def test_remediation_propose_and_compare():
    init_db()
    db = SessionLocal()

    # 1. Setup repository and initial run with findings
    repo = db.query(Repository).first()
    if not repo:
        repo = Repository(
            name="test-remediation-repo",
            repo_url="https://github.com/example/remediation-test.git",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
    assert repo is not None

    before_run = AnalysisRun(
        repository_id=repo.id,
        event_type="push",
        branch="feature/test-remediation",
        status="COMPLETED",
        release_status="BLOCKED"
    )
    db.add(before_run)
    db.commit()
    db.refresh(before_run)

    # Add verified finding
    f1 = Finding(
        analysis_run_id=before_run.id,
        agent_name="security",
        finding_id="SEC-TEST-001",
        severity="CRITICAL",
        title="Raw query parameter concatenation",
        description="SQL injection in search",
        file="README.md",
        line_start=1,
        line_end=5,
        evidence="ShipSafe AI",
        recommendation="Use parameterized query",
        verified=True,
        verification_notes="Verified"
    )
    db.add(f1)
    db.commit()

    # 2. Propose remediation actions
    actions = RemediationEngine.propose_patches_for_run(db, before_run.id)
    assert len(actions) == 1
    action = actions[0]
    assert action.target_file == "README.md"
    assert "--- a/README.md" in action.patch_diff
    assert action.status == "PROPOSED"

    # 3. Simulate After Run where finding is resolved
    after_run = AnalysisRun(
        repository_id=repo.id,
        event_type="recheck",
        branch="feature/test-remediation",
        status="COMPLETED",
        release_status="READY"
    )
    db.add(after_run)
    db.commit()
    db.refresh(after_run)

    # 4. Compare runs
    comparison = RemediationEngine.compare_runs(db, before_run.id, after_run.id)
    assert comparison["before_gate"] == "BLOCKED"
    assert comparison["after_gate"] == "READY"
    assert comparison["gate_improved"] is True
    assert len(comparison["resolved_findings"]) == 1
    assert "Raw query parameter concatenation" in comparison["resolved_findings"]

    db.close()
