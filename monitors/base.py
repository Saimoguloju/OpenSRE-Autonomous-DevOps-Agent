from abc import ABC, abstractmethod
from typing import List, Optional
from agent.state import Metric


class BaseMonitor(ABC):
    name: str = "base"

    @abstractmethod
    def poll(self) -> List[Metric]:
        """Poll for metrics. Returns list of Metric dicts that breach thresholds."""
        ...

    def severity(self, value: float, threshold: float) -> str:
        ratio = value / threshold
        if ratio >= 1.5:
            return "critical"
        if ratio >= 1.25:
            return "high"
        if ratio >= 1.0:
            return "medium"
        return "low"
