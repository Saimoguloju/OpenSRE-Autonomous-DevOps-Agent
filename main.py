"""
OpenSRE — Autonomous DevOps Agent
Entry point: starts the monitor loop and all notification channels
(Slack, Telegram, WhatsApp + console fallback).
"""
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path so imports work regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

# Load .env before anything else reads config
from dotenv import load_dotenv
load_dotenv()

from config import config
from monitors.cpu import CpuMonitor
from monitors.database import DatabaseMonitor
from monitors.kubernetes import KubernetesMonitor
from monitors.base import BaseMonitor
from agent.state import new_incident
from agent.graph import sre_graph
from storage.incidents import IncidentStore
from notifications.dispatcher import NotificationDispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("opensre")


# ── Alert deduplication ──────────────────────────────────────────────────────
# Tracks the expiry timestamp for each active alert fingerprint.
# Fingerprint = "{metric_source}:{metric_name}:{host}"
_alert_cooldown: dict[str, float] = {}


def _make_fingerprint(metric: dict) -> str:
    """Create a unique key for an alert to detect duplicates."""
    return f"{metric['source']}:{metric['name']}:{metric['host']}"


def _is_duplicate(metric: dict) -> bool:
    """
    Return True if an identical alert fired recently (within cooldown window).
    Updates the cooldown timestamp when a new alert is allowed through.
    """
    fingerprint = _make_fingerprint(metric)
    now = time.monotonic()
    expires_at = _alert_cooldown.get(fingerprint, 0)

    if now < expires_at:
        logger.debug(
            "Duplicate alert suppressed: %s (cooldown %.0fs remaining)",
            fingerprint, expires_at - now,
        )
        return True

    # Allow this alert — start a new cooldown window
    _alert_cooldown[fingerprint] = now + config.alert_cooldown_seconds
    return False


def _clear_cooldown(metric: dict):
    """Remove a fingerprint from the cooldown store when an incident resolves."""
    fingerprint = _make_fingerprint(metric)
    _alert_cooldown.pop(fingerprint, None)
    logger.debug("Cooldown cleared for: %s", fingerprint)


# ── Core pipeline ────────────────────────────────────────────────────────────

async def process_metric(
    metric: dict,
    store: IncidentStore,
    dispatcher: NotificationDispatcher,
):
    """Run one metric through the full LangGraph pipeline and notify all channels."""
    # Severity uses BaseMonitor's ratio formula
    monitor = BaseMonitor.__new__(BaseMonitor)
    severity = monitor.severity(metric["value"], metric["threshold"])

    incident = new_incident(metric, severity)
    store.save(incident)
    logger.info(
        "Incident %s created — %s = %.1f %s (severity: %s)",
        incident["incident_id"], metric["name"], metric["value"], metric["unit"], severity,
    )

    # Run LangGraph: ANALYZE → DECIDE (→ EXECUTE or AWAIT_HUMAN)
    result = sre_graph.invoke(incident)
    store.save(result)

    # Record incident metric
    try:
        from agent.metrics import INCIDENTS_TOTAL
        INCIDENTS_TOTAL.labels(
            source=metric["source"],
            severity=severity,
            status=result["status"]
        ).inc()
    except Exception as e:
        logger.error("Failed to record incident metric: %s", e)

    # Broadcast to all enabled channels (Slack + Telegram + WhatsApp + console)
    slack_ts = await dispatcher.send_alert(result)
    if slack_ts:
        store.update_status(result["incident_id"], result["status"], slack_message_ts=slack_ts)

    # Auto-resolved low-severity incidents get an immediate resolution notification
    if result["status"] == "resolved":
        await dispatcher.send_update(result)
        _clear_cooldown(metric)  # allow fresh alert if same issue recurs later
        logger.info(
            "Incident %s auto-resolved: %s",
            result["incident_id"], result.get("action_taken"),
        )


async def monitor_loop(
    monitors: list[BaseMonitor],
    store: IncidentStore,
    dispatcher: NotificationDispatcher,
):
    """Continuously poll monitors and process any triggered alerts."""
    logger.info("OpenSRE monitor loop started. Poll interval: %ds", config.poll_interval_seconds)
    logger.info("Simulation mode: %s", config.simulation_mode)
    logger.info("Model: %s", config.model)
    logger.info("Alert cooldown: %ds per fingerprint", config.alert_cooldown_seconds)

    while True:
        for monitor in monitors:
            try:
                metrics = monitor.poll()
                for metric in metrics:
                    if _is_duplicate(metric):
                        continue  # Suppress duplicate alert — same issue still ongoing
                    await process_metric(metric, store, dispatcher)
            except Exception as e:
                logger.error("Monitor %s error: %s", monitor.name, e, exc_info=True)

        await asyncio.sleep(config.poll_interval_seconds)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    try:
        config.validate()
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Copy .env.example to .env and fill in your values.\n")
        sys.exit(1)

    # Start Prometheus metrics server
    try:
        from prometheus_client import start_http_server
        start_http_server(8000)
        logger.info("Prometheus metrics server started on port 8000.")
    except Exception as e:
        logger.error("Failed to start Prometheus metrics server: %s", e)

    store = IncidentStore(config.db_path)
    dispatcher = NotificationDispatcher(store=store)
    dispatcher.start_socket_mode()  # Starts Slack socket mode in a background thread

    monitors = [
        CpuMonitor(),
        DatabaseMonitor(),
        KubernetesMonitor(),
    ]

    print("""
 ██████╗ ██████╗ ███████╗███╗   ██╗███████╗██████╗ ███████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔══██╗██╔════╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████╗██████╔╝█████╗
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║╚════██║██╔══██╗██╔══╝
╚██████╔╝██║     ███████╗██║ ╚████║███████║██║  ██║███████╗
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝
 Autonomous DevOps Agent — Slack · Telegram · WhatsApp
""")

    asyncio.run(monitor_loop(monitors, store, dispatcher))


if __name__ == "__main__":
    main()
