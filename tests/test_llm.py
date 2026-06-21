"""Tests for the pluggable LLM provider layer."""

import pytest

import llm
from config import config


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    """Each test gets a fresh provider cache so config changes take effect."""
    llm.reset_cache()
    yield
    llm.reset_cache()


def test_default_provider_is_anthropic(monkeypatch):
    monkeypatch.setattr(config, "llm_provider", "anthropic")
    provider = llm.get_provider()
    assert provider.name == "anthropic"


def test_provider_aliases_resolve(monkeypatch):
    assert llm.get_provider("claude").name == "anthropic"
    assert llm.get_provider("gpt").name == "openai"
    assert llm.get_provider("ollama").name == "openai"
    assert llm.get_provider("gemini").name == "google"


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        llm.get_provider("not-a-real-provider")


def test_anthropic_provider_is_mock_with_mock_key(monkeypatch):
    # conftest sets ANTHROPIC_API_KEY=mock_key -> the singleton reflects it.
    monkeypatch.setattr(config, "anthropic_api_key", "mock_key")
    assert llm.get_provider("anthropic").is_mock is True


def test_anthropic_provider_reports_model(monkeypatch):
    monkeypatch.setattr(config, "model", "claude-sonnet-4-6")
    assert llm.get_provider("anthropic").model == "claude-sonnet-4-6"


def test_openai_provider_uses_configured_model(monkeypatch):
    monkeypatch.setattr(config, "openai_model", "gpt-4o-mini")
    assert llm.get_provider("openai").model == "gpt-4o-mini"


def test_google_provider_uses_configured_model(monkeypatch):
    monkeypatch.setattr(config, "google_model", "gemini-2.0-flash")
    assert llm.get_provider("google").model == "gemini-2.0-flash"


def test_provider_cache_returns_same_instance():
    a = llm.get_provider("anthropic")
    b = llm.get_provider("anthropic")
    assert a is b


# ── Config-level provider helpers ────────────────────────────────────────────


def test_active_model_tracks_provider(monkeypatch):
    monkeypatch.setattr(config, "llm_provider", "openai")
    monkeypatch.setattr(config, "openai_model", "gpt-4o")
    assert config.active_model == "gpt-4o"

    monkeypatch.setattr(config, "llm_provider", "google")
    monkeypatch.setattr(config, "google_model", "gemini-2.0-flash")
    assert config.active_model == "gemini-2.0-flash"

    monkeypatch.setattr(config, "llm_provider", "anthropic")
    monkeypatch.setattr(config, "model", "claude-sonnet-4-6")
    assert config.active_model == "claude-sonnet-4-6"
