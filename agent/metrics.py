from prometheus_client import Counter, Histogram

INCIDENTS_TOTAL = Counter(
    "opensre_incidents_total",
    "Total count of incidents detected by OpenSRE.",
    ["source", "severity", "status"],
)

CLAUDE_LATENCY = Histogram(
    "opensre_claude_latency_seconds",
    "Time spent in seconds calling Claude AI for incident root cause analysis.",
)

ACTION_DURATION = Histogram(
    "opensre_action_duration_seconds",
    "Time spent in seconds executing remediation actions.",
)
