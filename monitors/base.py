from abc import ABC, abstractmethod
from typing import List, Optional
from agent.state import Metric


class BaseMonitor(ABC):
    name: str = "base"

    @abstractmethod
    def poll(self) -> List[Metric]:
        """Poll for metrics. Returns list of Metric dicts that breach thresholds."""
        ...

    @staticmethod
    def severity(value: float, threshold: float) -> str:
        """Classify a breach by how far the value exceeds its threshold."""
        if threshold <= 0:
            # Avoid division by zero; any positive value is at least critical.
            return "critical" if value > 0 else "low"
        ratio = value / threshold
        if ratio >= 1.5:
            return "critical"
        if ratio >= 1.25:
            return "high"
        if ratio >= 1.0:
            return "medium"
        return "low"
