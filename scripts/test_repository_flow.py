"""End-to-end CLI workflow test: registers a real repository, triggers analysis, and prints result."""

import argparse
import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shipsafe.database import SessionLocal, init_db, AnalysisRun
from shipsafe.core.repo_manager import RepositoryManager
from worker.worker import AnalysisWorker


def main():
    parser = argparse.ArgumentParser(description="Test full repository connect, analysis, and gate flow.")
    parser.add_argument("--url", required=True, help="GitHub repository URL")
    parser.add_argument("--branch", default=None, help="Branch to analyze")
    parser.add_argument("--token", default=None, help="Optional GitHub token")

    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    print(f"\n==================================================")
    print(f"  ShipSafe AI — Real Repository Flow Test")
    print(f"==================================================")
    print(f"Target: {args.url}")

    # 1. Connect
    print("\n[Step 1] Connecting repository...")
    repo = RepositoryManager.connect_repository(
        db=db,
        url=args.url,
        branch=args.branch,
        token=args.token
    )
    print(f"Connected: {repo.display_name} (Branch: {repo.selected_branch}, Commit: {repo.latest_commit_sha[:8]})")

    # 2. Enqueue real analysis
    print("\n[Step 2] Enqueuing analysis job...")
    run = AnalysisRun(
        repository_id=repo.id,
        event_type="cli_test",
        branch=repo.selected_branch,
        head_sha=repo.latest_commit_sha,
        status="PENDING",
        release_status="PENDING",
        summary={"trigger": "test_repository_flow"}
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 3. Execute analysis
    print(f"\n[Step 3] Executing analysis run #{run.id} with worker...")
    worker = AnalysisWorker()
    asyncio.run(worker.process_job_by_id(run.id))

    # 4. Print results
    db.refresh(run)
    print(f"\n==================================================")
    print(f"  Analysis Result for {repo.display_name}")
    print(f"==================================================")
    print(f"Run ID: #{run.id}")
    print(f"Branch: {run.branch}")
    print(f"Release Gate: {run.release_status}")
    print(f"Duration: {run.duration_seconds}s")
    print(f"Verified Findings Count: {len([f for f in run.findings if f.verified])}")

    for f in run.findings:
        if f.verified:
            print(f" - [{f.severity}] {f.finding_id}: {f.title} ({f.file}:{f.line_start or 1})")

    db.close()


if __name__ == "__main__":
    main()
