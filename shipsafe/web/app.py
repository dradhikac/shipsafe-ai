"""ShipSafe AI Web Dashboard.

Provides an enterprise DevSecOps dashboard and read-only REST API visualizing:
- Release status & executive summary
- Five IBM Bob 2.0 specialized analysis agent reports
- Requirement-to-code traceability & R003 conflict resolution
- Synthesized findings with filtering by severity, requirement, and agent
- Release impact simulation & regression flow visualization
- Before/after metric comparison (Baseline vs Bad Release)
- Prioritized remediation plan
- Detailed audit trail inspection
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request, abort


def get_repo_root() -> Path:
    """Locate the repository root directory."""
    # From shipsafe/web/app.py -> repo root is 2 levels up
    return Path(__file__).resolve().parent.parent.parent


REPORT_FILES = {
    "synthesis": "reports/latest_release_report.json",
    "traceability": "reports/traceability.json",
    "simulation": "reports/release_simulation.json",
    "remediation": "reports/remediation_plan.json",
    "comparison": "reports/comparison.json",
    "agent-impact": "reports/agents/impact_report.json",
    "agent-test_gap": "reports/agents/test_gap_report.json",
    "agent-security": "reports/agents/security_report.json",
    "agent-contract": "reports/agents/contract_report.json",
    "agent-database": "reports/agents/database_report.json",
}

REPORT_TITLES = {
    "synthesis": "Consolidated Release Synthesis Report",
    "traceability": "Requirement-to-Code Traceability Matrix",
    "simulation": "Release Impact Simulation & Regression Paths",
    "remediation": "Prioritized Release Remediation Plan",
    "comparison": "Before/After Release Metrics & Delta Analysis",
    "agent-impact": "IBM Bob 2.0 — Code Impact Analyst Report",
    "agent-test_gap": "IBM Bob 2.0 — Test Gap Analyst Report",
    "agent-security": "IBM Bob 2.0 — Security Analyst Report",
    "agent-contract": "IBM Bob 2.0 — Contract & Doc Analyst Report",
    "agent-database": "IBM Bob 2.0 — Database & Schema Analyst Report",
}


class DataStore:
    """Manages loading and caching of JSON report artifacts."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._cache: Dict[str, Any] = {}

    def reload(self) -> None:
        """Clear cache to force reloading from disk."""
        self._cache.clear()

    def get_report(self, report_key: str) -> Dict[str, Any]:
        """Load report by key with caching and error checking."""
        if report_key not in REPORT_FILES:
            raise KeyError(f"Unknown report key: {report_key}")

        rel_path = REPORT_FILES[report_key]
        full_path = self.repo_root / rel_path

        if not full_path.exists():
            raise FileNotFoundError(f"Report artifact not found: {rel_path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in report '{rel_path}': {exc}") from exc

    def get_all_reports_status(self) -> list[dict]:
        """Return existence and metadata for all audit reports."""
        status_list = []
        for key, rel_path in REPORT_FILES.items():
            full_path = self.repo_root / rel_path
            exists = full_path.exists()
            size = full_path.stat().st_size if exists else 0
            mtime = full_path.stat().st_mtime if exists else None
            status_list.append({
                "key": key,
                "title": REPORT_TITLES.get(key, key),
                "path": rel_path,
                "exists": exists,
                "size_bytes": size,
                "mtime": mtime,
            })
        return status_list


