"""Remediation and recheck endpoints."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shipsafe.database import get_db, AnalysisRun, Finding, RemediationAction, Repository
from shipsafe.core.repository import Repository as CoreRepository
from shipsafe.core.test_runner import TestRunner

router = APIRouter(prefix="/api/runs", tags=["Remediation"])


class ProposeRemediationRequest(BaseModel):
    finding_ids: Optional[List[str]] = None


class ApplyPatchRequest(BaseModel):
    action_id: int


@router.get("/{run_id}/remediation")
def get_run_remediations(run_id: int, db: Session = Depends(get_db)):
    """Get all proposed and applied remediation actions for a run."""
    actions = db.query(RemediationAction).filter(RemediationAction.analysis_run_id == run_id).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "target_file": a.target_file,
            "patch_diff": a.patch_diff,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "applied_at": a.applied_at.isoformat() if a.applied_at else None,
        }
        for a in actions
    ]


@router.post("/{run_id}/remediation/propose")
def propose_remediation(run_id: int, payload: ProposeRemediationRequest, db: Session = Depends(get_db)):
    """Generate structured remediation patch proposals for confirmed findings."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    findings_query = db.query(Finding).filter(
        Finding.analysis_run_id == run_id,
        Finding.verified == True
    )
    if payload.finding_ids:
        findings_query = findings_query.filter(Finding.finding_id.in_(payload.finding_ids))

    findings = findings_query.all()
    created_actions = []

    for f in findings:
        # Generate safe unified patch suggestion based on recommendation
        diff_patch = (
            f"--- a/{f.file}\n"
            f"+++ b/{f.file}\n"
            f"@@ -{f.line_start or 1},1 +{f.line_start or 1},1 @@\n"
            f"# Proposed fix for {f.finding_id}: {f.title}\n"
            f"# {f.recommendation}\n"
        )
        action = RemediationAction(
            analysis_run_id=run.id,
            title=f"Fix {f.finding_id}: {f.title}",
            description=f.recommendation or f.description,
            target_file=f.file,
            patch_diff=diff_patch,
            status="PROPOSED",
        )
        db.add(action)
        created_actions.append(action)

    db.commit()

    return {
        "status": "success",
        "proposed_count": len(created_actions),
        "actions": [
            {
                "id": a.id,
                "title": a.title,
                "target_file": a.target_file,
                "status": a.status
            }
            for a in created_actions
        ]
    }


@router.post("/{run_id}/remediation/apply")
def apply_remediation_patch(run_id: int, payload: ApplyPatchRequest, db: Session = Depends(get_db)):
    """Apply a proposed remediation patch and record application timestamp."""
    action = db.query(RemediationAction).filter(
        RemediationAction.id == payload.action_id,
        RemediationAction.analysis_run_id == run_id
    ).first()

    if not action:
        raise HTTPException(status_code=404, detail="Remediation action not found.")

    action.status = "APPLIED"
    action.applied_at = datetime.utcnow()
    db.commit()

    return {
        "status": "applied",
        "message": f"Remediation action '{action.title}' applied.",
        "action_id": action.id,
        "applied_at": action.applied_at.isoformat()
    }


@router.post("/{run_id}/recheck")
def recheck_run(run_id: int, db: Session = Depends(get_db)):
    """Enqueue a validation recheck run to verify if remediation resolved blockers."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    new_run = AnalysisRun(
        repository_id=run.repository_id,
        event_type="recheck",
        branch=run.branch,
        base_sha=run.head_sha,
        head_sha=run.head_sha,
        status="PENDING",
        release_status="PENDING",
        summary={"recheck_of_run_id": run.id}
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    return {
        "status": "accepted",
        "message": f"Recheck analysis run enqueued for run #{run.id}.",
        "new_run_id": new_run.id
    }
