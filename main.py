"""
OpenSRE — Autonomous DevOps Agent
Entry point: starts the monitor loop and all notification channels
(Slack, Telegram, WhatsApp, Discord + console fallback).
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add project root to path so imports work regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

# Make console output UTF-8 safe (banner/emojis crash a cp1252 Windows console).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
            fingerprint,
            expires_at - now,
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
    # Severity uses BaseMonitor's ratio formula (static — no instance needed)
    severity = BaseMonitor.severity(metric["value"], metric["threshold"])

    incident = new_incident(metric, severity)
    store.save(incident)
    logger.info(
        "Incident %s created — %s = %.1f %s (severity: %s)",
        incident["incident_id"],
        metric["name"],
        metric["value"],
        metric["unit"],
        severity,
    )

    # Run LangGraph: ANALYZE → DECIDE (→ EXECUTE or AWAIT_HUMAN)
    result = sre_graph.invoke(incident)
    store.save(result)

    # Record incident metric
    try:
        from agent.metrics import INCIDENTS_TOTAL

        INCIDENTS_TOTAL.labels(
            source=metric["source"], severity=severity, status=result["status"]
        ).inc()
    except Exception as e:
        logger.error("Failed to record incident metric: %s", e)

    # Broadcast to all enabled channels (Slack + Telegram + WhatsApp + console)
    slack_ts = await dispatcher.send_alert(result)
    if slack_ts:
        store.update_status(
            result["incident_id"], result["status"], slack_message_ts=slack_ts
        )

    # Auto-resolved low-severity incidents get an immediate resolution notification
    if result["status"] == "resolved":
        await dispatcher.send_update(result)
        _clear_cooldown(metric)  # allow fresh alert if same issue recurs later
        logger.info(
            "Incident %s auto-resolved: %s",
            result["incident_id"],
            result.get("action_taken"),
        )


async def monitor_loop(
    monitors: list[BaseMonitor],
    store: IncidentStore,
    dispatcher: NotificationDispatcher,
    stop_event: asyncio.Event,
    once: bool = False,
):
    """Poll monitors and process alerts until ``stop_event`` is set (or once)."""
    logger.info(
        "OpenSRE monitor loop started. Poll interval: %ds", config.poll_interval_seconds
    )
    logger.info("Simulation mode: %s", config.simulation_mode)
    logger.info(
        "LLM provider: %s (model: %s)", config.llm_provider, config.active_model
    )
    logger.info("Alert cooldown: %ds per fingerprint", config.alert_cooldown_seconds)

    while not stop_event.is_set():
        for monitor in monitors:
            try:
                metrics = monitor.poll()
                for metric in metrics:
                    if _is_duplicate(metric):
                        continue  # Suppress duplicate alert — same issue still ongoing
                    await process_metric(metric, store, dispatcher)
            except Exception as e:
                logger.error("Monitor %s error: %s", monitor.name, e, exc_info=True)

        # Refresh the active-incidents gauge from the store after each cycle.
        try:
            from agent.metrics import refresh_active_incidents

            refresh_active_incidents(store)
        except Exception as e:
            logger.debug("Failed to refresh active-incidents gauge: %s", e)

        if once:
            break

        # Sleep until the next poll, but wake immediately on shutdown.
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=config.poll_interval_seconds
            )
        except asyncio.TimeoutError:
            pass

    logger.info("OpenSRE monitor loop stopped.")


BANNER = r"""
 ██████╗ ██████╗ ███████╗███╗   ██╗███████╗██████╗ ███████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔══██╗██╔════╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████╗██████╔╝█████╗
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║╚════██║██╔══██╗██╔══╝
╚██████╔╝██║     ███████╗██║ ╚████║███████║██║  ██║███████╗
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝
 Autonomous DevOps Agent — Slack · Telegram · WhatsApp · Discord
"""


# ── Entry point ──────────────────────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opensre",
        description="OpenSRE — autonomous AI Site Reliability Engineer.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit (useful for cron / CI).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Single cycle in simulation mode, console-only — no listeners started.",
    )
    parser.add_argument(
        "--provider",
        metavar="NAME",
        help="Override LLM_PROVIDER for this run (anthropic | openai | google).",
    )
    parser.add_argument(
        "--list-incidents",
        nargs="?",
        type=int,
        const=20,
        metavar="N",
        help="Print the N most recent incidents from the store and exit (default 20).",
    )
    parser.add_argument(
        "--version", action="store_true", help="Print the OpenSRE version and exit."
    )
    return parser


def _print_recent_incidents(store: IncidentStore, limit: int) -> None:
    incidents = store.list_recent(limit=limit)
    if not incidents:
        print("No incidents recorded yet.")
        return
    print(f"\n{'ID':<10} {'SEVERITY':<9} {'STATUS':<18} {'METRIC':<16} HOST")
    print("-" * 80)
    for inc in incidents:
        m = inc["metric"]
        print(
            f"{inc['incident_id']:<10} {inc['severity']:<9} {inc['status']:<18} "
            f"{m['name']:<16} {m['host']}"
        )
    print()


async def _amain(monitors, store, dispatcher, once: bool) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, AttributeError, ValueError):
            # Windows / non-main-thread: rely on KeyboardInterrupt instead.
            pass
    await monitor_loop(monitors, store, dispatcher, stop_event, once=once)


def main():
    args = _build_arg_parser().parse_args()

    if args.version:
        print("OpenSRE 1.3.0")
        return

    # Provider override (applies before config is read by the LLM layer).
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
        config.llm_provider = args.provider
        try:
            from llm import reset_cache

            reset_cache()
        except Exception:
            pass

    # --list-incidents only reads the DB; no LLM/config validation needed.
    if args.list_incidents is not None:
        _print_recent_incidents(IncidentStore(config.db_path), args.list_incidents)
        return

    dry_run = args.dry_run
    once = args.once or dry_run
    if dry_run:
        config.simulation_mode = True
        os.environ["SIMULATION_MODE"] = "true"
        logger.info("Dry-run: forcing simulation mode, single cycle, no listeners.")

    try:
        config.validate()
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Copy .env.example to .env and fill in your values.\n")
        sys.exit(1)

    store = IncidentStore(config.db_path)

    # Metrics + health server (serves /metrics and /healthz on one port).
    try:
        from observability import start_metrics_server

        start_metrics_server(store=store, port=8000)
    except Exception as e:
        logger.error("Failed to start metrics/health server: %s", e)

    dispatcher = NotificationDispatcher(store=store)
    if not dry_run:
        # Start Slack socket mode + Telegram polling (interactive approvals).
        dispatcher.start_listeners()

    monitors = [
        CpuMonitor(),
        DatabaseMonitor(),
        KubernetesMonitor(),
    ]

    print(BANNER)

    try:
        asyncio.run(_amain(monitors, store, dispatcher, once))
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down.")


if __name__ == "__main__":
    main()
