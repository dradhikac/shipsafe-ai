"""Deterministic remediation patch engine and before/after verification."""

import os
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from shipsafe.database import AnalysisRun, Finding, RemediationAction, Repository as DBRepo
from shipsafe.core.repository import Repository
from shipsafe.core.test_runner import TestRunner


class RemediationEngine:
    """Manages patch generation, safe application, and before/after finding comparisons."""

    @classmethod
    def propose_patches_for_run(cls, db: Session, run_id: int) -> List[RemediationAction]:
        """Generate unified diff patch proposals for verified findings."""
        findings = db.query(Finding).filter(
            Finding.analysis_run_id == run_id,
            Finding.verified == True
        ).all()

        actions = []
        for f in findings:
            # Generate deterministic patch suggestion
            diff_text = (
                f"--- a/{f.file}\n"
                f"+++ b/{f.file}\n"
                f"@@ -{f.line_start or 1},1 +{f.line_start or 1},1 @@\n"
                f"# Remediating {f.finding_id} ({f.severity})\n"
                f"# Guidance: {f.recommendation}\n"
            )
            action = RemediationAction(
                analysis_run_id=run_id,
                title=f"Resolve {f.finding_id}: {f.title}",
                description=f.recommendation or f.description,
                target_file=f.file,
                patch_diff=diff_text,
                status="PROPOSED"
            )
            db.add(action)
            actions.append(action)

        db.commit()
        return actions

    @classmethod
    def compare_runs(cls, db: Session, before_run_id: int, after_run_id: int) -> Dict[str, Any]:
        """Compare findings and release gates between two runs (before vs after remediation)."""
        before_run = db.query(AnalysisRun).filter(AnalysisRun.id == before_run_id).first()
        after_run = db.query(AnalysisRun).filter(AnalysisRun.id == after_run_id).first()

        if not before_run or not after_run:
            raise ValueError("One or both run IDs do not exist.")

        before_findings = {f.finding_id: f for f in before_run.findings}
        after_findings = {f.finding_id: f for f in after_run.findings}

        resolved_ids = set(before_findings.keys()) - set(after_findings.keys())
        remaining_ids = set(before_findings.keys()) & set(after_findings.keys())
        new_ids = set(after_findings.keys()) - set(before_findings.keys())

        return {
            "before_run_id": before_run_id,
            "after_run_id": after_run_id,
            "before_gate": before_run.release_status,
            "after_gate": after_run.release_status,
            "gate_improved": before_run.release_status == "BLOCKED" and after_run.release_status in ("READY", "ATTENTION"),
            "resolved_findings": [before_findings[fid].title for fid in resolved_ids],
            "remaining_findings": [after_findings[fid].title for fid in remaining_ids],
            "new_findings": [after_findings[fid].title for fid in new_ids],
        }
