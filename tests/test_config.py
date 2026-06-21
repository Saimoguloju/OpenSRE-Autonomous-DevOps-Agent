"""Tests for configuration parsing and validation."""

import pytest

from config import Config


def test_validate_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = Config()
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        cfg.validate()


def test_validate_passes_with_api_key_and_console_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SIMULATION_MODE", "true")
    # No channels configured -> warns but does not raise.
    Config().validate()


def test_validate_requires_db_url_when_not_simulating(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SIMULATION_MODE", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Config().validate()


def test_whatsapp_recipients_parsing(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ALERT_NUMBERS", "whatsapp:+1111, whatsapp:+2222 , ")
    cfg = Config()
    assert cfg.whatsapp_recipients == ["whatsapp:+1111", "whatsapp:+2222"]


def test_whatsapp_recipients_empty(monkeypatch):
    monkeypatch.delenv("WHATSAPP_ALERT_NUMBERS", raising=False)
    assert Config().whatsapp_recipients == []


def test_auto_remediate_defaults_off(monkeypatch):
    monkeypatch.delenv("AUTO_REMEDIATE", raising=False)
    assert Config().auto_remediate is False


def test_auto_remediate_enabled(monkeypatch):
    monkeypatch.setenv("AUTO_REMEDIATE", "true")
    assert Config().auto_remediate is True


def test_auto_approve_min_confidence_default(monkeypatch):
    monkeypatch.delenv("AUTO_APPROVE_MIN_CONFIDENCE", raising=False)
    assert Config().auto_approve_min_confidence == 80


def test_threshold_defaults(monkeypatch):
    for var in ("CPU_THRESHOLD_PCT", "MEMORY_THRESHOLD_PCT", "POLL_INTERVAL_SECONDS"):
        monkeypatch.delenv(var, raising=False)
    cfg = Config()
    assert cfg.cpu_threshold_pct == 85
    assert cfg.memory_threshold_pct == 90
    assert cfg.poll_interval_seconds == 30
