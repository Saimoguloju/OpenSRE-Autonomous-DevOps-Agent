from prometheus_client import Counter, Gauge, Histogram

INCIDENTS_TOTAL = Counter(
    "opensre_incidents_total",
    "Total count of incidents detected by OpenSRE.",
    ["source", "severity", "status"],
)

# Currently-open incidents (not yet resolved or ignored), broken down by severity.
# Recomputed from the store at the end of each poll cycle.
ACTIVE_INCIDENTS = Gauge(
    "opensre_active_incidents",
    "Number of incidents currently open (status not resolved/ignored).",
    ["severity"],
)

CLAUDE_LATENCY = Histogram(
    "opensre_claude_latency_seconds",
    "Time spent in seconds calling the LLM provider for root cause analysis.",
)

ACTION_DURATION = Histogram(
    "opensre_action_duration_seconds",
    "Time spent in seconds executing remediation actions.",
)

# Mean-time-to-resolve: wall-clock seconds from incident creation to resolution.
INCIDENT_RESOLUTION_SECONDS = Histogram(
    "opensre_incident_resolution_seconds",
    "Seconds from incident creation to resolution (MTTR).",
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600),
)

# Mean-time-to-approve: seconds from incident creation to a human decision.
APPROVAL_LATENCY_SECONDS = Histogram(
    "opensre_approval_latency_seconds",
    "Seconds from incident creation to a human approve/ignore decision.",
    buckets=(5, 15, 30, 60, 120, 300, 600, 1800, 3600, 7200),
)


def _seconds_since(created_at: str) -> float | None:
    """Return seconds elapsed since an ISO-8601 ``created_at`` timestamp."""
    from datetime import datetime, UTC

    try:
        created = datetime.fromisoformat(created_at)
        return (datetime.now(UTC) - created).total_seconds()
    except (ValueError, TypeError):
        return None


def observe_resolution(created_at: str) -> None:
    """Record MTTR for a resolved incident (best-effort)."""
    seconds = _seconds_since(created_at)
    if seconds is not None and seconds >= 0:
        INCIDENT_RESOLUTION_SECONDS.observe(seconds)


def observe_approval(created_at: str) -> None:
    """Record approval latency when a human makes a decision (best-effort)."""
    seconds = _seconds_since(created_at)
    if seconds is not None and seconds >= 0:
        APPROVAL_LATENCY_SECONDS.observe(seconds)


def refresh_active_incidents(store) -> None:
    """Set the active-incidents gauge from the current store contents."""
    try:
        counts = store.active_count_by_severity()
    except Exception:  # pragma: no cover - defensive
        return
    # Reset known severities to 0 so resolved ones drop back down.
    for severity in ("low", "medium", "high", "critical"):
        ACTIVE_INCIDENTS.labels(severity=severity).set(counts.get(severity, 0))
