"""
OpenSRE — Multi-Channel Notification Dispatcher
Fans out incident alerts to ALL configured channels simultaneously:
  • Slack    (interactive Fix It / Ignore buttons)
  • Telegram (interactive inline approve/ignore buttons)
  • WhatsApp (via Twilio)
  • Discord  (via incoming webhook)
  • Console  (always — useful for development and as a fallback)

Add a new channel by:
  1. Create notifications/<channel>_notifier.py with send_alert() / send_update()
  2. Import and register it in NotificationDispatcher.__init__()
"""

import asyncio
import logging
from typing import Optional

from agent.state import IncidentState
from notifications.slack_bot import SlackNotifier
from notifications.telegram_notifier import TelegramNotifier
from notifications.whatsapp_notifier import WhatsAppNotifier
from notifications.discord_notifier import DiscordNotifier

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Sends alerts to every enabled notification channel in parallel.
    Failures in one channel do NOT block others.
    """

    def __init__(self, store=None):
        # Slack and Telegram support interactive approval, so they need the store.
        self.slack = SlackNotifier(store=store)
        self.telegram = TelegramNotifier(store=store)
        self.whatsapp = WhatsAppNotifier()
        self.discord = DiscordNotifier()

        active = []
        if self.slack._enabled:
            active.append("Slack")
        if self.telegram._enabled:
            active.append("Telegram")
        if self.whatsapp._enabled:
            active.append("WhatsApp")
        if self.discord._enabled:
            active.append("Discord")
        if not active:
            active.append("Console (fallback)")

        logger.info("Notification channels active: %s", ", ".join(active))

    def start_listeners(self):
        """Start interactive listeners for channels that support approvals."""
        self.slack.start_socket_mode()
        self.telegram.start_polling()

    # Backwards-compatible alias.
    def start_socket_mode(self):
        self.start_listeners()

    async def send_alert(self, incident: IncidentState) -> Optional[str]:
        """
        Broadcast the incident to all channels at once (asyncio.gather).
        Returns the Slack message timestamp if Slack is enabled, else None.
        """
        # Slack is first so results[0] is its message timestamp.
        tasks = [
            asyncio.create_task(self.slack.send_alert(incident), name="slack_alert"),
            asyncio.create_task(
                self.telegram.send_alert(incident), name="telegram_alert"
            ),
            asyncio.create_task(
                self.whatsapp.send_alert(incident), name="whatsapp_alert"
            ),
            asyncio.create_task(
                self.discord.send_alert(incident), name="discord_alert"
            ),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        channel_names = ["Slack", "Telegram", "WhatsApp", "Discord"]
        for name, result in zip(channel_names, results):
            if isinstance(result, Exception):
                logger.error("Channel %s raised an exception: %s", name, result)

        slack_ts = results[0] if not isinstance(results[0], Exception) else None
        return slack_ts  # may be None

    async def send_update(self, incident: IncidentState):
        """Broadcast a resolution / status-update to all channels."""
        await asyncio.gather(
            self.slack.send_update(incident),
            self.telegram.send_update(incident),
            self.whatsapp.send_update(incident),
            self.discord.send_update(incident),
            return_exceptions=True,
        )
