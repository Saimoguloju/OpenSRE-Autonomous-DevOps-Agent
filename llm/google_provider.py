"""Google Gemini provider (via the google-genai SDK)."""

import logging

from config import config
from llm.base import LLMProvider, ProviderNotInstalled

logger = logging.getLogger(__name__)


class GoogleProvider(LLMProvider):
    name = "google"

    def __init__(self):
        self._client = None

    @property
    def is_mock(self) -> bool:
        return config.google_api_key == "mock_key"

    @property
    def model(self) -> str:
        return config.google_model

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:  # pragma: no cover - import guard
                raise ProviderNotInstalled(
                    "google", "google-genai", "pip install google-genai"
                ) from e
            self._client = genai.Client(api_key=config.google_api_key)
        return self._client

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        client = self._get_client()
        from google.genai import types

        response = client.models.generate_content(
            model=config.google_model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text or ""
