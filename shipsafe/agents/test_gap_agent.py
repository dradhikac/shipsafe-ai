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
Highlight missing tests, deleted regression paths, or unasserted edge cases in source code changes.

CRITICAL INSTRUCTION:
Do NOT create a test gap finding for README.md or documentation files.
If the changed code is covered by tests, or tests pass with no missing test assertions, return:
{
  "agent": "test_gap",
  "findings": []
}
Never invent a test gap finding. Zero findings is a valid and expected result when test coverage is sufficient.

Schema when findings exist:
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
      "evidence_type": "test_failure",
      "affected_components": ["ServiceUnderTest"],
      "recommendation": "Specific test cases and assertions to add",
      "confidence": 0.90
    }
  ]
}
Ground every finding in real source or test files from the repository."""

    def build_prompt(self, evidence: EvidencePack) -> str:
        # Strictly exclude documentation files from changed files
        code_changed_files = [
            f for f in evidence.changed_files
            if not f.lower().endswith(("readme.md", ".txt", ".md", ".png", ".jpg", ".svg"))
        ]
        payload = {
            "agent_name": self.name,
            "test_results": evidence.test_results,
            "test_files": evidence.discovery.get("test_files", []),
            "changed_files": code_changed_files,
            "file_diffs": [
                d for d in evidence.file_diffs
                if not d.get("file_path", "").lower().endswith(("readme.md", ".txt", ".md"))
            ],
            "raw_diff": evidence.raw_diff[:12000],
        }

        return json.dumps(payload, indent=2)

