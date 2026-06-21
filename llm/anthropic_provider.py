"""Anthropic Claude provider (the OpenSRE default)."""

import logging

from config import config
from llm.base import LLMProvider, ProviderNotInstalled

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self):
        self._client = None

    @property
    def is_mock(self) -> bool:
        return config.anthropic_api_key == "mock_key"

    @property
    def model(self) -> str:
        return config.model

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover - import guard
                raise ProviderNotInstalled(
                    "anthropic", "anthropic", "pip install anthropic"
                ) from e
            self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        return self._client

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=config.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
