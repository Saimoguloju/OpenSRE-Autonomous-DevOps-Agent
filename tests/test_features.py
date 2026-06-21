"""Tests for the newly added features: Discord, Telegram approval, observability."""

import asyncio

import pytest

from config import config
from agent.state import new_incident

# ── Discord notifier ─────────────────────────────────────────────────────────


@pytest.fixture
def incident(mock_metric):
    inc = new_incident(mock_metric, "critical")
    inc["root_cause"] = "Pod OOMKilled."
    inc["recommended_action"] = "kubectl delete pod api-pod -n production"
    return inc


def test_discord_payload_structure(incident):
    from notifications.discord_notifier import _build_alert_payload

    payload = _build_alert_payload(incident)
    assert payload["username"] == "OpenSRE"
    embed = payload["embeds"][0]
    assert "CRITICAL" in embed["title"]
    assert embed["color"] == 15158332  # red
    serialized = str(embed["fields"])
    assert incident["incident_id"] in serialized
    assert "pod_crash_loop" in serialized


def test_discord_disabled_returns_false(incident, monkeypatch):
    monkeypatch.setattr(config, "discord_webhook_url", "")
    from notifications.discord_notifier import DiscordNotifier

    notifier = DiscordNotifier()
    assert notifier._enabled is False
    assert asyncio.run(notifier.send_alert(incident)) is False


def test_discord_enabled_posts(incident, monkeypatch):
    import requests

    monkeypatch.setattr(config, "discord_webhook_url", "https://discord/webhook")
    from notifications.discord_notifier import DiscordNotifier

    calls = {}

    class _Resp:
        status_code = 204
        text = ""

    def _fake_post(url, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        return _Resp()

    monkeypatch.setattr(requests, "post", _fake_post)

    notifier = DiscordNotifier()
    assert asyncio.run(notifier.send_alert(incident)) is True
    assert calls["url"] == "https://discord/webhook"
    assert calls["json"]["embeds"][0]["title"].startswith("🚨")


# ── Telegram interactive approval ────────────────────────────────────────────


def test_telegram_parse_callback_data():
    from notifications.telegram_notifier import _parse_callback_data

    assert _parse_callback_data("opensre:approve:abc123") == ("approve", "abc123")
    assert _parse_callback_data("opensre:ignore:xyz") == ("ignore", "xyz")
    assert _parse_callback_data("garbage") is None
    assert _parse_callback_data("opensre:delete:abc") is None


def test_telegram_apply_decision_approve(temp_db, mock_metric, monkeypatch, tmp_path):
    # Avoid network/LLM in post-mortem generation; isolate file output.
    import agent.nodes as nodes

    monkeypatch.setattr(nodes, "_complete", lambda system, user, max_tokens=1024: "PM")
    monkeypatch.chdir(tmp_path)

    from notifications.telegram_notifier import TelegramNotifier

    inc = new_incident(mock_metric, "critical")
    inc["recommended_action"] = "kubectl delete pod api-pod -n production"
    inc["status"] = "awaiting_approval"
    temp_db.save(inc)

    notifier = TelegramNotifier(store=temp_db)
    result = notifier._apply_decision("approve", inc["incident_id"])
    assert result["status"] == "resolved"
    assert "[SIMULATION]" in result["action_taken"]
    # Persisted.
    assert temp_db.get(inc["incident_id"])["status"] == "resolved"


def test_telegram_apply_decision_ignore(temp_db, mock_metric):
    from notifications.telegram_notifier import TelegramNotifier

    inc = new_incident(mock_metric, "high")
    inc["status"] = "awaiting_approval"
    temp_db.save(inc)

    notifier = TelegramNotifier(store=temp_db)
    result = notifier._apply_decision("ignore", inc["incident_id"])
    assert result["status"] == "ignored"


def test_telegram_apply_decision_no_store(mock_metric):
    from notifications.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier(store=None)
    assert notifier._apply_decision("approve", "missing") is None


# ── Observability: store counts, gauge, health ───────────────────────────────


def test_active_count_by_severity(temp_db, mock_metric):
    open_inc = new_incident(mock_metric, "high")
    open_inc["status"] = "awaiting_approval"
    temp_db.save(open_inc)

    resolved = new_incident(mock_metric, "low")
    resolved["status"] = "resolved"
    temp_db.save(resolved)

    counts = temp_db.active_count_by_severity()
    assert counts.get("high") == 1
    assert "low" not in counts  # resolved ones are excluded


def test_refresh_active_incidents_sets_gauge(temp_db, mock_metric):
    from agent.metrics import ACTIVE_INCIDENTS, refresh_active_incidents

    inc = new_incident(mock_metric, "critical")
    inc["status"] = "awaiting_approval"
    temp_db.save(inc)

    refresh_active_incidents(temp_db)
    assert ACTIVE_INCIDENTS.labels(severity="critical")._value.get() == 1.0
    # A severity with no open incidents is reset to 0.
    assert ACTIVE_INCIDENTS.labels(severity="low")._value.get() == 0.0


def test_observe_helpers_dont_raise():
    from agent.metrics import observe_resolution, observe_approval

    # Valid and invalid timestamps must both be safe.
    observe_resolution("2020-01-01T00:00:00+00:00")
    observe_resolution("not-a-date")
    observe_approval("2020-01-01T00:00:00+00:00")
    observe_approval(None)


def test_health_payload(temp_db, mock_metric):
    from observability import health_payload

    inc = new_incident(mock_metric, "high")
    inc["status"] = "awaiting_approval"
    temp_db.save(inc)

    payload = health_payload(temp_db)
    assert payload["status"] == "ok"
    assert payload["active_incidents"] == 1
    assert "llm_provider" in payload
    assert "model" in payload
