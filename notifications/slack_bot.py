import asyncio
import logging
import threading
from typing import Optional

from agent.state import IncidentState
from config import config

logger = logging.getLogger(__name__)

# Reference to the main event loop — set once in start_socket_mode()
_main_loop: Optional[asyncio.AbstractEventLoop] = None

SEVERITY_EMOJI = {
    "low": ":green_circle:",
    "medium": ":yellow_circle:",
    "high": ":orange_circle:",
    "critical": ":red_circle:",
}


def _build_incident_blocks(incident: IncidentState) -> list:
    metric = incident["metric"]
    emoji = SEVERITY_EMOJI.get(incident["severity"], ":white_circle:")
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} OpenSRE Incident — {incident['severity'].upper()}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Metric:*\n{metric['name']}"},
                {"type": "mrkdwn", "text": f"*Host:*\n{metric['host']}"},
                {"type": "mrkdwn", "text": f"*Value:*\n{metric['value']} {metric['unit']} (threshold: {metric['threshold']})"},
                {"type": "mrkdwn", "text": f"*Incident ID:*\n`{incident['incident_id']}`"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{incident.get('root_cause', 'Analyzing...')}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recommended Action:*\n`{incident.get('recommended_action', 'Pending...')}`"},
        },
        {
            "type": "actions",
            "block_id": f"incident_actions_{incident['incident_id']}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Fix It"},
                    "style": "primary",
                    "action_id": "approve_action",
                    "value": incident["incident_id"],
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Ignore"},
                    "style": "danger",
                    "action_id": "ignore_action",
                    "value": incident["incident_id"],
                },
            ],
        },
    ]


class SlackNotifier:
    """Sends incident alerts to Slack and handles button callbacks."""

    def __init__(self, store=None):
        self.store = store
        self._app = None
        self._client = None
        self._enabled = bool(config.slack_bot_token)

        if self._enabled:
            try:
                from slack_bolt import App
                from slack_bolt.adapter.socket_mode import SocketModeHandler
                self._App = App
                self._SocketModeHandler = SocketModeHandler
                self._setup_app()
            except ImportError:
                logger.warning("slack_bolt not installed — Slack notifications disabled.")
                self._enabled = False

    def _setup_app(self):
        from slack_bolt import App
        self._app = App(token=config.slack_bot_token)
        self._client = self._app.client

        @self._app.action("approve_action")
        def handle_approve(ack, body, say):
            ack()
            incident_id = body["actions"][0]["value"]
            logger.info("Human approved action for incident %s", incident_id)
            if self.store:
                self.store.update_status(incident_id, "acting", human_approved=True)
                # Schedule async work onto the main event loop from this sync thread
                if _main_loop and _main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._resume_incident(incident_id), _main_loop
                    )
                else:
                    logger.warning("Main event loop not available — cannot resume incident %s", incident_id)
            say(f":white_check_mark: Action approved for incident `{incident_id}`. Executing fix...")

        @self._app.action("ignore_action")
        def handle_ignore(ack, body, say):
            ack()
            incident_id = body["actions"][0]["value"]
            logger.info("Human ignored incident %s", incident_id)
            if self.store:
                self.store.update_status(incident_id, "ignored", human_approved=False)
            say(f":no_entry_sign: Incident `{incident_id}` marked as ignored.")

    async def _resume_incident(self, incident_id: str):
        """Re-run the LangGraph agent after human approval."""
        if not self.store:
            return
        incident = self.store.get(incident_id)
        if incident is None:
            return
        from agent.graph import sre_graph
        result = sre_graph.invoke(incident)
        self.store.save(result)
        await self.send_update(result)

    async def send_alert(self, incident: IncidentState) -> Optional[str]:
        """Post incident card to Slack. Returns message timestamp."""
        if not self._enabled:
            self._log_to_console(incident)
            return None

        try:
            blocks = _build_incident_blocks(incident)
            resp = self._client.chat_postMessage(
                channel=config.slack_alert_channel,
                blocks=blocks,
                text=f"Incident {incident['incident_id']}: {incident['metric']['name']} alert",
            )
            return resp["ts"]
        except Exception as e:
            logger.error("Slack send_alert failed: %s", e)
            return None

    async def send_update(self, incident: IncidentState):
        """Update an existing Slack message with resolution status."""
        if not self._enabled or not incident.get("slack_message_ts"):
            return
        try:
            status_text = f":white_check_mark: Resolved" if incident["status"] == "resolved" else f"Status: {incident['status']}"
            self._client.chat_update(
                channel=config.slack_alert_channel,
                ts=incident["slack_message_ts"],
                text=f"Incident {incident['incident_id']} — {status_text}",
                blocks=_build_incident_blocks(incident),
            )
        except Exception as e:
            logger.error("Slack send_update failed: %s", e)

    def start_socket_mode(self):
        if not self._enabled or not config.slack_app_token:
            logger.info("Slack socket mode not started (token missing or disabled).")
            return
        # Capture the main event loop so Slack callbacks can schedule async work
        global _main_loop
        try:
            _main_loop = asyncio.get_running_loop()
        except RuntimeError:
            _main_loop = asyncio.get_event_loop()

        handler = self._SocketModeHandler(self._app, config.slack_app_token)
        thread = threading.Thread(target=handler.start, daemon=True)
        thread.start()
        logger.info("Slack socket mode started.")

    def _log_to_console(self, incident: IncidentState):
        """Fallback when Slack is not configured."""
        metric = incident["metric"]
        print("\n" + "=" * 60)
        print(f"  OPENSRE ALERT [{incident['severity'].upper()}] — {incident['incident_id']}")
        print("=" * 60)
        print(f"  Metric   : {metric['name']} = {metric['value']} {metric['unit']}")
        print(f"  Host     : {metric['host']}")
        print(f"  Cause    : {incident.get('root_cause', 'Analyzing...')}")
        print(f"  Action   : {incident.get('recommended_action', 'Pending...')}")
        print("=" * 60 + "\n")
