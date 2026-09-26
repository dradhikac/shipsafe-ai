"""Official Groq (GroqCloud) client integration."""

import json
import os
import httpx
from typing import Optional, Dict, Any
from .provider import AIProvider


class GroqProvider(AIProvider):
    """Groq LPU client communicating with GroqCloud API."""

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model or os.environ.get("GROQ_MODEL") or self.DEFAULT_MODEL
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute chat completion with Groq."""
        # If API key is missing or dummy, return deterministic mock JSON response
        if not self.api_key or self.api_key.startswith("your_") or self.api_key == "test":
            from .mock_provider import MockProvider
            mock = MockProvider()
            return await mock.analyze(prompt, system_prompt, schema)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        sys_content = (system_prompt or "You are a specialist analysis agent.") + "\nYou MUST return your answer as a valid JSON object."
        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Groq API call failed: {e}")

