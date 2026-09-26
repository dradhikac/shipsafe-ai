"""Base agent execution harness with error recovery and schema enforcement."""

import json
import re
from typing import Dict, Any, Optional
from pydantic import ValidationError
from shipsafe.ai.provider import AIProvider
from shipsafe.ai.schemas import AgentReport, AgentFinding
from shipsafe.core.evidence import EvidencePack


class BaseSpecialistAgent:
    """Base harness for Grok specialist agents."""

    name: str = "base"
    system_prompt: str = ""

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def build_prompt(self, evidence: EvidencePack) -> str:
        """Subclasses customize the evidence slice sent to the agent."""
        d = evidence.to_dict()
        d["agent_name"] = self.name
        return json.dumps(d, indent=2)


    async def run(self, evidence: EvidencePack) -> AgentReport:
        """Execute agent analysis and enforce structured schema output."""
        prompt = self.build_prompt(evidence)
        raw_response = await self.provider.analyze(
            prompt=prompt,
            system_prompt=self.system_prompt
        )

        return self._parse_and_validate(raw_response)

    def _parse_and_validate(self, text: str) -> AgentReport:
        """Parse JSON response, extracting object if wrapped in markdown code blocks."""
        cleaned = text.strip()
        if "```" in cleaned:
            # Extract JSON block
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if m:
                cleaned = m.group(1).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                if "agent" not in data:
                    data["agent"] = self.name
                # Ensure each finding has agent set
                if "findings" in data and isinstance(data["findings"], list):
                    for f in data["findings"]:
                        if isinstance(f, dict) and not f.get("agent"):
                            f["agent"] = self.name
                return AgentReport(**data)
            else:
                raise ValueError(f"Agent {self.name} expected JSON object, got {type(data).__name__}")
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Agent {self.name} received malformed model output: {e} | Raw: {cleaned[:200]}")

