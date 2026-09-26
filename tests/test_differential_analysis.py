"""Differential analysis tests across distinct repositories and EvidenceValidator validation."""

import os
import asyncio
import pytest
from shipsafe.core.repository import Repository
from shipsafe.core.evidence import EvidenceEngine
from shipsafe.core.evidence_validator import EvidenceValidator
from shipsafe.core.context import AnalysisContext
from shipsafe.ai.mock_provider import MockProvider
from shipsafe.ai.schemas import AgentReport, AgentFinding
from shipsafe.agents import (
    ChangeImpactAgent,
    TestGapAgent,
    SecurityAgent,
    ContractAgent,
    DatabaseAgent,
    ReleaseSynthesizer,
)


@pytest.fixture
def fixtures_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))


def test_differential_analysis_across_distinct_repositories(fixtures_dir):
    """Verify that different repositories produce strictly different findings and zero findings where appropriate."""
    repo_py_path = os.path.join(fixtures_dir, "repo_python")
    repo_js_path = os.path.join(fixtures_dir, "repo_js")
    repo_nodb_path = os.path.join(fixtures_dir, "repo_no_database")

    provider = MockProvider()

    async def analyze_repo(path: str, repo_id: int):
        repo = Repository(root_dir=path, name=os.path.basename(path))
        evidence = EvidenceEngine.collect(repo, run_tests=False)
        profile = repo.discovery.get_profile()

        context = AnalysisContext(
            repository_id=repo_id,
            repository_url=f"https://github.com/test/{os.path.basename(path)}",
            repository_name=os.path.basename(path),
            branch="main",
            commit_sha="commit_abc123",
            base_sha=None,
            profile=profile,
        )

        agents = {
            "impact": ChangeImpactAgent(provider),
            "test_gap": TestGapAgent(provider),
            "security": SecurityAgent(provider),
            "contract": ContractAgent(provider),
            "database": DatabaseAgent(provider),
        }

        reports = {}
        for name, agent in agents.items():
            reports[name] = await agent.run(evidence)

        synthesis = ReleaseSynthesizer.synthesize(
            repo=repo,
            evidence=evidence,
            agent_reports=reports,
            agent_statuses={k: "COMPLETED" for k in reports},
            context=context,
        )
        return repo, evidence, reports, synthesis

    async def _test():
        _, _, rep_py, syn_py = await analyze_repo(repo_py_path, 1)
        _, _, rep_js, syn_js = await analyze_repo(repo_js_path, 2)
        _, _, rep_nodb, syn_nodb = await analyze_repo(repo_nodb_path, 3)

        # 1. Verify differential findings: A != B and B != C
        py_finding_ids = [f["finding_id"] for f in syn_py["findings"]]
        js_finding_ids = [f["finding_id"] for f in syn_js["findings"]]
        nodb_finding_ids = [f["finding_id"] for f in syn_nodb["findings"]]

        assert py_finding_ids != js_finding_ids
        assert js_finding_ids != nodb_finding_ids

        # 2. Verify Security Agent finds the SQL injection in repo_python
        py_sec_findings = [f for f in syn_py["findings"] if f["agent_name"] == "security"]
        assert len(py_sec_findings) >= 1
        assert "SQL" in py_sec_findings[0]["title"]
        assert "routes/auth.py" in py_sec_findings[0]["file"]
        assert py_sec_findings[0]["verified"] is True
        assert py_sec_findings[0]["validation_status"] == EvidenceValidator.STATUS_VALIDATED

        # 3. Verify Security Agent returns ZERO findings for clean JS and No-DB repos
        js_sec_findings = [f for f in syn_js["findings"] if f["agent_name"] == "security"]
        assert len(js_sec_findings) == 0

        nodb_sec_findings = [f for f in syn_nodb["findings"] if f["agent_name"] == "security"]
        assert len(nodb_sec_findings) == 0

        # 4. Verify Contract Agent finds the schema mismatch in repo_js
        js_contract_findings = [f for f in syn_js["findings"] if f["agent_name"] == "contract"]
        assert len(js_contract_findings) >= 1
        assert "userId" in js_contract_findings[0]["description"]

        # 5. Verify Database Agent returns ZERO findings for repo_no_database
        nodb_db_findings = [f for f in syn_nodb["findings"] if f["agent_name"] == "database"]
        assert len(nodb_db_findings) == 0

        # 6. Verify NO agent reports generic findings against README.md
        for f in syn_py["findings"] + syn_js["findings"] + syn_nodb["findings"]:
            assert "readme.md" not in f["file"].lower()
            assert "Unbounded blast radius in README" not in f["title"]

    asyncio.run(_test())


def test_evidence_validator_rules():
    """Verify that EvidenceValidator strictly accepts grounded findings and rejects invalid ones."""
    repo = Repository(root_dir=".")

    # 1. Grounded valid finding
    valid_f = {
        "agent": "security",
        "finding_id": "SEC-001",
        "file": "shipsafe/core/evidence_validator.py",
        "line_start": 1,
        "line_end": 5,
        "evidence": "Deterministic evidence validation engine.",
    }
    status, notes = EvidenceValidator.validate(repo, valid_f)
    assert status == EvidenceValidator.STATUS_VALIDATED

    # 2. Non-existent file
    missing_f = {
        "agent": "security",
        "finding_id": "SEC-002",
        "file": "src/non_existent_module.py",
        "line_start": 10,
        "line_end": 20,
    }
    status, notes = EvidenceValidator.validate(repo, missing_f)
    assert status == EvidenceValidator.STATUS_REJECTED
    assert "does not exist" in notes

    # 3. Line number beyond total lines in file
    out_of_bounds_f = {
        "agent": "security",
        "finding_id": "SEC-003",
        "file": "shipsafe/core/evidence_validator.py",
        "line_start": 999999,
        "line_end": 999999,
    }
    status, notes = EvidenceValidator.validate(repo, out_of_bounds_f)
    assert status == EvidenceValidator.STATUS_REJECTED
    assert "beyond end of file" in notes

    # 4. Reject database finding on README.md
    readme_db_f = {
        "agent": "database",
        "finding_id": "DB-001",
        "file": "README.md",
        "line_start": 1,
        "line_end": 5,
    }
    status, notes = EvidenceValidator.validate(repo, readme_db_f)
    assert status == EvidenceValidator.STATUS_REJECTED
    assert "Database finding rejected" in notes

    # 5. Reject test gap finding on README.md
    readme_gap_f = {
        "agent": "test_gap",
        "finding_id": "GAP-001",
        "file": "README.md",
        "line_start": 1,
        "line_end": 5,
    }
    status, notes = EvidenceValidator.validate(repo, readme_gap_f)
    assert status == EvidenceValidator.STATUS_REJECTED
    assert "Test gap finding rejected" in notes


def test_agent_failure_gate_behavior():
    """Verify release synthesizer does not claim READY when a specialist agent fails."""
    repo = Repository(root_dir=".")
    evidence = EvidenceEngine.collect(repo, run_tests=False)

    reports = {
        "impact": AgentReport(agent="impact", findings=[]),
        "security": AgentReport(agent="security", findings=[]),
    }
    # Simulate Security Agent failure
    agent_statuses = {
        "impact": "COMPLETED",
        "security": "FAILED",
    }

    synthesis = ReleaseSynthesizer.synthesize(
        repo=repo,
        evidence=evidence,
        agent_reports=reports,
        agent_statuses=agent_statuses
    )

    # Gate must not silently claim READY
    assert synthesis["release_status"] != "READY"
    assert synthesis["release_status"] == "ATTENTION"
