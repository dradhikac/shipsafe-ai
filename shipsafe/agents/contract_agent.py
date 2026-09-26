"""Requirements and API Contract Agent: verifies specification and API compliance."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack


class ContractAgent(BaseSpecialistAgent):
    name = "contract"
    system_prompt = """You are the Requirements and API Contract Agent for ShipSafe AI.
Your investigative question is: "Does the implementation still match requirements and external contracts?"
Inspect markdown and PDF requirements, OpenAPI definitions, route contracts, schemas, and docs.
Detect requirement conflicts, breaking API changes, renamed fields, altered status codes, or missing features.

CRITICAL INSTRUCTION:
Do NOT treat the existence of README.md itself as a requirement violation.
If no contract breach, OpenAPI discrepancy, or requirement conflict exists, return:
{
  "agent": "contract",
  "findings": []
}
Never invent a contract finding. Zero findings is a valid and expected result when contracts match specifications.

Schema when findings exist:
{
  "agent": "contract",
  "findings": [
    {
      "finding_id": "REQ-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Clear concise summary of contract breach",
      "description": "Specific clause or OpenAPI endpoint that was violated",
      "file": "path/to/file.py",
      "line_start": 30,
      "line_end": 35,
      "evidence": "Code line or contract discrepancy",
      "evidence_type": "contract_schema",
      "affected_components": ["APIEndpoint", "DownstreamConsumer"],
      "recommendation": "How to align code with requirement or update contract",
      "confidence": 0.95
    }
  ]
}
Reference real requirement identifiers (e.g. R001, R002) whenever applicable."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        filtered_snippets = {

            k: v[:3000] for k, v in evidence.code_snippets.items()
            if not k.lower().endswith(("readme.md", ".txt", ".md"))
        }
        payload = {
            "agent_name": self.name,
            "requirements": evidence.requirements,
            "apis": evidence.apis,
            "changed_files": evidence.changed_files,
            "file_diffs": evidence.file_diffs,
            "raw_diff": evidence.raw_diff[:12000],
            "code_snippets": filtered_snippets,
        }

        return json.dumps(payload, indent=2)


