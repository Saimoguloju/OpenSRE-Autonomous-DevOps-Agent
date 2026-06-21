"""Tests for notification message builders and the multi-channel dispatcher."""

import asyncio

import pytest

from agent.state import new_incident
from notifications.slack_bot import _build_incident_blocks
from notifications.telegram_notifier import (
    _build_alert_message as tg_alert,
    _build_resolution_message as tg_resolution,
)
from notifications.whatsapp_notifier import (
    _build_whatsapp_message as wa_alert,
    _build_resolution_message as wa_resolution,
)
from notifications.dispatcher import NotificationDispatcher


@pytest.fixture
def incident(mock_metric):
    inc = new_incident(mock_metric, "critical")
    inc["root_cause"] = "Pod in CrashLoopBackOff due to OOMKill."
    inc["recommended_action"] = "kubectl delete pod api-pod -n production"
    return inc


# ── Slack Block Kit ──────────────────────────────────────────────────────────


def test_slack_blocks_include_actions_and_id(incident):
    blocks = _build_incident_blocks(incident)
    serialized = str(blocks)
    assert incident["incident_id"] in serialized
    assert "pod_crash_loop" in serialized
    # Interactive approve/ignore buttons must be present.
    action_block = next(b for b in blocks if b["type"] == "actions")
    action_ids = {el["action_id"] for el in action_block["elements"]}
    assert action_ids == {"approve_action", "ignore_action"}


# ── Telegram ─────────────────────────────────────────────────────────────────


def test_telegram_alert_message_contents(incident):
    msg = tg_alert(incident)
    assert "CRITICAL" in msg
    assert incident["incident_id"] in msg
    assert "Pod in CrashLoopBackOff" in msg


def test_telegram_resolution_message(incident):
    incident["status"] = "resolved"
    incident["action_taken"] = "Restarted pod."
    msg = tg_resolution(incident)
    assert "Resolved" in msg
    assert "Restarted pod." in msg


# ── WhatsApp ─────────────────────────────────────────────────────────────────


def test_whatsapp_alert_message_contents(incident):
    msg = wa_alert(incident)
    assert "CRITICAL" in msg
    assert incident["incident_id"] in msg
    assert "approve" in msg.lower()


def test_whatsapp_resolution_message(incident):
    incident["status"] = "ignored"
    msg = wa_resolution(incident)
    assert "IGNORED" in msg


# ── Dispatcher fan-out (all channels disabled -> console fallback) ────────────


def test_dispatcher_send_alert_no_channels(incident):
    # No tokens configured in the test env, so every channel is disabled and
    # the dispatcher must not raise; Slack ts is None.
    dispatcher = NotificationDispatcher(store=None)
    slack_ts = asyncio.run(dispatcher.send_alert(incident))
    assert slack_ts is None


def test_dispatcher_send_update_no_channels(incident):
    dispatcher = NotificationDispatcher(store=None)
    # Should complete without raising even when nothing is configured.
    asyncio.run(dispatcher.send_update(incident))
