"""
OpenSRE — Autonomous DevOps Agent
Entry point: starts the monitor loop and Slack bot.
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path so imports work regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from monitors.cpu import CpuMonitor
from monitors.database import DatabaseMonitor
from monitors.kubernetes import KubernetesMonitor
from monitors.base import BaseMonitor
from agent.state import new_incident
from agent.graph import sre_graph
from storage.incidents import IncidentStore
from notifications.slack_bot import SlackNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("opensre")


async def process_metric(metric, store: IncidentStore, notifier: SlackNotifier):
    """Run one metric through the full LangGraph pipeline."""
    from monitors.base import BaseMonitor
    monitor = BaseMonitor.__new__(BaseMonitor)
    severity = monitor.severity(metric["value"], metric["threshold"])

    incident = new_incident(metric, severity)
    store.save(incident)
    logger.info(
        "Incident %s created — %s = %.1f %s (severity: %s)",
        incident["incident_id"], metric["name"], metric["value"], metric["unit"], severity,
    )

    # Run LangGraph: DETECT → ANALYZE → DECIDE
    result = sre_graph.invoke(incident)
    store.save(result)

    # Notify via Slack (or console fallback)
    ts = await notifier.send_alert(result)
    if ts:
        store.update_status(result["incident_id"], result["status"], slack_message_ts=ts)

    # If auto-approved (low severity in sim mode), send resolution update
    if result["status"] == "resolved":
        await notifier.send_update(result)
        logger.info("Incident %s auto-resolved: %s", result["incident_id"], result.get("action_taken"))


async def monitor_loop(monitors: list[BaseMonitor], store: IncidentStore, notifier: SlackNotifier):
    """Continuously poll monitors and process any triggered alerts."""
    logger.info("OpenSRE monitor loop started. Poll interval: %ds", config.poll_interval_seconds)
    logger.info("Simulation mode: %s", config.simulation_mode)
    logger.info("Model: %s", config.model)

    while True:
        for monitor in monitors:
            try:
                metrics = monitor.poll()
                for metric in metrics:
                    await process_metric(metric, store, notifier)
            except Exception as e:
                logger.error("Monitor %s error: %s", monitor.name, e)

        await asyncio.sleep(config.poll_interval_seconds)


def main():
    try:
        config.validate()
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Copy .env.example to .env and fill in your values.\n")
        sys.exit(1)

    store = IncidentStore(config.db_path)
    notifier = SlackNotifier(store=store)
    notifier.start_socket_mode()

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
 Autonomous DevOps Agent — github.com/your-username/opensre
""")

    asyncio.run(monitor_loop(monitors, store, notifier))


if __name__ == "__main__":
    main()
