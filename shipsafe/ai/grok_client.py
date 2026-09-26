"""Official Grok (xAI) client integration."""

import json
import os
import httpx
from typing import Optional, Dict, Any
from .provider import AIProvider


class GrokProvider(AIProvider):
    """Grok AI client communicating with xAI API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("XAI_API_KEY", "")
        self.model = model or os.environ.get("XAI_MODEL", "grok-4.7")
        self.api_url = "https://api.x.ai/v1/chat/completions"

    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute chat completion with Grok."""
        # If API key is missing or dummy, return deterministic mock JSON response
        if not self.api_key or self.api_key.startswith("your_") or self.api_key == "test":
            from .mock_provider import MockProvider
            mock = MockProvider()
            return await mock.analyze(prompt, system_prompt, schema)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for strict factual investigation
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
