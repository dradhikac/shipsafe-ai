"""Release Synthesizer: validates evidence, aggregates specialist agents, and evaluates release gate."""

from typing import Dict, List, Any, Tuple, Optional
from shipsafe.ai.schemas import AgentReport, AgentFinding

from shipsafe.core.repository import Repository
from shipsafe.core.evidence import EvidencePack, EvidenceEngine


class ReleaseSynthesizer:
    """Consumes specialist agent reports, verifies findings against repository, and enforces release gate."""

    @classmethod
    def synthesize(
        cls,
        repo: Repository,
        evidence: EvidencePack,
        agent_reports: Dict[str, AgentReport],
        agent_statuses: Optional[Dict[str, str]] = None,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        from shipsafe.core.evidence_validator import EvidenceValidator

        all_findings: List[Dict[str, Any]] = []
        verified_findings: List[Dict[str, Any]] = []
        rejected_findings: List[Dict[str, Any]] = []

        # 1. Collect and verify all agent findings using EvidenceValidator
        for agent_name, report in agent_reports.items():
            for f in report.findings:
                f_dict = f.model_dump()
                f_dict["agent_name"] = agent_name

                # Ground finding against repository
                val_status, reason = EvidenceValidator.validate(repo, f_dict, context=context)
                is_valid = (val_status == EvidenceValidator.STATUS_VALIDATED)
                f_dict["verified"] = is_valid
                f_dict["validation_status"] = val_status
                f_dict["verification_notes"] = reason

                all_findings.append(f_dict)
                if is_valid:
                    verified_findings.append(f_dict)
                else:
                    rejected_findings.append(f_dict)

        # 2. Extract affected components and workflows
        affected_components = set()
        for f in verified_findings:
            for c in f.get("affected_components", []):
                affected_components.add(c)
        for f_diff in evidence.file_diffs:
            affected_components.add(f_diff["file_path"])

        # 3. Requirement Compliance Check
        requirement_checks = []
        for req in evidence.requirements:
            rid = req["id"]
            related = [
                f["finding_id"] for f in verified_findings
                if rid in f.get("description", "") or rid in f.get("title", "")
            ]
            has_violation = any(
                f["severity"] in ("CRITICAL", "HIGH")
                for f in verified_findings
                if f["finding_id"] in related and f["agent_name"] in ("contract", "security")
            )
            req_status = "NON_COMPLIANT" if has_violation else "COMPLIANT"
            requirement_checks.append({
                "requirement_id": rid,
                "title": req["title"],
                "status": req_status,
                "evidence": f"Linked to {len(related)} findings",
                "related_findings": related
            })

        # 4. Release Simulation & Blast Radius
        test_failures = evidence.test_results.get("failures", [])
        tests_failed = evidence.test_results.get("failed", 0) > 0 or len(test_failures) > 0

        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        component_risk = {}
        for f in verified_findings:
            sev = f["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            for comp in f.get("affected_components", []):
                component_risk[comp] = component_risk.get(comp, 0) + (10 if sev == "CRITICAL" else 5 if sev == "HIGH" else 2)

        highest_risk = max(component_risk.items(), key=lambda x: x[1])[0] if component_risk else "None"

        # 5. Deterministic Release Gate Evaluation
        has_critical_security = any(
            f["severity"] == "CRITICAL" and f["agent_name"] == "security"
            for f in verified_findings
        )
        has_critical_db = any(
            f["severity"] == "CRITICAL" and f["agent_name"] == "database"
            for f in verified_findings
        )
        has_blocking_req = any(r["status"] == "NON_COMPLIANT" for r in requirement_checks)

        statuses = agent_statuses or {}
        has_failed_agent = any(st == "FAILED" for st in statuses.values())

        is_blocked = (
            has_critical_security or
            has_critical_db or
            tests_failed or
            has_blocking_req
        )

        has_high_finding = any(f["severity"] == "HIGH" for f in verified_findings)
        has_test_gap = any(f["agent_name"] == "test_gap" for f in verified_findings)
        has_api_mismatch = any(f["agent_name"] == "contract" for f in verified_findings)

        if is_blocked:
            release_status = "BLOCKED"
        elif has_high_finding or has_test_gap or has_api_mismatch or has_failed_agent:
            release_status = "ATTENTION"
        else:
            release_status = "READY"

        simulation = {
            "affected_workflows": list(affected_components)[:10],
            "highest_risk_component": highest_risk,
            "test_gaps": [f["title"] for f in verified_findings if f["agent_name"] == "test_gap"][:5],
            "api_concerns": [f["title"] for f in verified_findings if f["agent_name"] == "contract"][:5],
            "database_concerns": [f["title"] for f in verified_findings if f["agent_name"] == "database"][:5],
            "recommended_validations": [
                f["recommendation"] for f in verified_findings if f.get("recommendation")
            ][:5],
            "blast_radius_nodes": [
                {"id": comp, "label": comp, "risk": component_risk.get(comp, 1)}
                for comp in list(affected_components)[:15]
            ]
        }


        summary = {
            "release_status": release_status,
            "severity_counts": severity_counts,
            "total_findings": len(all_findings),
            "verified_findings_count": len(verified_findings),
            "unverified_findings_count": len(rejected_findings),
            "rejected_findings_count": len(rejected_findings),
            "tests_passed": evidence.test_results.get("is_all_passed", False),

            "test_summary": {
                "total": evidence.test_results.get("total_tests", 0),
                "passed": evidence.test_results.get("passed", 0),
                "failed": evidence.test_results.get("failed", 0),
            },
            "files_analyzed": evidence.discovery.get("total_files", len(evidence.changed_files) or len(evidence.code_snippets)),
            "tests_discovered": evidence.test_results.get("total_tests") if evidence.test_results.get("total_tests", 0) > 0 else len(evidence.discovery.get("test_files", [])),
            "requirements_count": len(evidence.requirements),
            "simulation": simulation,
        }

        return {
            "release_status": release_status,
            "summary": summary,
            "findings": all_findings,
            "requirement_checks": requirement_checks,
            "simulation": simulation,
        }
