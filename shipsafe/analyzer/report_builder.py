"""ShipSafe report builder.

Provides deterministic functions to create, populate, validate, merge, save,
and load ShipSafe release reports.

This module is purely structural — it does not perform AI-based analysis or
synthesise findings.  It is infrastructure for the future Release Synthesizer
and the five Bob analysis agents.

Report format conforms to shipsafe/schemas/report_schema.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"})
VALID_STATUSES = frozenset({"RELEASE_READY", "NEEDS_ATTENTION",
                             "RELEASE_BLOCKED", "ANALYSIS_ONLY"})
VALID_FINDING_STATUSES = frozenset({"CONFIRMED", "WARNING", "INFORMATIONAL"})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ReportError(ValueError):
    """Raised when a report fails structural validation."""


class DuplicateFindingError(ReportError):
    """Raised when a duplicate finding_id is encountered during merge."""


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

def create_empty(
    report_type: str = "base_analysis",
    status: str = "ANALYSIS_ONLY",
) -> dict:
    """Return a valid empty report document.

    Parameters
    ----------
    report_type:
        One of: ``base_analysis``, ``agent_report``, ``synthesized_report``.
    status:
        Initial release status.  Defaults to ``ANALYSIS_ONLY``.

    Returns
    -------
    dict
        A JSON-compatible report dict with empty findings and zeroed summary.
    """
    if status not in VALID_STATUSES:
        raise ReportError(
            f"Invalid status '{status}'. Valid values: {sorted(VALID_STATUSES)}"
        )
    return {
        "report_type": report_type,
        "generated_at": _now(),
        "status": status,
        "summary": {
            "total_findings": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "info_count": 0,
            "requirements_compliant": 0,
            "requirements_non_compliant": 0,
            "requirements_unverifiable": 0,
        },
        "findings": [],
        "metrics": {},
        "repository": {},
        "git": {},
        "requirements": [],
        "test_analysis": {},
    }


# ---------------------------------------------------------------------------
# Finding management
# ---------------------------------------------------------------------------

def _validate_finding(finding: dict) -> None:
    """Validate a finding dict before adding it to a report."""
    required = ("finding_id", "severity", "title", "finding_status", "source_agent")
    for key in required:
        if key not in finding:
            raise ReportError(f"Finding is missing required field: '{key}'")

    if finding["severity"] not in VALID_SEVERITIES:
        raise ReportError(
            f"Finding '{finding['finding_id']}' has invalid severity "
            f"'{finding['severity']}'. Valid: {sorted(VALID_SEVERITIES)}"
        )

    if finding["finding_status"] not in VALID_FINDING_STATUSES:
        raise ReportError(
            f"Finding '{finding['finding_id']}' has invalid finding_status "
            f"'{finding['finding_status']}'. "
            f"Valid: {sorted(VALID_FINDING_STATUSES)}"
        )

    # CONFIRMED findings must have at least one evidence item
    if finding["finding_status"] == "CONFIRMED":
        evidence = finding.get("evidence", [])
        if not evidence:
            raise ReportError(
                f"Finding '{finding['finding_id']}' is CONFIRMED but has no "
                "evidence. Confirmed findings must have at least one evidence "
                "record (see AGENTS.md no-invention rule)."
            )


def add_finding(report: dict, finding: dict) -> None:
    """Add a validated finding to a report in-place.

    Parameters
    ----------
    report:
        The report dict to mutate.
    finding:
        The finding dict to add.

    Raises
    ------
    ReportError
        If the finding is structurally invalid.
    DuplicateFindingError
        If a finding with the same ``finding_id`` already exists in the report.
    """
    _validate_finding(finding)

    existing_ids = {f["finding_id"] for f in report.get("findings", [])}
    if finding["finding_id"] in existing_ids:
        raise DuplicateFindingError(
            f"Duplicate finding_id '{finding['finding_id']}'. "
            "Use a unique ID for each finding."
        )

    report.setdefault("findings", []).append(finding)
    _recompute_summary(report)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def set_metrics(report: dict, metrics: dict) -> None:
    """Attach a metrics dict to the report in-place."""
    report["metrics"] = metrics


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(report: dict) -> list[str]:
    """Validate the report structure and return a list of error messages.

    Returns an empty list if the report is valid.
    """
    errors: list[str] = []

    for field in ("report_type", "generated_at", "status", "summary",
                  "findings", "metrics"):
        if field not in report:
            errors.append(f"Missing required top-level field: '{field}'")

    if "status" in report and report["status"] not in VALID_STATUSES:
        errors.append(f"Invalid status: '{report['status']}'")

    for i, finding in enumerate(report.get("findings", [])):
        try:
            _validate_finding(finding)
        except ReportError as exc:
            errors.append(f"Finding[{i}]: {exc}")

    return errors


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge(base: dict, *fragments: dict) -> dict:
    """Merge one or more report fragments into a base report.

    Rules:
    - Findings are merged by ``finding_id``.
    - If the same ``finding_id`` appears in two fragments with different
      content, a :class:`DuplicateFindingError` is raised rather than
      silently choosing one.
    - Findings from fragments are appended to the base findings list.
    - ``metrics``, ``repository``, ``git``, ``requirements``, and
      ``test_analysis`` from the last fragment that provides them are used.
    - ``generated_at`` is updated to now.
    - ``status`` is escalated to the most severe value seen.

    Returns a new merged report dict (the input dicts are not mutated).
    """
    import copy
    result = copy.deepcopy(base)
    result["generated_at"] = _now()

    for fragment in fragments:
        # Merge findings
        existing_by_id: dict[str, dict] = {
            f["finding_id"]: f for f in result.get("findings", [])
        }
        for finding in fragment.get("findings", []):
            fid = finding["finding_id"]
            if fid in existing_by_id:
                if existing_by_id[fid] != finding:
                    raise DuplicateFindingError(
                        f"Conflicting content for finding_id '{fid}' during "
                        "merge. Resolve the conflict before merging."
                    )
                # Identical — skip (idempotent)
            else:
                _validate_finding(finding)
                result["findings"].append(finding)
                existing_by_id[fid] = finding

        # Merge scalar sections — last writer wins
        for section in ("metrics", "repository", "git",
                        "requirements", "test_analysis"):
            if section in fragment and fragment[section]:
                result[section] = copy.deepcopy(fragment[section])

        # Escalate status
        result["status"] = _escalate_status(
            result.get("status", "ANALYSIS_ONLY"),
            fragment.get("status", "ANALYSIS_ONLY"),
        )

    _recompute_summary(result)
    return result


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save(report: dict, path: str) -> None:
    """Save a report to a JSON file.

    Creates parent directories if they do not exist.

    Raises
    ------
    ReportError
        If the report has structural errors.
    """
    errors = validate(report)
    if errors:
        raise ReportError(
            "Cannot save invalid report:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")


def load(path: str) -> dict:
    """Load a report from a JSON file.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    json.JSONDecodeError
        If the file is not valid JSON.
    ReportError
        If the loaded report has structural errors.
    """
    text = Path(path).read_text(encoding="utf-8")
    report = json.loads(text)
    errors = validate(report)
    if errors:
        raise ReportError(
            f"Loaded report from '{path}' has structural errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_STATUS_ORDER = ["ANALYSIS_ONLY", "RELEASE_READY",
                 "NEEDS_ATTENTION", "RELEASE_BLOCKED"]


def _escalate_status(current: str, incoming: str) -> str:
    """Return the more severe of two status values."""
    ci = _STATUS_ORDER.index(current) if current in _STATUS_ORDER else 0
    ii = _STATUS_ORDER.index(incoming) if incoming in _STATUS_ORDER else 0
    return _STATUS_ORDER[max(ci, ii)]


def _recompute_summary(report: dict) -> None:
    """Recompute the summary counts from the current findings list."""
    counts: dict[str, int] = {
        "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0
    }
    for f in report.get("findings", []):
        sev = f.get("severity", "INFO")
        if sev in counts:
            counts[sev] += 1

    total = sum(counts.values())
    report["summary"] = {
        "total_findings": total,
        "critical_count": counts["CRITICAL"],
        "high_count": counts["HIGH"],
        "medium_count": counts["MEDIUM"],
        "low_count": counts["LOW"],
        "info_count": counts["INFO"],
        "requirements_compliant": report.get("summary", {}).get("requirements_compliant", 0),
        "requirements_non_compliant": report.get("summary", {}).get("requirements_non_compliant", 0),
        "requirements_unverifiable": report.get("summary", {}).get("requirements_unverifiable", 0),
    }
