import socket
from datetime import datetime, UTC
from typing import List

import psutil

from agent.state import Metric
from config import config
from monitors.base import BaseMonitor


class CpuMonitor(BaseMonitor):
    name = "cpu"

    def poll(self) -> List[Metric]:
        alerts: List[Metric] = []
        host = socket.gethostname()
        now = datetime.now(UTC).isoformat()

        cpu_pct = psutil.cpu_percent(interval=1)
        if cpu_pct >= config.cpu_threshold_pct:
            alerts.append(Metric(
                source="cpu",
                name="cpu_usage",
                value=cpu_pct,
                threshold=config.cpu_threshold_pct,
                unit="percent",
                host=host,
                timestamp=now,
            ))

        mem = psutil.virtual_memory()
        mem_pct = mem.percent
        if mem_pct >= config.memory_threshold_pct:
            alerts.append(Metric(
                source="memory",
                name="memory_usage",
                value=mem_pct,
                threshold=config.memory_threshold_pct,
                unit="percent",
                host=host,
                timestamp=now,
            ))

        return alerts
