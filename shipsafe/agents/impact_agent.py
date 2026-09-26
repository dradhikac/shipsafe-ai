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

CRITICAL INSTRUCTION:
Do NOT create an "unbounded blast radius" finding for README.md or general documentation.
If no source code, configuration, or interface change exists, or if the change has bounded/negligible blast radius, return:
{
  "agent": "impact",
  "findings": []
}
Never invent an impact finding. Zero findings is a valid and expected result when changes have no cascading risk.

Schema when findings exist:
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
      "evidence_type": "source_code",
      "affected_components": ["ComponentName", "RouteName"],
      "recommendation": "How to minimize blast radius or preserve compatibility",
      "confidence": 0.95
    }
  ]
}
Ground every finding in real repository files and diff hunks. Do NOT invent files or lines."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        # Filter changed files to only inspect code/config/manifest files
        code_changed_files = [
            f for f in evidence.changed_files
            if not f.lower().endswith(("readme.md", ".txt", ".md", ".png", ".jpg", ".svg", ".lock"))
        ]
        filtered_snippets = {
            k: v[:2000] for k, v in evidence.code_snippets.items()
            if not k.lower().endswith(("readme.md", ".txt", ".md"))
        }

        payload = {
            "agent_name": self.name,
            "changed_files": code_changed_files,
            "file_diffs": [
                d for d in evidence.file_diffs
                if not d.get("file_path", "").lower().endswith(("readme.md", ".txt", ".md"))
            ],
            "raw_diff": evidence.raw_diff[:12000],
            "routes": [a for a in evidence.discovery.get("api_definitions", [])],
            "models": evidence.discovery.get("database", {}).get("models", []),
            "code_snippets": filtered_snippets,
        }

        return json.dumps(payload, indent=2)

