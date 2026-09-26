"""Analysis Worker: claims jobs, gathers evidence, orchestrates parallel Grok agents, and persists release synthesis."""

import asyncio
import datetime
import os
import sys
import time
import traceback
from typing import Dict, Optional

from sqlalchemy.orm import Session
from shipsafe.database import (
    SessionLocal,
    init_db,
    AnalysisRun,
    AgentRun,
    Finding,
    RequirementCheck,
    Repository as DBRepository,
)
from shipsafe.core.repository import Repository
from shipsafe.core.evidence import EvidenceEngine, EvidencePack
from shipsafe.ai.provider import get_ai_provider
from shipsafe.ai.schemas import AgentReport
from shipsafe.agents import (
    ChangeImpactAgent,
    TestGapAgent,
    SecurityAgent,
    ContractAgent,
    DatabaseAgent,
    ReleaseSynthesizer,
)


class AnalysisWorker:
    """Processes enqueued analysis jobs continuously or on-demand."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.provider = get_ai_provider()

    async def run_forever(self):
        """Main worker loop."""
        print("[ShipSafe Worker] Started. Polling for pending analysis runs...")
        while True:
            try:
                processed = await self.process_next_job()
                if not processed:
                    await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"[ShipSafe Worker Error] Unexpected error in worker loop: {e}", file=sys.stderr)
                await asyncio.sleep(self.poll_interval)

    async def process_job_by_id(self, job_id: int) -> bool:
        """Claim and process a specific analysis job by ID."""
        db: Session = SessionLocal()
        try:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == job_id).first()
            if not run:
                return False

            run.status = "RUNNING"
            run.started_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(run)

            print(f"[ShipSafe Worker] Processing targeted job #{run.id} for repo ID {run.repository_id}")
            await self._execute_analysis(db, run)
            return True
        finally:
            db.close()

    async def process_next_job(self) -> bool:
        """Claim and process the next pending analysis job."""
        db: Session = SessionLocal()
        try:
            run = db.query(AnalysisRun).filter(AnalysisRun.status == "PENDING").first()
            if not run:
                return False

            # Claim job
            run.status = "RUNNING"
            run.started_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(run)

            print(f"[ShipSafe Worker] Claimed job #{run.id} for repo ID {run.repository_id} (Branch: {run.branch})")

            await self._execute_analysis(db, run)
            return True
        finally:
            db.close()

    async def _execute_analysis(self, db: Session, run: AnalysisRun):
        start_time = time.time()
        try:
            repo_record = run.repository
            if not repo_record:
                raise ValueError(f"Repository record missing for run #{run.id}")

            # Determine local filesystem path for the repository
            target_dir = repo_record.local_path
            if not target_dir or not os.path.isdir(target_dir):
                # Fallback to example repo or current workspace if not specified
                if os.path.isdir("examples/carehub"):
                    target_dir = os.path.abspath("examples/carehub")
                else:
                    target_dir = os.path.abspath(".")

            core_repo = Repository(root_dir=target_dir, name=repo_record.name)

            # 1. Deterministic Evidence Engine Collection
            print(f"[ShipSafe Worker] Assembling deterministic evidence pack from '{target_dir}'...")
            evidence: EvidencePack = EvidenceEngine.collect(
                repo=core_repo,
                base_commit=run.base_sha,
                head_commit=run.head_sha,
                run_tests=True
            )

            # 2. Parallel Specialist Agent Execution
            print("[ShipSafe Worker] Launching 5 parallel specialist agents via Grok provider...")
            agents = {
                "impact": ChangeImpactAgent(self.provider),
                "test_gap": TestGapAgent(self.provider),
                "security": SecurityAgent(self.provider),
                "contract": ContractAgent(self.provider),
                "database": DatabaseAgent(self.provider),
            }

            async def run_single_agent(name, agent):
                agent_start = time.time()
                try:
                    report = await agent.run(evidence)
                    duration = time.time() - agent_start
                    return name, report, duration, "COMPLETED", None
                except Exception as ex:
                    duration = time.time() - agent_start
                    return name, AgentReport(agent=name, findings=[]), duration, "FAILED", str(ex)

            agent_tasks = [run_single_agent(name, agent) for name, agent in agents.items()]
            agent_results = await asyncio.gather(*agent_tasks)

            agent_reports: Dict[str, AgentReport] = {}
            for name, report, duration, status, err in agent_results:
                agent_reports[name] = report
                # Record AgentRun
                agent_run_record = AgentRun(
                    analysis_run_id=run.id,
                    agent_name=name,
                    status=status,
                    raw_output=report.model_dump(),
                    duration_seconds=round(duration, 3)
                )
                db.add(agent_run_record)

            db.commit()

            # 3. Release Synthesizer & Gate Enforcement
            print("[ShipSafe Worker] Synthesizing findings and evaluating release gate...")
            synthesis = ReleaseSynthesizer.synthesize(core_repo, evidence, agent_reports)

            # 4. Persist Findings
            for f in synthesis["findings"]:
                db_finding = Finding(
                    analysis_run_id=run.id,
                    agent_name=f["agent_name"],
                    finding_id=f["finding_id"],
                    severity=f["severity"],
                    title=f["title"],
                    description=f["description"],
                    file=f["file"],
                    line_start=f.get("line_start"),
                    line_end=f.get("line_end"),
                    evidence=f.get("evidence"),
                    affected_components=f.get("affected_components", []),
                    recommendation=f.get("recommendation"),
                    confidence=f.get("confidence", 1.0),
                    verified=f["verified"],
                    verification_notes=f["verification_notes"]
                )
                db.add(db_finding)

            # 5. Persist Requirement Checks
            for rc in synthesis["requirement_checks"]:
                db_rc = RequirementCheck(
                    analysis_run_id=run.id,
                    requirement_id=rc["requirement_id"],
                    title=rc["title"],
                    status=rc["status"],
                    evidence=rc.get("evidence"),
                    related_findings=rc.get("related_findings", [])
                )
                db.add(db_rc)

            # 6. Finalize Run Record
            total_duration = time.time() - start_time
            run.status = "COMPLETED"
            run.release_status = synthesis["release_status"]
            run.completed_at = datetime.datetime.utcnow()
            run.duration_seconds = round(total_duration, 2)
            run.summary = synthesis["summary"]

            db.commit()
            print(f"[ShipSafe Worker] Completed run #{run.id} in {run.duration_seconds}s. Gate: {run.release_status}")

        except Exception as e:
            total_duration = time.time() - start_time
            run.status = "FAILED"
            run.error_message = f"{str(e)}\n{traceback.format_exc()}"
            run.completed_at = datetime.datetime.utcnow()
            run.duration_seconds = round(total_duration, 2)
            db.commit()
            print(f"[ShipSafe Worker] Failed run #{run.id}: {e}", file=sys.stderr)


if __name__ == "__main__":
    init_db()
    worker = AnalysisWorker()
    asyncio.run(worker.run_forever())
