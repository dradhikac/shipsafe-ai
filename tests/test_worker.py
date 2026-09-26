"""Integration test for AnalysisWorker."""

import os
import asyncio
from shipsafe.database import SessionLocal, init_db, Repository, AnalysisRun
from worker.worker import AnalysisWorker


def test_worker_process_job():
    async def _run():
        init_db()
        db = SessionLocal()

        # Ensure repository exists
        repo = db.query(Repository).filter(Repository.name == "worker-test-repo").first()
        if not repo:
            repo = Repository(
                name="worker-test-repo",
                repo_url="https://github.com/example/worker-test.git",
                local_path=os.path.abspath("examples/carehub") if os.path.isdir("examples/carehub") else os.path.abspath("."),
                default_branch="main"
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)

        # Create a pending analysis run
        run = AnalysisRun(
            repository_id=repo.id,
            event_type="push",
            branch="main",
            status="PENDING",
            release_status="PENDING"
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        db.close()

        # Set mock provider for test
        os.environ["AI_PROVIDER"] = "mock"

        worker = AnalysisWorker()
        processed = await worker.process_job_by_id(run_id)
        assert processed is True

        # Verify run completed in DB
        db2 = SessionLocal()
        completed_run = db2.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        assert completed_run is not None
        assert completed_run.status == "COMPLETED"
        assert completed_run.release_status in ("READY", "ATTENTION", "BLOCKED")
        assert len(completed_run.findings) > 0
        assert len(completed_run.agent_runs) == 5
        db2.close()

    asyncio.run(_run())
