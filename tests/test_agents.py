"""Unit tests for Grok specialist agents and Release Synthesizer."""

import pytest
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
from shipsafe.core.repository import Repository
from shipsafe.core.evidence import EvidenceEngine


def test_specialist_agents_execution():
    import asyncio
    async def _run():
        provider = MockProvider()
        repo = Repository(root_dir=".")
        evidence = EvidenceEngine.collect(repo, run_tests=False)

        impact_agent = ChangeImpactAgent(provider)
        test_gap_agent = TestGapAgent(provider)
        security_agent = SecurityAgent(provider)
        contract_agent = ContractAgent(provider)
        db_agent = DatabaseAgent(provider)

        r_impact = await impact_agent.run(evidence)
        r_gap = await test_gap_agent.run(evidence)
        r_sec = await security_agent.run(evidence)
        r_con = await contract_agent.run(evidence)
        r_db = await db_agent.run(evidence)

        assert r_impact.agent == "impact"
        assert len(r_impact.findings) > 0

        assert r_gap.agent == "test_gap"
        assert len(r_gap.findings) > 0

        assert r_sec.agent == "security"
        assert len(r_sec.findings) > 0

        assert r_con.agent == "contract"
        assert len(r_con.findings) > 0

        assert r_db.agent == "database"
        assert len(r_db.findings) > 0

    asyncio.run(_run())


def test_synthesizer_gate_evaluation():
    repo = Repository(root_dir=".")
    evidence = EvidenceEngine.collect(repo, run_tests=False)

    # 1. Test BLOCKED when Critical Security finding exists
    critical_reports = {
        "security": AgentReport(
            agent="security",
            findings=[
                AgentFinding(
                    finding_id="SEC-001",
                    severity="CRITICAL",
                    title="SQL Injection in auth",
                    description="Unsafe query format",
                    file="README.md",
                    line_start=1,
                    line_end=5,
                    evidence="ShipSafe",
                )
            ]
        )
    }
    synthesis = ReleaseSynthesizer.synthesize(repo, evidence, critical_reports)
    assert synthesis["release_status"] == "BLOCKED"

    # 2. Test ATTENTION when only High finding exists
    high_reports = {
        "impact": AgentReport(
            agent="impact",
            findings=[
                AgentFinding(
                    finding_id="IMP-001",
                    severity="HIGH",
                    title="High blast radius",
                    description="Wide import surface",
                    file="README.md",
                    line_start=1,
                    line_end=5,
                    evidence="ShipSafe",
                )
            ]
        )
    }
    synthesis_high = ReleaseSynthesizer.synthesize(repo, evidence, high_reports)
    assert synthesis_high["release_status"] == "ATTENTION"

    # 3. Test READY when only Low/Info findings exist and tests pass
    evidence.test_results["is_all_passed"] = True
    evidence.test_results["total_tests"] = 5
    evidence.test_results["failed"] = 0
    clean_reports = {
        "impact": AgentReport(
            agent="impact",
            findings=[
                AgentFinding(
                    finding_id="IMP-002",
                    severity="LOW",
                    title="Minor docs update",
                    description="Comment revised",
                    file="README.md",
                    line_start=1,
                    line_end=2,
                    evidence="ShipSafe",
                )
            ]
        )
    }
    synthesis_ready = ReleaseSynthesizer.synthesize(repo, evidence, clean_reports)
    assert synthesis_ready["release_status"] == "READY"
