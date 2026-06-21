"""
OpenSRE — Discord Notifier (via incoming webhook)

Setup:
  1. In your Discord server: Channel → Edit Channel → Integrations → Webhooks
  2. New Webhook → name it (e.g. "OpenSRE") → Copy Webhook URL
  3. Set DISCORD_WEBHOOK_URL in your .env

Notify-only: incoming webhooks can post messages but cannot present interactive
buttons (that needs a full Discord bot application). Approvals happen via Slack or
Telegram; Discord mirrors the alert and resolution updates.
"""

import asyncio
import logging

from agent.state import IncidentState
from config import config

logger = logging.getLogger(__name__)

# Discord embed colors (decimal) by severity.
SEVERITY_COLOR = {
    "low": 3066993,  # green
    "medium": 16776960,  # yellow
    "high": 15105570,  # orange
    "critical": 15158332,  # red
}


def _build_alert_payload(incident: IncidentState) -> dict:
    metric = incident["metric"]
    color = SEVERITY_COLOR.get(incident["severity"], 9807270)
    return {
        "username": "OpenSRE",
        "embeds": [
            {
                "title": f"🚨 OpenSRE Incident — {incident['severity'].upper()}",
                "color": color,
                "fields": [
                    {
                        "name": "Incident ID",
                        "value": f"`{incident['incident_id']}`",
                        "inline": True,
                    },
                    {"name": "Metric", "value": metric["name"], "inline": True},
                    {"name": "Host", "value": metric["host"], "inline": False},
                    {
                        "name": "Value",
                        "value": f"{metric['value']} {metric['unit']} (threshold: {metric['threshold']})",
                        "inline": False,
                    },
                    {
                        "name": "Root Cause",
                        "value": incident.get("root_cause") or "Analyzing...",
                        "inline": False,
                    },
                    {
                        "name": "Recommended Action",
                        "value": f"`{incident.get('recommended_action') or 'Pending...'}`",
                        "inline": False,
                    },
                ],
            }
        ],
    }


def _build_resolution_payload(incident: IncidentState) -> dict:
    emoji = "✅" if incident["status"] == "resolved" else "🚫"
    return {
        "username": "OpenSRE",
        "content": (
            f"{emoji} Incident `{incident['incident_id']}` — "
            f"**{incident['status'].replace('_', ' ').upper()}**\n"
            f"Action: {incident.get('action_taken') or 'N/A'}"
        ),
    }


class DiscordNotifier:
    """Posts incident alerts to a Discord channel via an incoming webhook."""

    def __init__(self):
        self._enabled = bool(config.discord_webhook_url)
        if self._enabled:
            logger.info("Discord notifier enabled.")

    def _post(self, payload: dict) -> bool:
        try:
            import requests

            resp = requests.post(config.discord_webhook_url, json=payload, timeout=10)
            # Discord returns 204 No Content on success.
            if resp.status_code >= 300:
                logger.error(
                    "Discord webhook returned %s: %s", resp.status_code, resp.text
                )
                return False
            return True
        except Exception as e:
            logger.error("Discord post failed: %s", e)
            return False

    async def send_alert(self, incident: IncidentState) -> bool:
        if not self._enabled:
            return False
        # requests is blocking — run it off the event loop so we don't stall siblings.
        return await asyncio.to_thread(self._post, _build_alert_payload(incident))

    async def send_update(self, incident: IncidentState) -> bool:
        if not self._enabled:
            return False
        return await asyncio.to_thread(self._post, _build_resolution_payload(incident))
