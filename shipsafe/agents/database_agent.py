"""Database and Dependency Agent: audits schema migrations and package manifests."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack
from shipsafe.ai.schemas import AgentReport


class DatabaseAgent(BaseSpecialistAgent):
    name = "database"
    system_prompt = """You are the Database and Dependency Agent for ShipSafe AI.
Your investigative question is: "Are persistence and dependencies still consistent with the change?"
Inspect models, schema files, SQL scripts, migrations, ORM entities, and dependency manifests.
Detect unmigrated model changes, unsafe column drops, non-nullable columns added without defaults,
breaking constraint modifications, and risky package additions or version drifts.

CRITICAL INSTRUCTION:
If no persistence, migration, schema, or dependency defect is detected, or if the repository does not use a database, return:
{
  "agent": "database",
  "findings": []
}
Never invent a database finding. Never report database issues against README or documentation.

Schema when findings exist:
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
      "evidence_type": "database_schema",
      "affected_components": ["DatabaseSchema", "ModelClass"],
      "recommendation": "Provide SQL migration script or dependency version constraint",
      "confidence": 0.94
    }
  ]
}
Ground every finding in real files from the repository."""

    async def run(self, evidence: EvidencePack) -> AgentReport:
        db_disc = evidence.discovery.get("database", {})
        models = db_disc.get("models", [])
        schemas = db_disc.get("schemas", [])
        migrations = db_disc.get("migrations", [])
        databases = evidence.discovery.get("databases", [])

        # If repo has NO database usage at all: return 0 findings immediately
        if not models and not schemas and not migrations and not databases:
            return AgentReport(agent=self.name, findings=[])

        return await super().run(evidence)

    def build_prompt(self, evidence: EvidencePack) -> str:
        # Filter changed files to ignore README and documentation
        code_changed_files = [
            f for f in evidence.changed_files
            if not f.lower().endswith(("readme.md", ".txt", ".md", ".png", ".jpg"))
        ]
        payload = {
            "agent_name": self.name,
            "database_discovery": evidence.discovery.get("database", {}),
            "databases": evidence.discovery.get("databases", []),
            "migration_system": evidence.discovery.get("migration_system", []),
            "dependency_manifests": evidence.discovery.get("dependency_manifests", []),
            "changed_files": code_changed_files,
            "file_diffs": [
                d for d in evidence.file_diffs
                if not d.get("file_path", "").lower().endswith(("readme.md", ".txt", ".md"))
            ],
            "raw_diff": evidence.raw_diff[:12000],
        }

        return json.dumps(payload, indent=2)

