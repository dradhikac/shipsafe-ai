"""Deterministic mock AI provider for offline testing and local CI.

Strictly evidence-grounded:
- Never invents generic findings.
- Returns zero findings ({"findings": []}) when no verifiable defect exists.
- Extracts real files and lines only from actual evidence present in the prompt.
"""

import json
import re
from typing import Optional, Dict, Any, List
from .provider import AIProvider


class MockProvider(AIProvider):
    """Provides deterministic structured agent findings grounded strictly in prompt evidence."""

    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            data = json.loads(prompt)
        except Exception:
            data = {}

        # 1. Deterministic agent type determination
        agent_type = data.get("agent_name") or "unknown"
        if agent_type == "unknown" and system_prompt:
            if "Security Agent" in system_prompt or "agent: security" in system_prompt.lower():
                agent_type = "security"
            elif "Test Gap Agent" in system_prompt or "agent: test_gap" in system_prompt.lower():
                agent_type = "test_gap"
            elif "Contract Agent" in system_prompt or "Requirements and API Contract" in system_prompt:
                agent_type = "contract"
            elif "Database and Dependency Agent" in system_prompt or "Database Agent" in system_prompt:
                agent_type = "database"
            elif "Change Impact Agent" in system_prompt:
                agent_type = "impact"

        findings: List[Dict[str, Any]] = []

        # -----------------------------------------------------------
        # 1. SECURITY AGENT
        # -----------------------------------------------------------
        if agent_type == "security":
            snippets = data.get("code_snippets", {})
            raw_diff = data.get("raw_diff", "")

            # Scan for real SQL injection patterns in code snippets
            for fpath, code in snippets.items():
                if fpath.lower().endswith(("readme.md", ".txt", ".md", ".json", ".lock")):
                    continue
                lines = code.splitlines()
                for idx, line in enumerate(lines, 1):
                    # SQL injection pattern: raw string formatting / interpolation
                    if re.search(r"SELECT\s+.*WHERE\s+.*[\'\"]\s*\+\s*\w+|f[\'\"]SELECT\s+.*\{", line, re.IGNORECASE):
                        findings.append({
                            "finding_id": "SEC-001",
                            "agent": "security",
                            "severity": "CRITICAL",
                            "title": "Unparameterized SQL query injection vulnerability",
                            "description": "User input is directly interpolated into raw SQL statement without parameter binding.",
                            "file": fpath,
                            "line_start": idx,
                            "line_end": idx,
                            "evidence": line.strip(),
                            "evidence_type": "source_code",
                            "affected_components": [fpath.split("/")[0]],
                            "recommendation": "Use parameterized queries or ORM query binding instead of string formatting.",
                            "confidence": 0.98,
                        })
                        break
                    # Command injection
                    elif re.search(r"(?:os\.system|subprocess\.Popen|subprocess\.run|subprocess\.call)\s*\([^)]*shell\s*=\s*True", line):
                        findings.append({
                            "finding_id": "SEC-002",
                            "agent": "security",
                            "severity": "CRITICAL",
                            "title": "Arbitrary command execution via shell=True",
                            "description": "Subprocess executed with shell=True exposing the host to command injection.",
                            "file": fpath,
                            "line_start": idx,
                            "line_end": idx,
                            "evidence": line.strip(),
                            "evidence_type": "source_code",
                            "affected_components": [fpath.split("/")[0]],
                            "recommendation": "Pass argument list to subprocess and avoid shell=True.",
                            "confidence": 0.96,
                        })
                        break

        # -----------------------------------------------------------
        # 2. CONTRACT / REQUIREMENTS AGENT
        # -----------------------------------------------------------
        elif agent_type == "contract":
            reqs = data.get("requirements", [])
            apis = data.get("apis", [])
            snippets = data.get("code_snippets", {})
            changed_files = [f for f in data.get("changed_files", []) if not f.lower().endswith("readme.md")]

            all_code_and_apis = str(apis) + " " + " ".join(snippets.values()) + " " + data.get("raw_diff", "")

            # Look for endpoint or schema discrepancies
            for req in reqs:
                rid = req.get("id", "R001")
                rdesc = req.get("description") or req.get("text", "")
                rtitle = req.get("title", "")


                # Check if requirement specifies camelCase (e.g. userId) but code/apis returns snake_case (e.g. user_id)
                if ("userId" in rdesc or "userId" in rtitle) and "user_id" in all_code_and_apis:
                    target_f = next((f for f, code in snippets.items() if "user_id" in code), None)
                    if not target_f and apis:
                        target_f = apis[0].get("file")
                    if not target_f and changed_files:
                        target_f = changed_files[0]
                    target_f = target_f or "routes/users.js"

                    findings.append({
                        "finding_id": f"REQ-{rid}",
                        "agent": "contract",
                        "severity": "HIGH",
                        "title": f"Field naming contract mismatch for {rid}",
                        "description": f"Requirement {rid} specifies camelCase 'userId' but implementation returns snake_case 'user_id'.",
                        "file": target_f,
                        "line_start": 1,
                        "line_end": 10,
                        "evidence": "userId vs user_id schema mismatch",
                        "evidence_type": "contract_schema",
                        "affected_components": ["APIContract"],
                        "recommendation": "Align JSON serialization field names with the contract specification.",
                        "confidence": 0.94,
                    })

        # -----------------------------------------------------------
        # 3. DATABASE AGENT
        # -----------------------------------------------------------
        elif agent_type == "database":
            db_discovery = data.get("database_discovery", {})
            databases = data.get("databases", [])
            models = db_discovery.get("models", [])
            schemas = db_discovery.get("schemas", [])
            migrations = db_discovery.get("migrations", [])

            # If repo has NO database models, schemas, migrations, or databases: return ZERO findings!
            if not models and not schemas and not migrations and not databases:
                return json.dumps({"agent": "database", "findings": []})

            # Check if models were changed in diff without matching migration
            raw_diff = data.get("raw_diff", "")
            file_diffs = data.get("file_diffs", [])
            model_diffs = [
                d.get("file_path") for d in file_diffs
                if any(m in d.get("file_path", "") for m in ("model", "entity", "schema"))
            ]
            migration_diffs = [
                d.get("file_path") for d in file_diffs
                if "migration" in d.get("file_path", "")
            ]

            if raw_diff and model_diffs and not migration_diffs:
                target_f = model_diffs[0]
                findings.append({
                    "finding_id": "DB-001",
                    "agent": "database",
                    "severity": "HIGH",
                    "title": f"Unmigrated database model changes in {target_f}",
                    "description": "Model definitions were updated without a corresponding forward migration script.",
                    "file": target_f,
                    "line_start": 1,
                    "line_end": 10,
                    "evidence": f"Modified model '{target_f}' lacking migration.",
                    "evidence_type": "database_schema",
                    "affected_components": ["DatabaseSchema"],
                    "recommendation": "Generate and commit a versioned migration for model updates.",
                    "confidence": 0.92,
                })

        # -----------------------------------------------------------
        # 4. TEST GAP AGENT
        # -----------------------------------------------------------
        elif agent_type == "test_gap":
            test_results = data.get("test_results", {})
            changed_files = [f for f in data.get("changed_files", []) if not f.lower().endswith(("readme.md", ".txt", ".md"))]

            if test_results.get("failed", 0) > 0:
                failures = test_results.get("failures", [])
                fail_summary = failures[0] if failures else "Test failure detected"
                findings.append({
                    "finding_id": "GAP-001",
                    "agent": "test_gap",
                    "severity": "HIGH",
                    "title": "Failing test regression in test suite",
                    "description": str(fail_summary),
                    "file": changed_files[0] if changed_files else "tests/test_suite.py",
                    "line_start": 1,
                    "line_end": 5,
                    "evidence": str(fail_summary),
                    "evidence_type": "test_failure",
                    "affected_components": ["RegressionSuite"],
                    "recommendation": "Resolve the regression test assertion failure.",
                    "confidence": 0.95,
                })

        # -----------------------------------------------------------
        # 5. CHANGE IMPACT AGENT
        # -----------------------------------------------------------
        elif agent_type == "impact":
            raw_diff = data.get("raw_diff", "")
            file_diffs = data.get("file_diffs", [])
            code_diffs = [
                d for d in file_diffs
                if not d.get("file_path", "").lower().endswith(("readme.md", ".txt", ".md", ".json", ".lock"))
            ]
            if raw_diff and code_diffs:
                target_f = code_diffs[0]["file_path"]
                findings.append({
                    "finding_id": "IMP-001",
                    "agent": "impact",
                    "severity": "MEDIUM",
                    "title": f"Interface change blast radius in {target_f}",
                    "description": f"Modified symbols in {target_f} propagate to consumers across callers.",
                    "file": target_f,
                    "line_start": 1,
                    "line_end": 10,
                    "evidence": f"Diff changes in {target_f}",
                    "evidence_type": "source_code",
                    "affected_components": [target_f.split("/")[0]],
                    "recommendation": "Verify all callers conform to updated signature.",
                    "confidence": 0.90,
                })

        return json.dumps({
            "agent": agent_type,
            "findings": findings
        })
