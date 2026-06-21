"""
OpenSRE — WhatsApp Notifier (via Twilio)
Sends incident alerts to one or more WhatsApp numbers.

Setup:
  1. Create a free account at https://www.twilio.com
  2. Go to Console → Messaging → Try it out → Send a WhatsApp message
  3. Connect your personal WhatsApp to the sandbox by sending the join code
  4. Copy your Account SID and Auth Token from https://console.twilio.com
  5. Set the following in your .env:
       TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
       TWILIO_AUTH_TOKEN=your_auth_token
       TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   ← sandbox number (default)
       WHATSAPP_ALERT_NUMBERS=whatsapp:+91XXXXXXXXXX,whatsapp:+1XXXXXXXXXX

  Production: Replace TWILIO_WHATSAPP_FROM with your approved WhatsApp Business number.
"""

import logging

from agent.state import IncidentState
from config import config

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}


def _build_whatsapp_message(incident: IncidentState) -> str:
    """
    WhatsApp does not support rich markdown like Slack or Telegram.
    We use plain Unicode + emojis for formatting — works universally.
    """
    metric = incident["metric"]
    emoji = SEVERITY_EMOJI.get(incident["severity"], "⚪")

    lines = [
        f"{emoji} *OpenSRE Alert — {incident['severity'].upper()}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📋 ID: {incident['incident_id']}",
        f"📊 Metric: {metric['name']}",
        f"🖥️ Host: {metric['host']}",
        f"📈 Value: {metric['value']} {metric['unit']} (threshold: {metric['threshold']})",
        f"🔎 Root Cause:",
        f"   {incident.get('root_cause') or 'Analyzing...'}",
        f"",
        f"🛠️ Recommended Fix:",
        f"   {incident.get('recommended_action') or 'Pending...'}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Approve or ignore from Slack or Telegram",
        f"(WhatsApp is notify-only).",
    ]

    return "\n".join(lines)


def _build_resolution_message(incident: IncidentState) -> str:
    emoji = "✅" if incident["status"] == "resolved" else "🚫"
    return (
        f"{emoji} Incident {incident['incident_id']} — "
        f"{incident['status'].replace('_', ' ').upper()}\n"
        f"Action: {incident.get('action_taken') or 'N/A'}"
    )


class WhatsAppNotifier:
    """Sends incident alerts to WhatsApp numbers via Twilio API."""

    def __init__(self):
        self._client = None
        self._enabled = bool(
            config.twilio_account_sid
            and config.twilio_auth_token
            and config.whatsapp_recipients
        )

        if self._enabled:
            try:
                from twilio.rest import Client

                self._client = Client(
                    config.twilio_account_sid, config.twilio_auth_token
                )
                logger.info(
                    "WhatsApp notifier enabled → %d recipient(s)",
                    len(config.whatsapp_recipients),
                )
            except ImportError:
                logger.warning(
                    "twilio library not installed — WhatsApp notifications disabled. "
                    "Run: pip install twilio"
                )
                self._enabled = False

    async def send_alert(self, incident: IncidentState) -> bool:
        """Send an incident alert to all configured WhatsApp numbers."""
        if not self._enabled:
            return False

        message_body = _build_whatsapp_message(incident)
        success = True

        for recipient in config.whatsapp_recipients:
            try:
                self._client.messages.create(
                    body=message_body,
                    from_=config.twilio_whatsapp_from,
                    to=recipient,
                )
                logger.info(
                    "WhatsApp alert sent to %s for incident %s",
                    recipient,
                    incident["incident_id"],
                )
            except Exception as e:
                logger.error("WhatsApp send_alert failed for %s: %s", recipient, e)
                success = False

        return success

    async def send_update(self, incident: IncidentState) -> bool:
        """Send a resolution/status update to all WhatsApp numbers."""
        if not self._enabled:
            return False

        message_body = _build_resolution_message(incident)
        success = True

        for recipient in config.whatsapp_recipients:
            try:
                self._client.messages.create(
                    body=message_body,
                    from_=config.twilio_whatsapp_from,
                    to=recipient,
                )
                logger.info(
                    "WhatsApp update sent to %s for incident %s",
                    recipient,
                    incident["incident_id"],
                )
            except Exception as e:
                logger.error("WhatsApp send_update failed for %s: %s", recipient, e)
                success = False

        return success