def create_app(repo_root: Optional[str | Path] = None) -> Flask:
    """Application factory for ShipSafe Web Dashboard."""
    if repo_root is None:
        root_path = get_repo_root()
    else:
        root_path = Path(repo_root)

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    store = DataStore(root_path)

    # -----------------------------------------------------------------------
    # Helper formatters
    # -----------------------------------------------------------------------

    def get_safe_report(key: str) -> Optional[dict]:
        try:
            return store.get_report(key)
        except (FileNotFoundError, ValueError, KeyError):
            return None

    # -----------------------------------------------------------------------
    # Web UI Routes
    # -----------------------------------------------------------------------

    @app.route("/")
    def index():
        """Render the primary ShipSafe executive & engineering dashboard."""
        synthesis = get_safe_report("synthesis") or {}
        traceability = get_safe_report("traceability") or {}
        simulation = get_safe_report("simulation") or {}
        remediation = get_safe_report("remediation") or {}
        comparison = get_safe_report("comparison") or {}

        # Collect Bob agent reports
        bob_agents = []
        for agent_key in ["agent-impact", "agent-test_gap", "agent-security", "agent-contract", "agent-database"]:
            agent_data = get_safe_report(agent_key)
            if agent_data:
                agent_name = agent_data.get("agent_name", agent_key.replace("agent-", "").replace("_", " ").title())
                findings = agent_data.get("findings", [])
                critical_count = sum(1 for f in findings if f.get("severity") == "CRITICAL")
                high_count = sum(1 for f in findings if f.get("severity") == "HIGH")
                med_count = sum(1 for f in findings if f.get("severity") in ("MEDIUM", "MED"))
                low_count = sum(1 for f in findings if f.get("severity") == "LOW")
                info_count = sum(1 for f in findings if f.get("severity") == "INFO")

                bob_agents.append({
                    "key": agent_key,
                    "name": agent_name,
                    "report_file": REPORT_FILES[agent_key],
                    "status": agent_data.get("status", "COMPLETE"),
                    "finding_count": len(findings),
                    "critical_count": critical_count,
                    "high_count": high_count,
                    "medium_count": med_count,
                    "low_count": low_count,
                    "info_count": info_count,
                    "generated_at": agent_data.get("timestamp") or agent_data.get("generated_at"),
                })

        audit_trail = store.get_all_reports_status()

        return render_template(
            "index.html",
            synthesis=synthesis,
            traceability=traceability,
            simulation=simulation,
            remediation=remediation,
            comparison=comparison,
            bob_agents=bob_agents,
            audit_trail=audit_trail,
        )

    @app.route("/report/<report_type>")
    def report_detail(report_type: str):
        """Display a dedicated, human-readable view of a specific JSON report artifact."""
        if report_type not in REPORT_FILES:
            abort(404, description=f"Report type '{report_type}' not recognized.")

        try:
            data = store.get_report(report_type)
        except FileNotFoundError:
            abort(404, description=f"Report '{REPORT_FILES[report_type]}' not found on disk.")
        except ValueError as exc:
            abort(500, description=f"Report format error: {exc}")

        title = REPORT_TITLES.get(report_type, report_type)
        file_path = REPORT_FILES[report_type]
        raw_json = json.dumps(data, indent=2)

        return render_template(
            "report_detail.html",
            report_type=report_type,
            title=title,
            file_path=file_path,
            data=data,
            raw_json=raw_json,
        )

    # -----------------------------------------------------------------------
    # REST API Routes
    # -----------------------------------------------------------------------

    @app.route("/api/overview")
    def api_overview():
        """Return top-level release status, repository metadata, and high-level KPIs."""
        synthesis = get_safe_report("synthesis")
        comparison = get_safe_report("comparison")

        if not synthesis:
            return jsonify({"error": "Synthesis report not available", "status": "NOT_FOUND"}), 404

        summary = synthesis.get("summary", {})
        repo = synthesis.get("repository", {})

        # Extract delta comparisons if comparison report exists
        metrics_summary = {}
        if comparison and "comparisons" in comparison:
            metrics_summary = comparison["comparisons"].get("metrics_summary", {})

        return jsonify({
            "status": synthesis.get("status", "UNKNOWN"),
            "generated_at": synthesis.get("generated_at"),
            "repository": {
                "name": "shipsafe-ai",
                "branch": repo.get("branch", "main"),
                "head_commit": repo.get("head_commit", "unknown"),
                "is_clean": repo.get("is_clean", False),
            },
            "kpis": {
                "total_findings": summary.get("total_findings", 0),
                "critical_count": summary.get("critical_count", 0),
                "high_count": summary.get("high_count", 0),
                "medium_count": summary.get("medium_count", 0),
                "requirements_failed": summary.get("requirements_non_compliant", 0),
                "requirements_compliant": summary.get("requirements_compliant", 0),
                "requirements_total": 5,
                "files_changed": metrics_summary.get("affected_files", {}).get("bad_release", 6),
            },
            "comparison": metrics_summary,
            "evidence_statement": "Release status is derived from IBM Bob analysis evidence and deterministic synthesis.",
        })

    @app.route("/api/agents")
    def api_agents():
        """Return status and finding metrics for the five IBM Bob 2.0 analysis agents."""
        agents = []
        agent_keys = ["agent-impact", "agent-test_gap", "agent-security", "agent-contract", "agent-database"]

        for k in agent_keys:
            try:
                data = store.get_report(k)
                findings = data.get("findings", [])
                severities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
                for f in findings:
                    sev = f.get("severity", "INFO").upper()
                    if sev in severities:
                        severities[sev] += 1
                    elif sev in ("MED", "WARNING"):
                        severities["MEDIUM"] += 1

                agents.append({
                    "key": k,
                    "agent_id": k.replace("agent-", ""),
                    "agent_name": data.get("agent_name", k),
                    "report_file": REPORT_FILES[k],
                    "status": data.get("status", "COMPLETE"),
                    "finding_count": len(findings),
                    "severities": severities,
                    "targets": data.get("targets", []),
                    "timestamp": data.get("timestamp") or data.get("generated_at"),
                    "attribution": "Historical analysis artifact generated by IBM Bob 2.0",
                })
            except FileNotFoundError:
                agents.append({
                    "key": k,
                    "agent_id": k.replace("agent-", ""),
                    "status": "NOT_FOUND",
                    "report_file": REPORT_FILES[k],
                    "error": "Report file missing",
                })
            except ValueError as exc:
                agents.append({
                    "key": k,
                    "agent_id": k.replace("agent-", ""),
                    "status": "INVALID_JSON",
                    "report_file": REPORT_FILES[k],
                    "error": str(exc),
                })

        return jsonify({
            "count": len(agents),
            "agents": agents,
            "orchestrated_by": "IBM Bob 2.0",
        })

    @app.route("/api/requirements")
    def api_requirements():
        """Return the five release requirements (R001–R005) with compliance status and conflict data."""
        traceability = get_safe_report("traceability")
        synthesis = get_safe_report("synthesis")

        if not traceability:
            return jsonify({"error": "Traceability report not available", "status": "NOT_FOUND"}), 404

        reqs = traceability.get("requirements", [])
        return jsonify({
            "count": len(reqs),
            "requirements": reqs,
        })

    @app.route("/api/findings")
    def api_findings():
        """Return synthesized findings with optional query filtering by severity, requirement, and agent."""
        synthesis = get_safe_report("synthesis")
        if not synthesis:
            return jsonify({"error": "Synthesis report not available", "status": "NOT_FOUND"}), 404

        findings = synthesis.get("findings", [])

        # Filter parameters
        sev_filter = request.args.get("severity", "").upper()
        req_filter = request.args.get("requirement", "").upper()
        agent_filter = request.args.get("agent", "").lower()

        filtered = []
        for f in findings:
            if sev_filter and f.get("severity") != sev_filter:
                continue
            if req_filter and req_filter not in f.get("title", "") and req_filter not in f.get("description", ""):
                # Also check requirement tags if present
                continue
            if agent_filter:
                f_id = f.get("finding_id", "").lower()
                if not f_id.startswith(agent_filter):
                    continue
            filtered.append(f)

        return jsonify({
            "total_available": len(findings),
            "filtered_count": len(filtered),
            "findings": filtered,
        })

    @app.route("/api/traceability")
    def api_traceability():
        """Return full requirement traceability data."""
        data = get_safe_report("traceability")
        if not data:
            return jsonify({"error": "Traceability report not available", "status": "NOT_FOUND"}), 404
        return jsonify(data)

    @app.route("/api/simulation")
    def api_simulation():
        """Return release impact simulation components, workflows, and regression paths."""
        data = get_safe_report("simulation")
        if not data:
            return jsonify({"error": "Simulation report not available", "status": "NOT_FOUND"}), 404
        return jsonify(data)

    @app.route("/api/remediation")
    def api_remediation():
        """Return prioritized remediation items."""
        data = get_safe_report("remediation")
        if not data:
            return jsonify({"error": "Remediation report not available", "status": "NOT_FOUND"}), 404
        return jsonify(data)

    @app.route("/api/comparison")
    def api_comparison():
        """Return baseline vs bad release metrics and post-remediation status."""
        data = get_safe_report("comparison")
        if not data:
            return jsonify({"error": "Comparison report not available", "status": "NOT_FOUND"}), 404
        return jsonify(data)

    @app.route("/api/report/<report_type>")
    def api_report_content(report_type: str):
        """Return raw JSON content for a specific report key."""
        if report_type not in REPORT_FILES:
            return jsonify({"error": f"Unknown report key: {report_type}", "status": "NOT_FOUND"}), 404

        try:
            data = store.get_report(report_type)
            return jsonify(data)
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc), "status": "NOT_FOUND"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc), "status": "INVALID_JSON"}), 500

    @app.route("/api/refresh", methods=["POST", "GET"])
    def api_refresh():
        """Clear cache and reload reports from disk."""
        store.reload()
        return jsonify({
            "status": "OK",
            "message": "Report artifacts reloaded from disk.",
            "reports": store.get_all_reports_status(),
        })

    # Error handlers
    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": str(e.description if hasattr(e, "description") else e), "status": "NOT_FOUND"}), 404
        return render_template("report_detail.html", title="Not Found", report_type="error", error=str(e), file_path="", raw_json="", data={}), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": str(e.description if hasattr(e, "description") else e), "status": "SERVER_ERROR"}), 500
        return render_template("report_detail.html", title="Server Error", report_type="error", error=str(e), file_path="", raw_json="", data={}), 500

    return app


# Module-level instance for WSGI / `python -m shipsafe.web.app`
app = create_app()

if __name__ == "__main__":
    host = os.environ.get("SHIPSAFE_HOST", "127.0.0.1")
    port = int(os.environ.get("SHIPSAFE_PORT", "5000"))
    print("=" * 65)
    print(f"  ShipSafe AI — Dashboard running at http://{host}:{port}")
    print("  Agentic Release & Regression Guardian")
    print("=" * 65)
    app.run(host=host, port=port, debug=False)
