import logging
from datetime import datetime

import anthropic

from agent.state import IncidentState
from config import config

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    return _client


def analyze_root_cause(state: IncidentState) -> IncidentState:
    """Call Claude to analyze the incident and suggest a fix."""
    metric = state["metric"]

    system_prompt = """You are OpenSRE, an expert Site Reliability Engineer AI.
Your job is to analyze infrastructure incidents, identify root causes, and recommend specific remediation actions.
Be concise and actionable. Format your response as:

ROOT CAUSE: <one sentence>
RECOMMENDED ACTION: <specific command or step>
RISK LEVEL: <low|medium|high>
ESTIMATED FIX TIME: <duration>"""

    user_message = f"""Incident detected on host: {metric['host']}

Metric: {metric['name']}
Value: {metric['value']} {metric['unit']} (threshold: {metric['threshold']} {metric['unit']})
Source: {metric['source']}
Detected at: {metric['timestamp']}
Severity: {state['severity']}

Analyze this incident and provide your root cause assessment and recommended action."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=config.model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        analysis = response.content[0].text

        root_cause = ""
        recommended_action = ""
        for line in analysis.splitlines():
            if line.startswith("ROOT CAUSE:"):
                root_cause = line.replace("ROOT CAUSE:", "").strip()
            elif line.startswith("RECOMMENDED ACTION:"):
                recommended_action = line.replace("RECOMMENDED ACTION:", "").strip()

        state["root_cause"] = root_cause or analysis[:200]
        state["recommended_action"] = recommended_action or "Manual investigation required."
    except Exception as e:
        logger.error("Claude analysis failed: %s", e)
        state["root_cause"] = "Analysis unavailable — Claude API error."
        state["recommended_action"] = "Manual investigation required."

    state["status"] = "awaiting_approval"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def decide_action(state: IncidentState) -> IncidentState:
    """Determine if we can auto-act or need human approval."""
    # Auto-act only on low-severity incidents in simulation mode
    if state["severity"] == "low" and config.simulation_mode:
        state["human_approved"] = True
        state["status"] = "acting"
    else:
        state["status"] = "awaiting_approval"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def execute_action(state: IncidentState) -> IncidentState:
    """Execute the remediation action (tools called here)."""
    metric = state["metric"]
    action_log = []

    if metric["source"] == "cpu":
        from tools.k8s_tools import scale_deployment
        result = scale_deployment("api-deployment", replicas=3)
        action_log.append(result)

    elif metric["source"] == "database":
        from tools.db_tools import kill_slow_queries
        result = kill_slow_queries()
        action_log.append(result)

    elif metric["source"] == "kubernetes":
        from tools.k8s_tools import restart_pod
        pod_name = metric["host"].split("/")[-1]
        result = restart_pod(pod_name)
        action_log.append(result)

    elif metric["source"] == "memory":
        from tools.k8s_tools import restart_pod
        result = restart_pod("api-deployment")
        action_log.append(result)

    state["action_taken"] = "; ".join(action_log) if action_log else "No action taken."
    state["status"] = "resolved"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def mark_ignored(state: IncidentState) -> IncidentState:
    state["status"] = "ignored"
    state["action_taken"] = "Human chose to ignore this incident."
    state["updated_at"] = datetime.utcnow().isoformat()
    return state
