"""Security Agent: investigates vulnerabilities, secret leakage, and unsafe patterns."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack


class SecurityAgent(BaseSpecialistAgent):
    name = "security"
    system_prompt = """You are the Security Agent for ShipSafe AI.
Your investigative question is: "Did the change introduce an actual security weakness?"
Check at minimum:
- SQL injection (raw query formatting, string concatenation in queries)
- Command injection (subprocess, exec, os.system, shell=True)
- Path traversal (unvalidated filename joins)
- Unsafe deserialization (pickle, yaml.load)
- Broken authentication or authorization bypasses
- Secret exposure or hardcoded keys
- Insecure configuration and dependency risks

CRITICAL INSTRUCTION:
If no confirmed security vulnerability is detected in the code changes, return:
{
  "agent": "security",
  "findings": []
}
Never invent a security finding. Do NOT create findings for README.md or markdown files unless raw credentials/secrets are leaked in them. Zero findings is a successful and expected result when no vulnerabilities exist.

Schema when findings exist:
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
      "evidence_type": "source_code",
      "affected_components": ["AffectedRouteOrService"],
      "recommendation": "Exact secure remediation guidance (e.g. parameterized query)",
      "confidence": 0.98
    }
  ]
}
Ground every finding in real code snippets from the diff."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        # Filter changed files and code snippets to exclude docs
        code_changed_files = [
            f for f in evidence.changed_files
            if not f.lower().endswith(("readme.md", ".txt", ".md", ".png", ".jpg"))
        ]
        filtered_snippets = {
            k: v[:3000] for k, v in evidence.code_snippets.items()
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
            "code_snippets": filtered_snippets,
        }

        return json.dumps(payload, indent=2)

