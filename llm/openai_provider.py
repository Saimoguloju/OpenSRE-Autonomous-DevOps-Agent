"""OpenAI (and OpenAI-compatible) provider.

Works with the OpenAI API and any OpenAI-compatible endpoint — Azure OpenAI,
Groq, Together, OpenRouter, or a local Ollama / vLLM server — by setting
``OPENAI_BASE_URL``. The Chat Completions API is the lingua franca all of these
speak.
"""

import logging

from config import config
from llm.base import LLMProvider, ProviderNotInstalled

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        self._client = None

    @property
    def is_mock(self) -> bool:
        return config.openai_api_key == "mock_key"

    @property
    def model(self) -> str:
        return config.openai_model

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:  # pragma: no cover - import guard
                raise ProviderNotInstalled(
                    "openai", "openai", "pip install openai"
                ) from e
            # base_url=None lets the SDK use the default OpenAI endpoint.
            self._client = OpenAI(
                api_key=config.openai_api_key,
                base_url=config.openai_base_url or None,
            )
        return self._client

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=config.openai_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
