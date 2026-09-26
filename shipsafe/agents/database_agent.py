"""Database and Dependency Agent: audits schema migrations and package manifests."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack


class DatabaseAgent(BaseSpecialistAgent):
    name = "database"
    system_prompt = """You are the Database and Dependency Agent for ShipSafe AI.
Your investigative question is: "Are persistence and dependencies still consistent with the change?"
Inspect models, schema files, SQL scripts, migrations, ORM entities, and dependency manifests.
Detect unmigrated model changes, unsafe column drops, non-nullable columns added without defaults,
breaking constraint modifications, and risky package additions or version drifts.
Return ONLY a valid JSON object matching this schema:
{
  "agent": "database",
  "findings": [
    {
      "finding_id": "DB-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Clear concise summary of persistence or dependency issue",
      "description": "Details regarding schema drift, missing migration, or package risk",
      "file": "path/to/file.py",
      "line_start": 20,
      "line_end": 25,
      "evidence": "Model field definition or SQL snippet",
      "affected_components": ["DatabaseSchema", "ModelClass"],
      "recommendation": "Provide SQL migration script or dependency version constraint",
      "confidence": 0.94
    }
  ]
}
Ground every finding in real files from the repository."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        payload = {
            "database_discovery": evidence.discovery.get("database", {}),
            "dependency_manifests": evidence.discovery.get("dependency_manifests", []),
            "changed_files": evidence.changed_files,
            "file_diffs": evidence.file_diffs,
            "raw_diff": evidence.raw_diff[:12000],
        }
        return json.dumps(payload, indent=2)
