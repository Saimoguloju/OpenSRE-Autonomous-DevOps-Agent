import random
import socket
from datetime import datetime, UTC
from typing import List

from agent.state import Metric
from config import config
from monitors.base import BaseMonitor


# Simulated slow queries — in production, replace with real DB polling
SIMULATED_QUERIES = [
    {"query": "SELECT * FROM orders JOIN users ON orders.user_id = users.id WHERE status='pending'", "duration_ms": 2400},
    {"query": "UPDATE inventory SET stock=stock-1 WHERE product_id IN (SELECT product_id FROM cart)", "duration_ms": 890},
    {"query": "SELECT COUNT(*) FROM logs WHERE created_at > NOW() - INTERVAL '1 day'", "duration_ms": 3100},
    {"query": "DELETE FROM sessions WHERE expires_at < NOW()", "duration_ms": 1200},
]


class DatabaseMonitor(BaseMonitor):
    name = "database"

    def __init__(self):
        self._call_count = 0

    def poll(self) -> List[Metric]:
        alerts: List[Metric] = []
        host = socket.gethostname()
        now = datetime.now(UTC).isoformat()
        self._call_count += 1

        if config.simulation_mode:
            # Trigger a simulated slow query every ~5 polls so demo is visible
            if self._call_count % 5 == 0:
                query_info = random.choice(SIMULATED_QUERIES)
                duration_ms = query_info["duration_ms"] + random.randint(-100, 100)
                if duration_ms >= config.slow_query_threshold_ms:
                    alerts.append(Metric(
                        source="database",
                        name="slow_query",
                        value=float(duration_ms),
                        threshold=float(config.slow_query_threshold_ms),
                        unit="ms",
                        host=f"{host}:5432",
                        timestamp=now,
                    ))
        return alerts

    def get_slow_queries(self) -> List[dict]:
        """Return simulated slow query details for the agent to analyze."""
        if config.simulation_mode:
            return [
                {**q, "pid": random.randint(1000, 9999), "state": "active"}
                for q in SIMULATED_QUERIES
                if q["duration_ms"] >= config.slow_query_threshold_ms
            ]
        return []
