"""
OpenSRE — Telegram Notifier
Sends incident alerts to a Telegram chat/group/channel via the Bot API.

Setup:
  1. Message @BotFather on Telegram → /newbot → copy the token
  2. Add the bot to your group/channel and make it an admin
  3. Get your chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
  4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env
"""

import logging
from typing import Optional

from agent.state import IncidentState
from config import config

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}

STATUS_EMOJI = {
    "resolved": "✅",
    "ignored": "🚫",
    "acting": "⚙️",
    "awaiting_approval": "⏳",
    "detected": "🔍",
    "analyzing": "🧠",
}


def _build_alert_message(incident: IncidentState) -> str:
    """Build a clean Markdown message for Telegram."""
    metric = incident["metric"]
    emoji = SEVERITY_EMOJI.get(incident["severity"], "⚪")
    status_emoji = STATUS_EMOJI.get(incident["status"], "")

    lines = [
        f"{emoji} *OpenSRE Incident — {incident['severity'].upper()}*",
        "",
        f"📋 *ID:* `{incident['incident_id']}`",
        f"📊 *Metric:* {metric['name']}",
        f"🖥️ *Host:* `{metric['host']}`",
        f"📈 *Value:* {metric['value']} {metric['unit']} _(threshold: {metric['threshold']})_",
        f"{status_emoji} *Status:* {incident['status'].replace('_', ' ').title()}",
        "",
        f"🔎 *Root Cause:*",
        f"{incident.get('root_cause') or '_Analyzing..._'}",
        "",
        f"🛠️ *Recommended Action:*",
        f"`{incident.get('recommended_action') or 'Pending...'}`",
    ]

    if incident.get("action_taken"):
        lines += ["", f"✅ *Action Taken:*", incident["action_taken"]]

    return "\n".join(lines)


def _build_resolution_message(incident: IncidentState) -> str:
    """Short resolution / update message."""
    emoji = "✅" if incident["status"] == "resolved" else "🚫"
    return (
        f"{emoji} *Incident `{incident['incident_id']}` — "
        f"{incident['status'].replace('_', ' ').title()}*\n"
        f"Action: {incident.get('action_taken') or 'N/A'}"
    )


class TelegramNotifier:
    """Sends incident alerts to a Telegram chat using python-telegram-bot v20+."""

    def __init__(self):
        self._bot = None
        self._enabled = bool(config.telegram_bot_token and config.telegram_chat_id)

        if self._enabled:
            try:
                from telegram import Bot

                self._bot = Bot(token=config.telegram_bot_token)
                logger.info(
                    "Telegram notifier enabled → chat_id=%s", config.telegram_chat_id
                )
            except ImportError:
                logger.warning(
                    "python-telegram-bot not installed — Telegram notifications disabled. "
                    "Run: pip install python-telegram-bot"
                )
                self._enabled = False

    async def send_alert(self, incident: IncidentState) -> bool:
        """Send an incident alert. Returns True on success."""
        if not self._enabled:
            return False

        try:
            message = _build_alert_message(incident)
            await self._bot.send_message(
                chat_id=config.telegram_chat_id,
                text=message,
                parse_mode="Markdown",
            )
            logger.info("Telegram alert sent for incident %s", incident["incident_id"])
            return True
        except Exception as e:
            logger.error("Telegram send_alert failed: %s", e)
            return False

    async def send_update(self, incident: IncidentState) -> bool:
        """Send a resolution/status update message."""
        if not self._enabled:
            return False

        try:
            message = _build_resolution_message(incident)
            await self._bot.send_message(
                chat_id=config.telegram_chat_id,
                text=message,
                parse_mode="Markdown",
            )
            logger.info("Telegram update sent for incident %s", incident["incident_id"])
            return True
        except Exception as e:
            logger.error("Telegram send_update failed: %s", e)
            return False
