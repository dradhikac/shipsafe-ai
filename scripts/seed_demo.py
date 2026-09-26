"""Seed database with CareHub Example Repository and initial release run."""

import os
import sys
import datetime

# Add root to sys.path
sys.path.insert(0, os.path.abspath("."))

from shipsafe.database import SessionLocal, init_db, Repository, AnalysisRun, Finding, RequirementCheck
from worker.worker import AnalysisWorker
import asyncio


def seed_demo_data():
    init_db()
    db = SessionLocal()

    # 1. Register Example Repository (CareHub)
    carehub_path = os.path.abspath("examples/carehub")
    repo = db.query(Repository).filter(Repository.name == "carehub-appointment-service").first()

    if not repo:
        repo = Repository(
            name="carehub-appointment-service",
            repo_url="https://github.com/example/carehub-appointment-service.git",
            local_path=carehub_path if os.path.isdir(carehub_path) else os.path.abspath("."),
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        print(f"[Seed] Created Example Repository: {repo.name} (ID: {repo.id})")
    else:
        print(f"[Seed] Repository already registered: {repo.name} (ID: {repo.id})")

    # 2. Check if runs exist; if not, trigger initial baseline run
    run_count = db.query(AnalysisRun).filter(AnalysisRun.repository_id == repo.id).count()
    if run_count == 0:
        print("[Seed] Enqueuing initial baseline analysis run...")
        run = AnalysisRun(
            repository_id=repo.id,
            event_type="seed_baseline",
            branch="main",
            status="PENDING",
            release_status="PENDING",
            summary={"trigger": "seed_demo"}
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Execute run with worker
        os.environ["AI_PROVIDER"] = "mock"
        worker = AnalysisWorker()
        asyncio.run(worker.process_job_by_id(run.id))
        db.refresh(run)
        print(f"[Seed] Initial analysis run completed! Status: {run.release_status}")
    else:
        print(f"[Seed] Repository already has {run_count} analysis runs recorded.")

    db.close()
    print("[Seed] Seeding complete! Database is ready for Streamlit console.")


if __name__ == "__main__":
    seed_demo_data()
