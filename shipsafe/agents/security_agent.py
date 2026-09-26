"""Security Agent: investigates vulnerabilities, secret leakage, and unsafe patterns."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack


class SecurityAgent(BaseSpecialistAgent):
    name = "security"
    system_prompt = """You are the Security Agent for ShipSafe AI.
Your investigative question is: "Did the change introduce a security weakness?"
Check at minimum:
- SQL injection (raw query formatting, unparameterized cursors)
- Command injection (subprocess, exec, os.system)
- Path traversal (unvalidated filename joins)
- Unsafe deserialization (pickle, yaml.load)
- Broken authentication or authorization bypasses
- Secret exposure or hardcoded keys
- Insecure configuration and dependency risks
Return ONLY a valid JSON object matching this schema:
{
  "agent": "security",
  "findings": [
    {
      "finding_id": "SEC-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Clear concise summary of vulnerability",
      "description": "Exploitation mechanism and impact details",
      "file": "path/to/file.py",
      "line_start": 45,
      "line_end": 48,
      "evidence": "Vulnerable code snippet",
      "affected_components": ["AffectedRouteOrService"],
      "recommendation": "Exact secure remediation guidance (e.g. parameterized query)",
      "confidence": 0.98
    }
  ]
}
Ground every finding in real code snippets from the diff."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        payload = {
            "changed_files": evidence.changed_files,
            "file_diffs": evidence.file_diffs,
            "raw_diff": evidence.raw_diff[:12000],
            "code_snippets": {
                k: v[:3000] for k, v in evidence.code_snippets.items()
            }
        }
        return json.dumps(payload, indent=2)
