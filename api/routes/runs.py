"""Analysis run inspection endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shipsafe.database import get_db, AnalysisRun, Finding, RequirementCheck

router = APIRouter(prefix="/api/runs", tags=["Analysis Runs"])


@router.get("")
def list_analysis_runs(
    repository_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """List analysis runs ordered by most recent."""
    query = db.query(AnalysisRun)
    if repository_id:
        query = query.filter(AnalysisRun.repository_id == repository_id)
    if status:
        query = query.filter(AnalysisRun.status == status)

    runs = query.order_by(AnalysisRun.id.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "repository_id": r.repository_id,
            "repository_name": r.repository.name if r.repository else None,
            "event_type": r.event_type,
            "branch": r.branch,
            "base_sha": r.base_sha,
            "head_sha": r.head_sha,
            "status": r.status,
            "release_status": r.release_status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "duration_seconds": r.duration_seconds,
            "summary": r.summary,
        }
        for r in runs
    ]


@router.get("/{run_id}")
def get_analysis_run(run_id: int, db: Session = Depends(get_db)):
    """Get full details of a specific analysis run."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    return {
        "id": run.id,
        "repository_id": run.repository_id,
        "repository_name": run.repository.name if run.repository else None,
        "event_type": run.event_type,
        "branch": run.branch,
        "base_sha": run.base_sha,
        "head_sha": run.head_sha,
        "status": run.status,
        "release_status": run.release_status,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": run.duration_seconds,
        "summary": run.summary,
        "findings_count": len(run.findings),
        "requirements_count": len(run.requirement_checks),
    }


@router.get("/{run_id}/findings")
def get_run_findings(run_id: int, severity: Optional[str] = None, db: Session = Depends(get_db)):
    """Get verified and unverified findings for an analysis run."""
    query = db.query(Finding).filter(Finding.analysis_run_id == run_id)
    if severity:
        query = query.filter(Finding.severity == severity.upper())

    findings = query.order_by(Finding.id.asc()).all()

    return [
        {
            "id": f.id,
            "finding_id": f.finding_id,
            "agent_name": f.agent_name,
            "severity": f.severity,
            "title": f.title,
            "description": f.description,
            "file": f.file,
            "line_start": f.line_start,
            "line_end": f.line_end,
            "evidence": f.evidence,
            "affected_components": f.affected_components or [],
            "recommendation": f.recommendation,
            "confidence": f.confidence,
            "verified": f.verified,
            "verification_notes": f.verification_notes,
        }
        for f in findings
    ]


@router.get("/{run_id}/requirements")
def get_run_requirements(run_id: int, db: Session = Depends(get_db)):
    """Get requirement checks and traceability statuses for an analysis run."""
    checks = db.query(RequirementCheck).filter(RequirementCheck.analysis_run_id == run_id).all()
    return [
        {
            "id": c.id,
            "requirement_id": c.requirement_id,
            "title": c.title,
            "status": c.status,
            "evidence": c.evidence,
            "related_findings": c.related_findings or [],
        }
        for c in checks
    ]


@router.get("/{run_id}/simulation")
def get_run_simulation(run_id: int, db: Session = Depends(get_db)):
    """Get release simulation and blast radius mapping for an analysis run."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    summary = run.summary or {}
    simulation = summary.get("simulation", {})

    return {
        "run_id": run.id,
        "release_status": run.release_status,
        "affected_workflows": simulation.get("affected_workflows", []),
        "highest_risk_component": simulation.get("highest_risk_component", "Unknown"),
        "test_gaps": simulation.get("test_gaps", []),
        "api_concerns": simulation.get("api_concerns", []),
        "database_concerns": simulation.get("database_concerns", []),
        "recommended_validations": simulation.get("recommended_validations", []),
        "blast_radius_nodes": simulation.get("blast_radius_nodes", []),
    }
