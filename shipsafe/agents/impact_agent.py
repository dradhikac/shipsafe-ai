"""Change Impact Agent: maps changed code to affected components and workflows."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack


class ChangeImpactAgent(BaseSpecialistAgent):
    name = "impact"
    system_prompt = """You are the Change Impact Agent for ShipSafe AI.
Your investigative question is: "What changed and what parts of the system can this change affect?"
Analyze the provided git diff, modified files, changed symbols, routes, models, and caller relationships.
Identify affected downstream components, external APIs, and user workflows.
Return ONLY a valid JSON object matching this schema:
{
  "agent": "impact",
  "findings": [
    {
      "finding_id": "IMP-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Clear concise summary",
      "description": "Technical detail explaining the impact and blast radius",
      "file": "path/to/file.py",
      "line_start": 10,
      "line_end": 25,
      "evidence": "Exact code line or function signature from diff",
      "affected_components": ["ComponentName", "RouteName"],
      "recommendation": "How to minimize blast radius or preserve compatibility",
      "confidence": 0.95
    }
  ]
}
Ground every finding in real repository files and diff hunks. Do NOT invent files or lines."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        payload = {
            "changed_files": evidence.changed_files,
            "file_diffs": evidence.file_diffs,
            "raw_diff": evidence.raw_diff[:12000],
            "routes": [a for a in evidence.discovery.get("api_definitions", [])],
            "models": evidence.discovery.get("database", {}).get("models", []),
            "code_snippets": {
                k: v[:2000] for k, v in evidence.code_snippets.items()
            }
        }
        return json.dumps(payload, indent=2)
