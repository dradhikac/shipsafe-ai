"""Abstract AI Provider base class and factory."""

import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class AIProvider(ABC):
    """Abstract interface for AI model execution."""

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute model reasoning and return response string (typically JSON)."""
        pass


def get_ai_provider() -> AIProvider:
    """Factory returning configured AI provider based on environment variables."""
    provider_type = os.environ.get("AI_PROVIDER", "grok").lower()

    if provider_type == "mock":
        from .mock_provider import MockProvider
        return MockProvider()

    # Default to Grok
    from .grok_client import GrokProvider
    return GrokProvider()
