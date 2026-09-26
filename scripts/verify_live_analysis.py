import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath("."))
from shipsafe.database import SessionLocal, init_db, Repository as DBRepository, AnalysisRun, Finding, AgentRun
from worker.worker import AnalysisWorker

def main():
    init_db()
    db = SessionLocal()

    repo_path = os.path.abspath('tests/fixtures/repo_python')
    repo_rec = db.query(DBRepository).filter(DBRepository.name == 'repo_python_demo').first()
    if not repo_rec:
        repo_rec = DBRepository(
            name='repo_python_demo',
            repo_url='https://github.com/shipsafe/repo_python_demo',
            local_path=repo_path,
            default_branch='main',
            selected_branch='main',
            files_count=3,
            is_active=True
        )
        db.add(repo_rec)
        db.commit()
        db.refresh(repo_rec)

    run = AnalysisRun(
        repository_id=repo_rec.id,
        event_type='manual',
        branch='main',
        head_sha='9a8b7c6d5e4f3a2b1c0d',
        status='PENDING',
        release_status='PENDING',
        summary={'trigger': 'verification_test'}
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    worker = AnalysisWorker()
    asyncio.run(worker.process_job_by_id(run.id))

    db.refresh(run)
    findings = db.query(Finding).filter(Finding.analysis_run_id == run.id).all()
    agent_runs = db.query(AgentRun).filter(AgentRun.analysis_run_id == run.id).all()

    print('=== ANALYSIS RESULT ===')
    print(f'Repository: {repo_rec.name} ({repo_rec.local_path})')
    print(f'Branch: {run.branch}')
    print(f'Commit: {run.head_sha}')
    print(f'Files: {run.summary.get("files_analyzed", 0)}')
    print(f'Agents: {len([a for a in agent_runs if a.status == "COMPLETED"])} / {len(agent_runs)} completed')
    print(f'Findings: {len(findings)} ({len([f for f in findings if f.validation_status == "VALIDATED"])} validated)')
    print(f'Release Status: {run.release_status}')

    print('\n=== FINDINGS INSPECTION ===')
    for f in findings:
        target_path = os.path.join(repo_path, f.file) if not os.path.isabs(f.file) else f.file
        exists = os.path.exists(target_path)
        line_exists = False
        actual_line = ''
        if exists and f.line_start:
            with open(target_path, 'r', encoding='utf-8', errors='replace') as fp:
                lines = fp.readlines()
                if 0 < f.line_start <= len(lines):
                    line_exists = True
                    actual_line = lines[f.line_start - 1].strip()
        print(f'Finding ID: {f.finding_id}')
        print(f'  Agent: {f.agent_name}')
        print(f'  Severity: {f.severity}')
        print(f'  Title: {f.title}')
        print(f'  File: {f.file} (File Exists on Disk: {exists})')
        print(f'  Line: {f.line_start} (Line Exists on Disk: {line_exists} -> "{actual_line}")')
        print(f'  Evidence: {f.evidence}')
        print(f'  Validation Status: {f.validation_status}')
        print(f'  Confidence: {f.confidence}')
        print(f'  Recommendation: {f.recommendation}')
        print('---')
    db.close()

if __name__ == '__main__':
    main()
