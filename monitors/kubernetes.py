import random
from datetime import datetime, UTC
from typing import List

from agent.state import Metric
from config import config
from monitors.base import BaseMonitor

SIMULATED_PODS = [
    {
        "name": "api-deployment-7d9f8b-xk2p",
        "namespace": "production",
        "restarts": 8,
        "status": "CrashLoopBackOff",
    },
    {
        "name": "worker-deployment-5c6d7e-mn3q",
        "namespace": "production",
        "restarts": 3,
        "status": "Running",
    },
    {
        "name": "redis-statefulset-0",
        "namespace": "production",
        "restarts": 0,
        "status": "Running",
    },
]


class KubernetesMonitor(BaseMonitor):
    name = "kubernetes"

    def __init__(self):
        self._call_count = 0  # instance variable — not shared across instances

    def poll(self) -> List[Metric]:
        alerts: List[Metric] = []
        now = datetime.now(UTC).isoformat()
        self._call_count += 1

        if config.simulation_mode:
            # Surface a crashing pod every ~8 polls
            if self._call_count % 8 == 0:
                pod = SIMULATED_PODS[0]
                if pod["status"] == "CrashLoopBackOff":
                    alerts.append(
                        Metric(
                            source="kubernetes",
                            name="pod_crash_loop",
                            value=float(pod["restarts"]),
                            threshold=5.0,
                            unit="count",
                            host=f"{pod['namespace']}/{pod['name']}",
                            timestamp=now,
                        )
                    )
        else:
            # Production: call kubectl or kubernetes Python client here
            pass

        return alerts
