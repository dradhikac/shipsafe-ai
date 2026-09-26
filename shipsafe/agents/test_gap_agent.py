"""Test Gap Agent: detects missing tests, deleted regression tests, and coverage drops."""

import json
from .base import BaseSpecialistAgent
from shipsafe.core.evidence import EvidencePack


class TestGapAgent(BaseSpecialistAgent):
    __test__ = False
    name = "test_gap"
    system_prompt = """You are the Test Gap Agent for ShipSafe AI.
Your investigative question is: "Did the change introduce behavior that is not adequately covered?"
Analyze modified code, new branches, deleted tests, and test execution results.
Highlight missing tests, deleted regression paths, or unasserted edge cases.
Return ONLY a valid JSON object matching this schema:
{
  "agent": "test_gap",
  "findings": [
    {
      "finding_id": "GAP-001",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "title": "Clear concise summary of test gap",
      "description": "Explanation of uncovered branches or regression risks",
      "file": "path/to/file.py",
      "line_start": 10,
      "line_end": 20,
      "evidence": "Uncovered code snippet or deleted test name",
      "affected_components": ["ServiceUnderTest"],
      "recommendation": "Specific test cases and assertions to add",
      "confidence": 0.90
    }
  ]
}
Ground every finding in real files from the repository."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        payload = {
            "test_results": evidence.test_results,
            "test_files": evidence.discovery.get("test_files", []),
            "changed_files": evidence.changed_files,
            "file_diffs": evidence.file_diffs,
            "raw_diff": evidence.raw_diff[:12000],
        }
        return json.dumps(payload, indent=2)
