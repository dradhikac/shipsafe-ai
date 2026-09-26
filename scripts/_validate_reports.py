#!/usr/bin/env python3
"""Quick structural validation of the five agent reports."""
import json
import sys

REPORTS = {
    "impact":   "reports/agents/impact_report.json",
    "test_gap": "reports/agents/test_gap_report.json",
    "security": "reports/agents/security_report.json",
    "contract": "reports/agents/contract_report.json",
    "database": "reports/agents/database_report.json",
}

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
VALID_STATUSES = {"RELEASE_READY", "NEEDS_ATTENTION", "RELEASE_BLOCKED", "ANALYSIS_ONLY"}
VALID_FINDING_STATUSES = {"CONFIRMED", "WARNING", "INFORMATIONAL"}
VALID_REQ_IDS = {"R001", "R002", "R003", "R004", "R005", None}

errors = []
summaries = []

for agent, path in REPORTS.items():
    try:
        r = json.loads(open(path, encoding="utf-8").read())
    except Exception as exc:
        errors.append(f"{agent}: PARSE ERROR — {exc}")
        continue

    # Required top-level fields
    for field in ("report_type", "generated_at", "status", "summary", "findings", "metrics"):
        if field not in r:
            errors.append(f"{agent}: missing top-level field '{field}'")

    if r.get("status") not in VALID_STATUSES:
        errors.append(f"{agent}: invalid status '{r.get('status')}'")

    if r.get("source_agent") != agent:
        errors.append(f"{agent}: source_agent='{r.get('source_agent')}' expected '{agent}'")

    # Validate findings
    for finding in r.get("findings", []):
        fid = finding.get("finding_id", "?")

        sev = finding.get("severity")
        if sev not in VALID_SEVERITIES:
            errors.append(f"{agent}/{fid}: invalid severity '{sev}'")

        fs = finding.get("finding_status")
        if fs not in VALID_FINDING_STATUSES:
            errors.append(f"{agent}/{fid}: invalid finding_status '{fs}'")

        if fs == "CONFIRMED" and not finding.get("evidence"):
            errors.append(f"{agent}/{fid}: CONFIRMED but no evidence")

        req = finding.get("requirement_id")
        if req not in VALID_REQ_IDS:
            errors.append(f"{agent}/{fid}: invalid requirement_id '{req}'")

        sa = finding.get("source_agent")
        if sa != agent:
            errors.append(f"{agent}/{fid}: source_agent='{sa}' expected '{agent}'")

    nf = len(r.get("findings", []))
    summaries.append((agent, r.get("status", "?"), nf, r.get("source_agent", "?")))

print("\n=== Agent Report Validation ===\n")
print(f"{'Agent':<12} {'Status':<22} {'Findings':>8}  Source Agent")
print("-" * 60)
for agent, status, nf, sa in summaries:
    print(f"{agent:<12} {status:<22} {nf:>8}  {sa}")

if errors:
    print(f"\nFailed — {len(errors)} error(s):")
    for e in errors:
        print(f"  ERROR: {e}")
    sys.exit(1)
else:
    print(f"\nAll {len(summaries)} reports pass structural validation.")
