"""Deterministic mock AI provider for offline testing and local CI."""

import json
import re
from typing import Optional, Dict, Any
from .provider import AIProvider


class MockProvider(AIProvider):
    """Provides deterministic structured agent findings based on evidence content."""

    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        agent_type = "unknown"
        if system_prompt:
            if "Impact Agent" in system_prompt:
                agent_type = "impact"
            elif "Test Gap Agent" in system_prompt:
                agent_type = "test_gap"
            elif "Security Agent" in system_prompt:
                agent_type = "security"
            elif "Requirements" in system_prompt or "Contract" in system_prompt:
                agent_type = "contract"
            elif "Database" in system_prompt or "Dependency" in system_prompt:
                agent_type = "database"

        # Search for files mentioned in prompt
        file_matches = re.findall(r'"file_path":\s*"([^"]+)"', prompt)
        sample_file = file_matches[0] if file_matches else "README.md"

        findings = []

        if agent_type == "impact":
            findings.append({
                "finding_id": "IMP-001",
                "severity": "HIGH",
                "title": f"Unbounded blast radius in {sample_file}",
                "description": f"Changes in {sample_file} affect downstream caller chains and route execution.",
                "file": sample_file,
                "line_start": 1,
                "line_end": 10,
                "evidence": "Modified symbol execution path detected in diff.",
                "affected_components": [sample_file],
                "recommendation": "Review downstream consumers and ensure backwards-compatible interfaces.",
                "confidence": 0.95
            })

        elif agent_type == "test_gap":
            findings.append({
                "finding_id": "GAP-001",
                "severity": "HIGH",
                "title": f"Missing regression coverage for changes in {sample_file}",
                "description": "New branches in the changed file lack corresponding test assertions.",
                "file": sample_file,
                "line_start": 1,
                "line_end": 10,
                "evidence": "Uncovered lines in diff.",
                "affected_components": [sample_file],
                "recommendation": "Add regression test cases covering modified execution branches.",
                "confidence": 0.90
            })

        elif agent_type == "security":
            # Check if SQL injection or secret patterns exist in prompt
            is_critical = "SELECT" in prompt or "password" in prompt or "key" in prompt
            findings.append({
                "finding_id": "SEC-001",
                "severity": "CRITICAL" if is_critical else "LOW",
                "title": f"Security risk inspection in {sample_file}",
                "description": "Potential unsafe parameter usage or insecure deserialization detected.",
                "file": sample_file,
                "line_start": 1,
                "line_end": 10,
                "evidence": "Raw variable usage in sensitive operation context.",
                "affected_components": [sample_file],
                "recommendation": "Apply parameter binding and strict input validation.",
                "confidence": 0.92
            })

        elif agent_type == "contract":
            findings.append({
                "finding_id": "REQ-001",
                "severity": "HIGH",
                "title": f"Requirement specification check for {sample_file}",
                "description": "Endpoint behavior may diverge from documented acceptance criteria in requirements.",
                "file": sample_file,
                "line_start": 1,
                "line_end": 10,
                "evidence": "Contract field mismatch detected against documented specification.",
                "affected_components": [sample_file],
                "recommendation": "Align response serialization model with requirement schema.",
                "confidence": 0.94
            })

        elif agent_type == "database":
            findings.append({
                "finding_id": "DB-001",
                "severity": "HIGH",
                "title": f"Database persistence alignment check in {sample_file}",
                "description": "Model or schema change requires forward migration validation.",
                "file": sample_file,
                "line_start": 1,
                "line_end": 10,
                "evidence": "Schema definition update without explicit migration step.",
                "affected_components": [sample_file],
                "recommendation": "Ensure versioned SQL migration is committed alongside model changes.",
                "confidence": 0.93
            })

        return json.dumps({
            "agent": agent_type,
            "findings": findings
        })
