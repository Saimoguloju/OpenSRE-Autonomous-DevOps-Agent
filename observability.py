"""Lightweight HTTP server exposing Prometheus metrics and a health check.

Serves two endpoints on a single port (default 8000):
  • ``/metrics``  — Prometheus exposition (scraped by prometheus.yml)
  • ``/healthz``  — JSON liveness/readiness probe (k8s/docker friendly)
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import config

logger = logging.getLogger(__name__)


def _make_handler(store):
    class _Handler(BaseHTTPRequestHandler):
        # Silence the default noisy request logging.
        def log_message(self, *args):  # noqa: D401
            return

        def _send(self, code: int, body: bytes, content_type: str):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - required name
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path == "/metrics":
                self._send(200, generate_latest(), CONTENT_TYPE_LATEST)
            elif path in ("/healthz", "/health", "/"):
                self._send(
                    200,
                    json.dumps(health_payload(store)).encode("utf-8"),
                    "application/json",
                )
            else:
                self._send(404, b'{"error": "not found"}', "application/json")

    return _Handler


def health_payload(store) -> dict:
    """Build the JSON body for /healthz."""
    active = 0
    if store is not None:
        try:
            active = sum(store.active_count_by_severity().values())
        except Exception:  # pragma: no cover - defensive
            active = -1
    return {
        "status": "ok",
        "simulation_mode": config.simulation_mode,
        "llm_provider": config.llm_provider,
        "model": config.active_model,
        "active_incidents": active,
    }


def start_metrics_server(store=None, port: int = 8000) -> ThreadingHTTPServer:
    """Start the metrics + health server in a daemon thread. Returns the server."""
    server = ThreadingHTTPServer(("", port), _make_handler(store))
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="metrics")
    thread.start()
    logger.info(
        "Metrics + health server started on port %d (/metrics, /healthz).", port
    )
    return server
