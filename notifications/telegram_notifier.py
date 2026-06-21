"""
OpenSRE — Telegram Notifier (with interactive approval)

Sends incident alerts to a Telegram chat and — when a store is provided — attaches
inline Approve / Ignore buttons. Button presses are handled by a background
long-poller that resumes the LangGraph pipeline, mirroring the Slack flow.

Setup:
  1. Message @BotFather on Telegram → /newbot → copy the token
  2. Add the bot to your group/channel and make it an admin
  3. Get your chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
  4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env
"""

import logging
import threading
from typing import Optional

from agent.state import IncidentState
from config import config

logger = logging.getLogger(__name__)

# callback_data format: "opensre:<action>:<incident_id>" (well under Telegram's 64B cap)
_CB_PREFIX = "opensre"

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


def _parse_callback_data(data: str) -> Optional[tuple]:
    """Parse "opensre:<action>:<incident_id>" -> (action, incident_id) or None."""
    parts = (data or "").split(":", 2)
    if len(parts) == 3 and parts[0] == _CB_PREFIX and parts[1] in ("approve", "ignore"):
        return parts[1], parts[2]
    return None


class TelegramNotifier:
    """Sends incident alerts to a Telegram chat using python-telegram-bot v20+.

    When constructed with a ``store``, alerts carry inline Approve / Ignore
    buttons and a background poller resumes the pipeline on a button press.
    """

    def __init__(self, store=None):
        self._bot = None
        self.store = store
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

    def _keyboard(self, incident_id: str):
        """Build the inline Approve / Ignore keyboard (None if non-interactive)."""
        if not self.store:
            return None
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Fix It", callback_data=f"{_CB_PREFIX}:approve:{incident_id}"
                    ),
                    InlineKeyboardButton(
                        "🚫 Ignore", callback_data=f"{_CB_PREFIX}:ignore:{incident_id}"
                    ),
                ]
            ]
        )

    def _apply_decision(self, action: str, incident_id: str) -> Optional[IncidentState]:
        """Apply a human decision and resume the pipeline. Returns the result state.

        Pure of any Telegram I/O so it can be unit-tested directly.
        """
        if not self.store:
            return None
        if action == "approve":
            self.store.update_status(incident_id, "acting", human_approved=True)
        else:
            self.store.update_status(incident_id, "ignored", human_approved=False)
        incident = self.store.get(incident_id)
        if incident is None:
            return None
        from agent.graph import resume_incident

        result = resume_incident(incident)
        self.store.save(result)
        return result

    async def send_alert(self, incident: IncidentState) -> bool:
        """Send an incident alert (with approval buttons if interactive)."""
        if not self._enabled:
            return False

        try:
            message = _build_alert_message(incident)
            await self._bot.send_message(
                chat_id=config.telegram_chat_id,
                text=message,
                parse_mode="Markdown",
                reply_markup=self._keyboard(incident["incident_id"]),
            )
            logger.info("Telegram alert sent for incident %s", incident["incident_id"])
            return True
        except Exception as e:
            logger.error("Telegram send_alert failed: %s", e)
            return False

    async def _on_callback(self, update, context):
        """Handle an inline-button press: resume the incident and report back."""
        query = update.callback_query
        await query.answer()
        parsed = _parse_callback_data(query.data)
        if parsed is None:
            return
        action, incident_id = parsed
        logger.info("Telegram human %s for incident %s", action, incident_id)

        result = self._apply_decision(action, incident_id)

        # Remove the buttons so the decision can't be double-submitted.
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:  # pragma: no cover - best-effort UI cleanup
            logger.debug("Could not clear Telegram keyboard: %s", e)

        if result is not None:
            try:
                await context.bot.send_message(
                    chat_id=config.telegram_chat_id,
                    text=_build_resolution_message(result),
                    parse_mode="Markdown",
                )
            except Exception as e:  # pragma: no cover - best-effort
                logger.error("Telegram resolution message failed: %s", e)

    def start_polling(self):
        """Start the inline-button listener in a daemon thread (no-op if disabled)."""
        if not self._enabled or not self.store:
            logger.info(
                "Telegram interactive approval not started (disabled or no store)."
            )
            return

        def _run():
            import asyncio

            try:
                from telegram.ext import Application, CallbackQueryHandler

                asyncio.set_event_loop(asyncio.new_event_loop())
                app = Application.builder().token(config.telegram_bot_token).build()
                app.add_handler(
                    CallbackQueryHandler(self._on_callback, pattern=f"^{_CB_PREFIX}:")
                )
                # stop_signals=None: signal handlers only work on the main thread.
                app.run_polling(stop_signals=None, close_loop=False)
            except Exception as e:  # pragma: no cover - runtime/network dependent
                logger.error("Telegram poller stopped: %s", e)

        threading.Thread(target=_run, daemon=True, name="telegram-poller").start()
        logger.info("Telegram interactive approval started (polling).")

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
