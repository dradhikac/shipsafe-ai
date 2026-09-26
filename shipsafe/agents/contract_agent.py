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
Return ONLY a valid JSON object matching this schema:
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
      "affected_components": ["APIEndpoint", "DownstreamConsumer"],
      "recommendation": "How to align code with requirement or update contract",
      "confidence": 0.95
    }
  ]
}
Reference real requirement identifiers (e.g. R001, R002) whenever applicable."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        payload = {
            "requirements": evidence.requirements,
            "apis": evidence.apis,
            "changed_files": evidence.changed_files,
            "file_diffs": evidence.file_diffs,
            "raw_diff": evidence.raw_diff[:12000],
        }
        return json.dumps(payload, indent=2)
