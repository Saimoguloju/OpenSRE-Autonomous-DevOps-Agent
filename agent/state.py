from typing import TypedDict, Optional, Literal
from datetime import datetime, UTC


class Metric(TypedDict):
    source: str  # "cpu", "memory", "database", "kubernetes"
    name: str  # metric name
    value: float  # current value
    threshold: float  # configured threshold
    unit: str  # "percent", "ms", "count"
    host: str  # hostname or pod name
    timestamp: str  # ISO format


class IncidentState(TypedDict):
    incident_id: str
    metric: Metric
    severity: Literal["low", "medium", "high", "critical"]
    root_cause: Optional[str]  # Claude's analysis
    recommended_action: Optional[str]  # Claude's suggestion
    action_taken: Optional[str]  # what was actually done
    status: Literal[
        "detected", "analyzing", "awaiting_approval", "acting", "resolved", "ignored"
    ]
    slack_message_ts: Optional[str]  # Slack message timestamp for updates
    created_at: str
    updated_at: str
    human_approved: Optional[bool]
    confidence_score: Optional[int]  # AI Self-reflection confidence score
    critique: Optional[str]  # AI Self-reflection critique notes


def new_incident(metric: Metric, severity: str) -> IncidentState:
    import uuid

    now = datetime.now(UTC).isoformat()
    return IncidentState(
        incident_id=str(uuid.uuid4())[:8],
        metric=metric,
        severity=severity,
        root_cause=None,
        recommended_action=None,
        action_taken=None,
        status="detected",
        slack_message_ts=None,
        created_at=now,
        updated_at=now,
        human_approved=None,
        confidence_score=None,
        critique=None,
    )
