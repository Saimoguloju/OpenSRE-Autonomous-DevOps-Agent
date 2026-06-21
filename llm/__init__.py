"""Pluggable LLM provider layer for OpenSRE.

The agent talks to whatever provider ``LLM_PROVIDER`` selects through a single
``complete()`` method, so swapping vendors is a config change — no code edits.

Supported values for ``LLM_PROVIDER``:
  • ``anthropic`` (default) — Claude
  • ``openai``              — OpenAI, or any OpenAI-compatible endpoint
                              (Azure / Groq / Together / OpenRouter / Ollama)
                              via ``OPENAI_BASE_URL``
  • ``google`` / ``gemini`` — Google Gemini
"""

from config import config
from llm.base import LLMProvider, ProviderNotInstalled

# Map of canonical name -> builder. Aliases are normalized in get_provider().
_BUILDERS = {}


def _register():
    """Lazily import provider classes so missing optional SDKs never break import."""
    if _BUILDERS:
        return
    from llm.anthropic_provider import AnthropicProvider
    from llm.openai_provider import OpenAIProvider
    from llm.google_provider import GoogleProvider

    _BUILDERS["anthropic"] = AnthropicProvider
    _BUILDERS["openai"] = OpenAIProvider
    _BUILDERS["google"] = GoogleProvider


_ALIASES = {
    "claude": "anthropic",
    "gpt": "openai",
    "openai-compatible": "openai",
    "azure": "openai",
    "ollama": "openai",
    "groq": "openai",
    "gemini": "google",
    "google-genai": "google",
}

_cache: dict[str, LLMProvider] = {}


def get_provider(name: str | None = None) -> LLMProvider:
    """Return a cached provider instance for ``name`` (or the configured default)."""
    _register()
    resolved = (name or config.llm_provider or "anthropic").strip().lower()
    resolved = _ALIASES.get(resolved, resolved)
    if resolved not in _BUILDERS:
        valid = ", ".join(sorted(set(_BUILDERS) | set(_ALIASES)))
        raise ValueError(f"Unknown LLM_PROVIDER '{resolved}'. Valid options: {valid}.")
    if resolved not in _cache:
        _cache[resolved] = _BUILDERS[resolved]()
    return _cache[resolved]


def reset_cache() -> None:
    """Clear cached provider instances (used by tests that flip config)."""
    _cache.clear()


__all__ = ["get_provider", "reset_cache", "LLMProvider", "ProviderNotInstalled"]
