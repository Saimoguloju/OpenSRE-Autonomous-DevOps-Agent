"""
OpenSRE — Multi-Channel Notification Dispatcher
Fans out incident alerts to ALL configured channels simultaneously:
  • Slack   (with interactive Fix It / Ignore buttons)
  • Telegram (rich Markdown messages)
  • WhatsApp (via Twilio)
  • Console  (always — useful for development and as a fallback)

Add a new channel by:
  1. Create notifications/<channel>_notifier.py with send_alert() / send_update()
  2. Import and register it in NotificationDispatcher.__init__()
"""
import asyncio
import logging
from typing import Optional

from agent.state import IncidentState
from config import config
from notifications.slack_bot import SlackNotifier
from notifications.telegram_notifier import TelegramNotifier
from notifications.whatsapp_notifier import WhatsAppNotifier

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Sends alerts to every enabled notification channel in parallel.
    Failures in one channel do NOT block others.
    """

    def __init__(self, store=None):
        self.slack = SlackNotifier(store=store)
        self.telegram = TelegramNotifier()
        self.whatsapp = WhatsAppNotifier()

        # Log which channels are active
        active = []
        if self.slack._enabled:
            active.append("Slack")
        if self.telegram._enabled:
            active.append("Telegram")
        if self.whatsapp._enabled:
            active.append("WhatsApp")
        if not active:
            active.append("Console (fallback)")

        logger.info("Notification channels active: %s", ", ".join(active))

    def start_socket_mode(self):
        """Start Slack socket mode (interactive button callbacks)."""
        self.slack.start_socket_mode()

    async def send_alert(self, incident: IncidentState) -> Optional[str]:
        """
        Broadcast the incident to all channels at once (asyncio.gather).
        Returns the Slack message timestamp if Slack is enabled, else None.
        """
        tasks = []

        # Slack returns a ts (timestamp) used for message updates
        slack_task = asyncio.create_task(
            self.slack.send_alert(incident), name="slack_alert"
        )
        tasks.append(slack_task)
        tasks.append(asyncio.create_task(self.telegram.send_alert(incident), name="telegram_alert"))
        tasks.append(asyncio.create_task(self.whatsapp.send_alert(incident), name="whatsapp_alert"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any channel failures without crashing
        channel_names = ["Slack", "Telegram", "WhatsApp"]
        for name, result in zip(channel_names, results):
            if isinstance(result, Exception):
                logger.error("Channel %s raised an exception: %s", name, result)

        # Slack ts is the first result
        slack_ts = results[0] if not isinstance(results[0], Exception) else None
        return slack_ts  # may be None

    async def send_update(self, incident: IncidentState):
        """Broadcast a resolution / status-update to all channels."""
        await asyncio.gather(
            self.slack.send_update(incident),
            self.telegram.send_update(incident),
            self.whatsapp.send_update(incident),
            return_exceptions=True,
        )
