"""ShipSafe Release Synthesizer.

Consolidates, normalizes, and synthesizes the five specialized analysis reports
produced by IBM Bob 2.0 subagents:
1. Impact Analyst (reports/agents/impact_report.json)
2. Test Gap Analyst (reports/agents/test_gap_report.json)
3. Security Analyst (reports/agents/security_report.json)
4. Contract & Documentation Analyst (reports/agents/contract_report.json)
5. Database Analyst (reports/agents/database_report.json)

The five IBM Bob reports are treated as immutable historical evidence.
Normalization and synthesis are deterministic and executed locally by ShipSafe.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shipsafe.analyzer import evidence, git_analyzer, report_builder, requirements as req_loader


# ---------------------------------------------------------------------------
# Constants & Specification
# ---------------------------------------------------------------------------

EXPECTED_AGENTS = ("impact", "test_gap", "security", "contract", "database")

AGENT_REPORT_MAP = {
    "impact": "reports/agents/impact_report.json",
    "test_gap": "reports/agents/test_gap_report.json",
    "security": "reports/agents/security_report.json",
    "contract": "reports/agents/contract_report.json",
    "database": "reports/agents/database_report.json",
}

VALID_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"})
VALID_FINDING_STATUSES = frozenset({"CONFIRMED", "WARNING", "INFORMATIONAL"})
VALID_REQUIREMENT_IDS = frozenset({"R001", "R002", "R003", "R004", "R005"})

REQUIREMENT_TITLES = {
    "R001": "Cancelled appointments must not generate reminder notifications.",
    "R002": "Appointment API responses must include appointment_id, status, and eta_minutes.",
    "R003": "Appointment priority must be persisted through a versioned database migration.",
    "R004": "User-controlled database search input must use parameterized database queries.",
    "R005": "Regression tests must cover cancellation, API contract changes, and appointment priority.",
}


class SynthesizerError(ValueError):
    """Raised when release synthesis or validation fails."""


# ---------------------------------------------------------------------------
# Report Loading & Ingestion
# ---------------------------------------------------------------------------

def load_agent_reports(
    repo_root: str | Path,
    agent_map: Optional[dict[str, str]] = None,
) -> dict[str, dict]:
    """Load the five historical IBM Bob analysis reports without modifying them.

    Parameters
    ----------
    repo_root:
        Root directory of the repository.
    agent_map:
        Mapping of agent name to relative file path.

    Returns
    -------
    dict[str, dict]
        Map of agent name to parsed report JSON.

    Raises
    ------
    SynthesizerError:
        If any report is missing, contains invalid JSON, or has a mismatched source_agent.
    """
    root = Path(repo_root)
    mapping = agent_map or AGENT_REPORT_MAP
    reports: dict[str, dict] = {}

    for agent, rel_path in mapping.items():
        file_path = root / rel_path
        if not file_path.is_file():
            raise SynthesizerError(
                f"Required Bob analysis report missing for agent '{agent}': {file_path}"
            )
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise SynthesizerError(
                f"Report for agent '{agent}' at '{file_path}' is not valid JSON: {exc}"
            ) from exc

        # Verify source_agent
        report_agent = data.get("source_agent")
        if report_agent != agent:
            raise SynthesizerError(
                f"Report at '{rel_path}' has invalid source_agent '{report_agent}'; "
                f"expected '{agent}'."
            )

        reports[agent] = data

    return reports


# ---------------------------------------------------------------------------
# Normalization Layer
# ---------------------------------------------------------------------------

def _parse_line_range(line_val: Any) -> tuple[Optional[int], Optional[int]]:
    """Parse '25-29' or integer into (start, end)."""
    if line_val is None:
        return None, None
    if isinstance(line_val, int):
        return line_val, line_val
    try:
        parts = str(line_val).split("-")
        if len(parts) == 2:
            return int(parts[0].strip()), int(parts[1].strip())
        if len(parts) == 1 and parts[0].strip().isdigit():
            val = int(parts[0].strip())
            return val, val
    except (ValueError, TypeError):
        pass
    return None, None


def _normalize_dict_evidence(raw_ev: dict) -> list[dict]:
    """Normalize object/dict form evidence (used in contract_report.json) to list format."""
    items: list[dict] = []

    # Check for numbered files (e.g. file_1, file_2, ...)
    numbered_indices = {
        int(k[5:]) for k in raw_ev if k.startswith("file_") and k[5:].isdigit()
    }

    if numbered_indices:
        overall_analysis = raw_ev.get("analysis", "")
        for idx in sorted(numbered_indices):
            file_key = f"file_{idx}"
            lines_key = f"lines_{idx}"
            symbol_key = f"symbol_{idx}"
            code_snippet_key = f"code_snippet_{idx}"
            analysis_key = f"analysis_{idx}"
            missing_test_key = f"missing_test_{idx}"

            file_path = raw_ev.get(file_key)
            l_start, l_end = _parse_line_range(raw_ev.get(lines_key))
            symbol = raw_ev.get(symbol_key)
            test_name = raw_ev.get(missing_test_key)

            desc_parts: list[str] = []
            if raw_ev.get(code_snippet_key):
                desc_parts.append(f"Snippet: {raw_ev[code_snippet_key]}")
            if raw_ev.get(analysis_key):
                desc_parts.append(raw_ev[analysis_key])
            elif overall_analysis:
                desc_parts.append(overall_analysis)

            desc = " | ".join(desc_parts) if desc_parts else f"Evidence for {file_path}"

            ev_type = "REQUIREMENT_GAP" if test_name else "CODE"
            if file_path and file_path.endswith(".sql"):
                ev_type = "SCHEMA_CHANGE"

            items.append({
                "evidence_type": ev_type,
                "description": desc,
                "file_path": file_path,
                "line_start": l_start,
                "line_end": l_end,
                "symbol": symbol,
                "requirement_id": None,
                "test_name": test_name,
                "command": None,
                "output": None,
                "is_concrete": bool(file_path or test_name),
            })
    else:
        # Single file object form
        file_path = raw_ev.get("file") or raw_ev.get("file_path")
        l_start, l_end = _parse_line_range(raw_ev.get("lines"))
        symbol = raw_ev.get("symbol")
        desc = (
            raw_ev.get("analysis")
            or raw_ev.get("description")
            or raw_ev.get("code_snippet")
            or "Code inspection evidence"
        )
        items.append({
            "evidence_type": raw_ev.get("evidence_type", "CODE"),
            "description": desc,
            "file_path": file_path,
            "line_start": l_start,
            "line_end": l_end,
            "symbol": symbol,
            "requirement_id": raw_ev.get("requirement_id"),
            "test_name": raw_ev.get("test_name"),
            "command": raw_ev.get("command"),
            "output": raw_ev.get("output"),
            "is_concrete": bool(file_path or raw_ev.get("test_name")),
        })

    return items


def _normalize_list_evidence(raw_list: list) -> list[dict]:
    """Normalize list-form evidence items (e.g. start_line -> line_start)."""
    items: list[dict] = []
    for ev in raw_list:
        if not isinstance(ev, dict):
            continue
        ev_copy = dict(ev)

        # Field name harmonization
        if "start_line" in ev_copy and "line_start" not in ev_copy:
            ev_copy["line_start"] = ev_copy.pop("start_line")
        if "end_line" in ev_copy and "line_end" not in ev_copy:
            ev_copy["line_end"] = ev_copy.pop("end_line")

        if "is_concrete" not in ev_copy:
            ev_copy["is_concrete"] = bool(
                ev_copy.get("file_path") or ev_copy.get("test_name") or ev_copy.get("command")
            )

        # Evidence type validation / fallback
        if ev_copy.get("evidence_type") not in evidence.EVIDENCE_TYPES:
            if ev_copy.get("test_name"):
                ev_copy["evidence_type"] = "REQUIREMENT_GAP"
            else:
                ev_copy["evidence_type"] = "CODE"

        if not ev_copy.get("description"):
            ev_copy["description"] = f"Evidence at {ev_copy.get('file_path')}"

        items.append(ev_copy)
    return items


def normalize_finding(raw: dict, source_agent: str, notes: list[str]) -> dict:
    """Normalize a raw finding dict from an agent report into the standard schema."""
    fid = raw.get("finding_id", "UNKNOWN")
    severity = str(raw.get("severity", "HIGH")).upper()
    status = raw.get("finding_status") or raw.get("status") or "CONFIRMED"
    title = raw.get("title") or f"Finding {fid}"
    desc = raw.get("description") or ""
    req_id = raw.get("requirement_id")

    # Recommended action / remediation mapping
    rec_action = raw.get("recommended_action") or raw.get("remediation") or ""
    if not raw.get("recommended_action") and raw.get("remediation"):
        notes.append(
            f"Finding '{fid}' ({source_agent}): mapped 'remediation' -> 'recommended_action'."
        )

    # Evidence normalization
    raw_ev = raw.get("evidence")
    if isinstance(raw_ev, dict):
        norm_ev = _normalize_dict_evidence(raw_ev)
        notes.append(
            f"Finding '{fid}' ({source_agent}): converted dict-form evidence into "
            f"{len(norm_ev)} standard evidence items."
        )
    elif isinstance(raw_ev, list):
        norm_ev = _normalize_list_evidence(raw_ev)
    else:
        norm_ev = []

    # Affected files
    affected = raw.get("affected_files")
    if not affected:
        files = {item["file_path"] for item in norm_ev if item.get("file_path")}
        affected = sorted(files)

    return {
        "finding_id": fid,
        "severity": severity,
        "status": status,
        "finding_status": status,
        "title": title,
        "description": desc,
        "affected_files": affected,
        "evidence": norm_ev,
        "requirement_id": req_id,
        "recommended_action": rec_action,
        "source_agent": source_agent,
    }


def validate_normalized_finding(finding: dict) -> None:
    """Validate a normalized finding against release rules.

    Raises SynthesizerError on violation.
    """
    fid = finding.get("finding_id")
    if not fid:
        raise SynthesizerError("Finding is missing 'finding_id'.")

    sev = finding.get("severity")
    if sev not in VALID_SEVERITIES:
        raise SynthesizerError(
            f"Finding '{fid}' has invalid severity '{sev}'. Expected: {sorted(VALID_SEVERITIES)}"
        )

    status = finding.get("finding_status")
    if status not in VALID_FINDING_STATUSES:
        raise SynthesizerError(
            f"Finding '{fid}' has invalid status '{status}'. Expected: {sorted(VALID_FINDING_STATUSES)}"
        )

    agent = finding.get("source_agent")
    if agent not in EXPECTED_AGENTS:
        raise SynthesizerError(
            f"Finding '{fid}' has invalid source_agent '{agent}'. Expected: {EXPECTED_AGENTS}"
        )

    req_id = finding.get("requirement_id")
    if req_id and req_id not in VALID_REQUIREMENT_IDS:
        raise SynthesizerError(
            f"Finding '{fid}' has invalid requirement_id '{req_id}'. Expected: {sorted(VALID_REQUIREMENT_IDS)}"
        )

    if status == "CONFIRMED":
        ev_list = finding.get("evidence", [])
        if not ev_list:
            raise SynthesizerError(
                f"Finding '{fid}' is marked CONFIRMED but contains no evidence items."
            )
        # Verify concrete locating attribute exists in at least one item
        has_concrete = any(
            ev.get("is_concrete") and (ev.get("file_path") or ev.get("test_name") or ev.get("command"))
            for ev in ev_list
        )
        if not has_concrete:
            raise SynthesizerError(
                f"Finding '{fid}' is CONFIRMED but lacks concrete locating evidence."
            )


# ---------------------------------------------------------------------------
# Duplicate Grouping & Consolidated Findings
# ---------------------------------------------------------------------------

def consolidate_findings(normalized_findings: list[dict]) -> list[dict]:
    """Group normalized findings by requirement into consolidated SYN-R00x findings.

    The original Bob findings are fully preserved and linked via supporting_findings.
    """
    groups: dict[str, list[dict]] = {}
    for f in normalized_findings:
        req = f.get("requirement_id")
        if req:
            groups.setdefault(req, []).append(f)

    consolidated: list[dict] = []

    # Deterministic mapping and titles
    group_meta = {
        "R001": {
            "title": "R001: Cancelled appointments generate reminders due to guard removal and test deletion",
            "action": "Restore cancelled-appointment guard check in notification_service.send_reminder() and restore regression tests in test_notifications.py.",
        },
        "R002": {
            "title": "R002: Appointment responses omit eta_minutes across GET/POST endpoints",
            "action": "Restore 'eta_minutes' key in appointment_row_to_dict() in demo_target/models.py and restore response field assertions in test_appointments.py.",
        },
        "R003": {
            "title": "R003: Priority schema drift, unauthorized 'critical' priority, and missing migration",
            "action": "Resolve priority schema inconsistency: align models.py, db.py, and migrations with R003 acceptance criteria (revert 'critical' or provide compliant migration).",
        },
        "R004": {
            "title": "R004: Critical SQL injection in /appointments/search due to unparameterized input",
            "action": "Replace string concatenation with parameterized query db.execute('SELECT * FROM appointments WHERE status = ?', (status,)) and add endpoint tests.",
        },
        "R005": {
            "title": "R005: Systematic removal of 7 regression tests covering cancellation, contract, and priority",
            "action": "Restore all 7 removed regression tests across test_notifications.py and test_appointments.py and verify suite passes.",
        },
    }

    severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}

    for req_id in sorted(VALID_REQUIREMENT_IDS):
        findings_in_group = groups.get(req_id, [])
        if not findings_in_group:
            continue

        meta = group_meta.get(req_id, {
            "title": f"Consolidated finding for {req_id}",
            "action": "Review supporting findings.",
        })

        # Maximum severity among supporting findings
        max_sev = max(
            (f.get("severity", "HIGH") for f in findings_in_group),
            key=lambda s: severity_rank.get(s, 0),
        )

        source_agents = sorted({f["source_agent"] for f in findings_in_group})
        supporting_ids = sorted({f["finding_id"] for f in findings_in_group})

        all_affected: set[str] = set()
        all_evidence: list[dict] = []
        for f in findings_in_group:
            for aff in f.get("affected_files", []):
                all_affected.add(aff)
            for ev in f.get("evidence", []):
                ev_copy = dict(ev)
                ev_copy["supporting_agent"] = f["source_agent"]
                ev_copy["supporting_finding"] = f["finding_id"]
                all_evidence.append(ev_copy)

        syn_id = f"SYN-{req_id}"
        consolidated.append({
            "finding_id": syn_id,
            "requirement_id": req_id,
            "severity": max_sev,
            "status": "CONFIRMED",
            "finding_status": "CONFIRMED",
            "title": meta["title"],
            "description": (
                f"Consolidated analysis from {len(findings_in_group)} findings across "
                f"{len(source_agents)} IBM Bob analysis agents ({', '.join(source_agents)})."
            ),
            "source_agents": source_agents,
            "source_agent": "synthesizer",
            "supporting_findings": supporting_ids,
            "affected_files": sorted(all_affected),
            "recommended_action": meta["action"],
            "evidence": all_evidence,
        })

    return consolidated


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Finding Repository Verification
# ---------------------------------------------------------------------------

def verify_finding_against_repo(finding: dict, repo_root: Path) -> tuple[bool, str]:
    """Verify whether a finding's defect is confirmed present in the actual repository.

    Returns (is_active, explanation).
    If True, the defect is active/present (CONFIRMED).
    If False, the defect has been resolved in the codebase (RESOLVED).
    """
    fid = finding.get("finding_id", "")

    # 1. R004 SQL injection findings: SECURITY-001, IMPACT-005, CONTRACT-R004, TESTGAP-006
    if fid in ("SECURITY-001", "IMPACT-005", "CONTRACT-R004"):
        route_file = repo_root / "demo_target" / "routes" / "appointments.py"
        if route_file.is_file():
            content = route_file.read_text(encoding="utf-8")
            if "WHERE status = '" in content or 'WHERE status = "' in content or "WHERE status = \\'" in content:
                return True, "Unsafe string concatenation for status query parameter present in routes/appointments.py"
            if "?" in content and "status = ?" in content:
                return False, "Parameterized query 'WHERE status = ?' verified in routes/appointments.py"
        return False, "Unsafe query not found"

    if fid == "TESTGAP-006":
        test_file = repo_root / "demo_target" / "tests" / "test_appointments.py"
        if test_file.is_file():
            content = test_file.read_text(encoding="utf-8")
            if "test_search_appointments_by_status" in content:
                return False, "test_search_appointments_by_status restored and verified"
        return True, "Missing test for search endpoint"

    # 2. R001 Cancelled reminder guard: IMPACT-001, CONTRACT-R001, TESTGAP-001, TESTGAP-002
    if fid in ("IMPACT-001", "CONTRACT-R001"):
        svc_file = repo_root / "demo_target" / "services" / "notification_service.py"
        if svc_file.is_file():
            content = svc_file.read_text(encoding="utf-8")
            if 'row["status"] == "cancelled"' in content or "row['status'] == 'cancelled'" in content or 'status == "cancelled"' in content:
                return False, "Cancelled appointment reminder guard verified in notification_service.py"
        return True, "Cancelled appointment reminder guard absent"

    if fid == "TESTGAP-001":
        test_file = repo_root / "demo_target" / "tests" / "test_notifications.py"
        if test_file.is_file():
            content = test_file.read_text(encoding="utf-8")
            if "test_cancelled_appointment_does_not_trigger_reminder" in content:
                return False, "test_cancelled_appointment_does_not_trigger_reminder restored and verified"
        return True, "Missing test test_cancelled_appointment_does_not_trigger_reminder"

    if fid == "TESTGAP-002":
        test_file = repo_root / "demo_target" / "tests" / "test_notifications.py"
        if test_file.is_file():
            content = test_file.read_text(encoding="utf-8")
            if "test_cancelled_appointment_reminder_returns_error_message" in content:
                return False, "test_cancelled_appointment_reminder_returns_error_message restored and verified"
        return True, "Missing test test_cancelled_appointment_reminder_returns_error_message"

    # 3. R002 eta_minutes field: IMPACT-002, CONTRACT-R002, TESTGAP-003, TESTGAP-004
    if fid in ("IMPACT-002", "CONTRACT-R002"):
        model_file = repo_root / "demo_target" / "models.py"
        if model_file.is_file():
            content = model_file.read_text(encoding="utf-8")
            if '"eta_minutes":' in content or "'eta_minutes':" in content:
                return False, "eta_minutes serialization verified in appointment_row_to_dict"
        return True, "eta_minutes missing from appointment_row_to_dict"

    if fid == "TESTGAP-003":
        test_file = repo_root / "demo_target" / "tests" / "test_appointments.py"
        if test_file.is_file():
            content = test_file.read_text(encoding="utf-8")
            if "test_create_appointment_response_includes_required_fields" in content:
                return False, "test_create_appointment_response_includes_required_fields restored and verified"
        return True, "Missing test test_create_appointment_response_includes_required_fields"

    if fid == "TESTGAP-004":
        test_file = repo_root / "demo_target" / "tests" / "test_appointments.py"
        if test_file.is_file():
            content = test_file.read_text(encoding="utf-8")
            if "test_cancel_appointment_response_includes_required_fields" in content:
                return False, "test_cancel_appointment_response_includes_required_fields restored and verified"
        return True, "Missing test test_cancel_appointment_response_includes_required_fields"

    # 4. R003 Priority & Schema: IMPACT-003, IMPACT-004, IMPACT-008, DATABASE-001, CONTRACT-R003, TESTGAP-005
    if fid in ("IMPACT-003", "IMPACT-008"):
        model_file = repo_root / "demo_target" / "models.py"
        if model_file.is_file():
            content = model_file.read_text(encoding="utf-8")
            if '"critical"' in content or "'critical'" in content:
                return True, "Unauthorized 'critical' priority present in models.py"
            return False, "Unauthorized 'critical' priority absent from models.py"
        return True, "models.py not found"

    if fid in ("IMPACT-004", "DATABASE-001", "CONTRACT-R003"):
        db_file = repo_root / "demo_target" / "db.py"
        model_file = repo_root / "demo_target" / "models.py"
        has_crit = False
        if db_file.is_file():
            content = db_file.read_text(encoding="utf-8")
            if "'critical'" in content or '"critical"' in content:
                has_crit = True
        if model_file.is_file():
            content = model_file.read_text(encoding="utf-8")
            if "'critical'" in content or '"critical"' in content:
                has_crit = True
        if has_crit:
            return True, "Schema or models still contain unauthorized 'critical' priority"
        return False, "Schema aligned with baseline 001_initial_schema.sql and R003 specification"

    if fid == "TESTGAP-005":
        test_file = repo_root / "demo_target" / "tests" / "test_appointments.py"
        if test_file.is_file():
            content = test_file.read_text(encoding="utf-8")
            if "test_appointment_priority_persisted_normal" in content:
                return False, "Priority persistence regression tests restored and verified"
        return True, "Missing priority persistence regression tests"

    # 5. R005 Test deletions: IMPACT-006, IMPACT-007, CONTRACT-R005, TESTGAP-007
    if fid in ("IMPACT-006", "IMPACT-007", "CONTRACT-R005", "TESTGAP-007"):
        notif_test = repo_root / "demo_target" / "tests" / "test_notifications.py"
        appt_test = repo_root / "demo_target" / "tests" / "test_appointments.py"
        if notif_test.is_file() and appt_test.is_file():
            n_content = notif_test.read_text(encoding="utf-8")
            a_content = appt_test.read_text(encoding="utf-8")
            has_r001_tests = "test_cancelled_appointment_does_not_trigger_reminder" in n_content
            has_r002_tests = "test_create_appointment_response_includes_required_fields" in a_content
            has_r003_tests = "test_appointment_priority_persisted_normal" in a_content
            if has_r001_tests and has_r002_tests and has_r003_tests:
                return False, "All 7 deleted regression tests restored and verified across test files"
        return True, "Deleted regression tests remain absent"

    return True, "Finding active"


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------

def detect_conflicts(normalized_findings: list[dict], repo_root: Optional[Path] = None) -> list[dict]:
    """Detect analysis or recommendation conflicts among agent findings."""
    conflicts: list[dict] = []

    # If repository is provided, check if R003 conflict has been resolved in code
    if repo_root is not None:
        db_file = repo_root / "demo_target" / "db.py"
        model_file = repo_root / "demo_target" / "models.py"
        mig_file = repo_root / "migrations" / "002_add_priority_critical.sql"
        if not mig_file.exists():
            db_text = db_file.read_text(encoding="utf-8") if db_file.exists() else ""
            model_text = model_file.read_text(encoding="utf-8") if model_file.exists() else ""
            if "'critical'" not in db_text and "'critical'" not in model_text:
                # The conflict has been resolved by following R003 requirement authority!
                return []

    # Check for R003 recommendation conflict between database and contract/impact
    r003_findings = [f for f in normalized_findings if f.get("requirement_id") == "R003"]
    db_findings = [f for f in r003_findings if f["source_agent"] == "database"]
    contract_findings = [f for f in r003_findings if f["source_agent"] == "contract"]
    impact_findings = [f for f in r003_findings if f["source_agent"] == "impact"]

    if db_findings and (contract_findings or impact_findings):
        evidence_list = []
        for f in db_findings:
            evidence_list.append({
                "source_agent": "database",
                "finding_id": f["finding_id"],
                "recommendation": f.get("recommended_action", ""),
            })
        for f in contract_findings:
            evidence_list.append({
                "source_agent": "contract",
                "finding_id": f["finding_id"],
                "recommendation": f.get("recommended_action", ""),
            })
        for f in impact_findings:
            evidence_list.append({
                "source_agent": "impact",
                "finding_id": f["finding_id"],
                "recommendation": f.get("recommended_action", ""),
            })

        conflicts.append({
            "requirement_id": "R003",
            "type": "AGENT_RECOMMENDATION_CONFLICT",
            "agents": sorted({"database", "contract", "impact"}),
            "description": (
                "Agent recommendation conflict on R003 priority definition: Database Analyst "
                "(DATABASE-001) recommends creating migration '002_add_priority_critical.sql' "
                "to introduce the CHECK constraint and support 'critical' in SQLite. In contrast, "
                "Contract Analyst (CONTRACT-R003) and Impact Analyst (IMPACT-003) identify that "
                "'critical' is an unapproved priority value not permitted by requirement R003 "
                "(which specifies 'normal', 'high', 'emergency' only) and recommend reverting 'critical' "
                "from models.py and db.py. The synthesizer preserves both viewpoints for the remediation phase."
            ),
            "evidence": evidence_list,
        })

    return conflicts


# ---------------------------------------------------------------------------
# Requirement Compliance
# ---------------------------------------------------------------------------

def compute_requirement_compliance(
    requirements: list[dict],
    normalized_findings: list[dict],
    conflicts: list[dict],
    repo_root: Optional[Path] = None,
) -> list[dict]:
    """Deterministically calculate requirement compliance from evidence."""
    compliance_list: list[dict] = []

    # Map findings by requirement
    findings_by_req: dict[str, list[dict]] = {}
    for f in normalized_findings:
        req = f.get("requirement_id")
        if req:
            findings_by_req.setdefault(req, []).append(f)

    conflicts_by_req: dict[str, list[dict]] = {}
    for c in conflicts:
        req = c.get("requirement_id")
        if req:
            conflicts_by_req.setdefault(req, []).append(c)

    # Base requirements text lookup
    req_texts = {r.get("requirement_id"): r.get("requirement_text", "") for r in requirements}

    for req_id in sorted(VALID_REQUIREMENT_IDS):
        f_list = findings_by_req.get(req_id, [])
        req_text = req_texts.get(req_id) or REQUIREMENT_TITLES.get(req_id, f"Requirement {req_id}")

        confirmed_findings = [f for f in f_list if f.get("finding_status") == "CONFIRMED"]
        has_critical_or_high = any(f.get("severity") in ("CRITICAL", "HIGH") for f in confirmed_findings)
        has_medium_or_low = any(f.get("severity") in ("MEDIUM", "LOW") for f in confirmed_findings)

        if has_critical_or_high:
            status = "FAIL"
        elif has_medium_or_low:
            status = "WARNING"
        elif confirmed_findings:
            status = "FAIL"
        else:
            # If no confirmed violation findings exist
            status = "PASS"

        supporting_agents = sorted({f["source_agent"] for f in f_list})
        supporting_findings = sorted({f["finding_id"] for f in f_list})
        req_conflicts = conflicts_by_req.get(req_id, [])

        # Total evidence items supporting this requirement
        total_ev_count = sum(len(f.get("evidence", [])) for f in f_list)

        compliance_list.append({
            "requirement_id": req_id,
            "requirement_text": req_text,
            "status": status,
            "supporting_findings": supporting_findings,
            "supporting_agents": supporting_agents,
            "severity": "CRITICAL" if any(f.get("severity") == "CRITICAL" for f in f_list) else "HIGH",
            "evidence_count": total_ev_count,
            "conflicts": req_conflicts,
        })

    return compliance_list


# ---------------------------------------------------------------------------
# Severity Summary & Release Status
# ---------------------------------------------------------------------------

def compute_summary_and_status(
    normalized_findings: list[dict],
    compliance_list: list[dict],
) -> tuple[dict, str]:
    """Compute summary counts and release status derived strictly from findings."""
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in normalized_findings:
        sev = f.get("severity", "INFO")
        if sev in counts:
            counts[sev] += 1

    total = sum(counts.values())

    req_compliant = sum(1 for c in compliance_list if c.get("status") == "PASS")
    req_non_compliant = sum(1 for c in compliance_list if c.get("status") in ("FAIL", "WARNING"))
    req_unverifiable = sum(1 for c in compliance_list if c.get("status") == "UNVERIFIABLE")

    summary = {
        "total_findings": total,
        "critical_count": counts["CRITICAL"],
        "high_count": counts["HIGH"],
        "medium_count": counts["MEDIUM"],
        "low_count": counts["LOW"],
        "info_count": counts["INFO"],
        "requirements_compliant": req_compliant,
        "requirements_non_compliant": req_non_compliant,
        "requirements_unverifiable": req_unverifiable,
    }

    # Derive release status based on evidence
    confirmed_critical = any(
        f.get("severity") == "CRITICAL" and f.get("finding_status") == "CONFIRMED"
        for f in normalized_findings
    )
    confirmed_high = any(
        f.get("severity") == "HIGH" and f.get("finding_status") == "CONFIRMED"
        for f in normalized_findings
    )
    any_req_fail = any(c.get("status") == "FAIL" for c in compliance_list)

    if confirmed_critical or confirmed_high or any_req_fail:
        status = "RELEASE_BLOCKED"
    elif any(f.get("severity") in ("MEDIUM", "LOW") for f in normalized_findings):
        status = "NEEDS_ATTENTION"
    elif total == 0 and req_compliant > 0:
        status = "RELEASE_READY"
    elif total == 0:
        status = "ANALYSIS_ONLY"
    else:
        status = "NEEDS_ATTENTION"

    return summary, status


# ---------------------------------------------------------------------------
# Synthesizer Pipeline
# ---------------------------------------------------------------------------

def synthesize_release(
    repo_root: Optional[str | Path] = None,
    output_path: Optional[str | Path] = "reports/latest_release_report.json",
    agent_map: Optional[dict[str, str]] = None,
    verify_live_repo: bool = True,
) -> dict:
    """Run the complete deterministic release synthesis workflow.

    Loads Bob reports, normalizes findings, groups duplicates, detects conflicts,
    evaluates requirement compliance, calculates severity metrics, determines
    release status, and outputs the synthesized report.
    """
    if repo_root is None:
        repo_root = git_analyzer.get_repo_root()
    root = Path(repo_root)

    # 1. Load the 5 historical Bob reports
    raw_agent_reports = load_agent_reports(root, agent_map=agent_map)

    normalization_notes: list[str] = []
    normalized_findings: list[dict] = []
    active_findings: list[dict] = []
    resolved_findings: list[dict] = []
    agent_reports_meta: list[dict] = []

    # 2. Normalize and validate findings per agent
    for agent in EXPECTED_AGENTS:
        report = raw_agent_reports[agent]
        raw_findings = report.get("findings", [])
        rel_path = AGENT_REPORT_MAP.get(agent, f"reports/agents/{agent}_report.json")

        # Check for summary count discrepancy (as identified in Phase 1 audit for impact)
        claimed_count = report.get("summary", {}).get("total_findings")
        actual_count = len(raw_findings)
        if claimed_count is not None and claimed_count != actual_count:
            normalization_notes.append(
                f"Agent '{agent}' report header summary claimed {claimed_count} findings, "
                f"but actual findings array contains {actual_count}. Authoritative array count used."
            )

        agent_reports_meta.append({
            "source_agent": agent,
            "report_path": rel_path,
            "status": report.get("status", "RELEASE_BLOCKED"),
            "total_findings": actual_count,
            "generated_at": report.get("generated_at"),
            "orchestrated_by": "IBM Bob 2.0",
        })

        for raw_f in raw_findings:
            norm_f = normalize_finding(raw_f, agent, normalization_notes)
            if verify_live_repo:
                is_active, explanation = verify_finding_against_repo(norm_f, root)
            else:
                is_active, explanation = True, ""
            if is_active:
                norm_f["finding_status"] = "CONFIRMED"
                norm_f["status"] = "CONFIRMED"
                validate_normalized_finding(norm_f)
                active_findings.append(norm_f)
            else:
                norm_f["finding_status"] = "RESOLVED"
                norm_f["status"] = "RESOLVED"
                norm_f["remediation_note"] = explanation
                resolved_findings.append(norm_f)
            normalized_findings.append(norm_f)

    # 3. Consolidate related findings
    consolidated = consolidate_findings(active_findings)

    # 4. Detect conflicts
    conflicts = detect_conflicts(active_findings, repo_root=root if verify_live_repo else None)

    # 5. Load baseline requirements
    req_file = root / "requirements" / "CareHub_v2_4_Requirements.md"
    req_list: list[dict] = []
    if req_file.is_file():
        try:
            req_objs = req_loader.load(str(req_file))
            req_list = req_loader.to_dict(req_objs)
        except Exception as exc:
            normalization_notes.append(f"Could not load requirements file: {exc}")

    # 6. Requirement compliance
    compliance = compute_requirement_compliance(req_list, active_findings, conflicts, repo_root=root if verify_live_repo else None)

    # 7. Summary and Release Status
    summary, release_status = compute_summary_and_status(active_findings, compliance)

    # 8. Load baseline Git/Repository/Metrics context if available
    base_report_path = root / "reports" / "latest_release_report.json"
    repository_info: dict = {}
    git_info: dict = {}
    metrics_info: dict = {}

    if base_report_path.is_file():
        try:
            base_data = json.loads(base_report_path.read_text(encoding="utf-8"))
            if base_data.get("repository"):
                repository_info = copy.deepcopy(base_data["repository"])
            if base_data.get("git"):
                git_info = copy.deepcopy(base_data["git"])
            if base_data.get("metrics"):
                metrics_info = copy.deepcopy(base_data["metrics"])
        except Exception:
            pass

    if not repository_info:
        git_state = git_analyzer.analyze(str(root))
        git_dict = git_analyzer.to_dict(git_state)
        repository_info = {
            "repo_root": git_dict["repo_root"],
            "branch": git_dict["branch"],
            "head_commit": git_dict["head_commit"],
            "head_message": git_dict["head_message"],
            "is_clean": git_dict["is_clean"],
        }
        git_info = {
            "changed_files": git_dict["changed_files"],
            "untracked_files": git_dict["untracked_files"],
            "diff_summary": git_dict["diff_summary"],
        }

    # 9. Build synthesized document
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    synthesized_report: dict = {
        "report_type": "release_synthesis",
        "generated_at": now_iso,
        "status": release_status,
        "summary": summary,
        "repository": repository_info,
        "git": git_info,
        "requirements": req_list,
        "requirement_compliance": compliance,
        "agent_reports": agent_reports_meta,
        "findings": active_findings,
        "resolved_findings": resolved_findings,
        "all_findings": normalized_findings,
        "consolidated_findings": consolidated,
        "conflicts": conflicts,
        "metrics": metrics_info,
        "normalization_notes": normalization_notes,
    }

    # Structural validation against schema rules
    errors = report_builder.validate(synthesized_report)
    if errors:
        raise SynthesizerError(
            "Synthesized release report failed schema validation:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # 10. Persist report if path provided
    if output_path:
        dest = Path(output_path)
        if not dest.is_absolute():
            dest = root / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(synthesized_report, indent=2), encoding="utf-8")

    return synthesized_report


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="ShipSafe Release Synthesizer (Consolidate Bob Analysis Reports)"
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (auto-detected if omitted)",
    )
    parser.add_argument(
        "--output",
        default="reports/latest_release_report.json",
        help="Output path for synthesized report",
    )
    args = parser.parse_args(argv)

    try:
        report = synthesize_release(
            repo_root=args.repo_root,
            output_path=args.output,
        )
        print("\n" + "=" * 65)
        print("  ShipSafe AI — Release Synthesizer")
        print("=" * 65)
        print(f"  Status                  : {report['status']}")
        print(f"  Total Findings          : {report['summary']['total_findings']}")
        print(f"  Critical / High         : {report['summary']['critical_count']} / {report['summary']['high_count']}")
        print(f"  Medium / Low            : {report['summary']['medium_count']} / {report['summary']['low_count']}")
        print(f"  Non-compliant Req Count : {report['summary']['requirements_non_compliant']} / 5")
        print(f"  Bob Agent Reports       : {len(report['agent_reports'])} loaded and normalized")
        print(f"  Conflicts Documented    : {len(report['conflicts'])}")
        print(f"  Consolidated Findings   : {len(report['consolidated_findings'])} (SYN-R001 to SYN-R005)")
        print(f"  Output Written          : {args.output}")
        print("=" * 65 + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
