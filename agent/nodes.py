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
        from agent.metrics import CLAUDE_LATENCY
        with CLAUDE_LATENCY.time():
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

    # 1. Run Safety Guardrails before execution
    from agent.guardrails import RemediationGuardrail
    is_safe, reason = RemediationGuardrail.validate_command(state.get("recommended_action", ""))
    if not is_safe:
        logger.warning("Incident %s remediation blocked by guardrails: %s", state["incident_id"], reason)
        state["action_taken"] = f"BLOCKED BY SAFETY GUARDRAIL: {reason}"
        state["status"] = "ignored"
        state["updated_at"] = datetime.utcnow().isoformat()
        return state

    # 2. Execute if safe
    from agent.metrics import ACTION_DURATION
    with ACTION_DURATION.time():
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

    # 3. Generate SRE Post-Mortem Report
    _generate_post_mortem(state)

    return state


def mark_ignored(state: IncidentState) -> IncidentState:
    state["status"] = "ignored"
    state["action_taken"] = "Human chose to ignore this incident."
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def _generate_post_mortem(state: IncidentState) -> str:
    """Generate a structured SRE post-mortem report and save it to disk."""
    import os
    from pathlib import Path
    
    metric = state["metric"]
    incident_id = state["incident_id"]
    
    system_prompt = """You are OpenSRE, an expert SRE Post-Mortem Writer.
Your job is to write a detailed, blameless SRE Post-Mortem Report in Markdown format based on the incident state.
The report must include sections:
1. Executive Summary
2. Incident Details & Timeline
3. Root Cause Analysis (5 Whys or similar logical explanation)
4. Remediation Executed
5. Prevention & Action Items (what we should do to avoid this in the future)

Be professional and technical."""

    user_message = f"""Incident ID: {incident_id}
Metric: {metric['name']}
Breach Value: {metric['value']} {metric['unit']} (Threshold: {metric['threshold']})
Host: {metric['host']}
Severity: {state['severity']}
Root Cause Identified: {state.get('root_cause', 'Unknown')}
Action Executed: {state.get('action_taken', 'N/A')}
Status: {state['status']}
Created At: {state['created_at']}
Resolved At: {state['updated_at']}
"""

    post_mortem_content = ""
    try:
        # Try Claude first
        client = _get_client()
        response = client.messages.create(
            model=config.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        post_mortem_content = response.content[0].text
    except Exception as e:
        logger.warning("Could not generate SRE post-mortem using Claude: %s. Falling back to template.", e)
        
        # Markdown template fallback
        post_mortem_content = f"""# SRE Post-Mortem Report (Blameless)
## Incident ID: {incident_id}

### 1. Executive Summary
On {state['created_at']}, an incident of **{state['severity'].upper()}** severity was detected on host `{metric['host']}`. The metric `{metric['name']}` breached its threshold of {metric['threshold']} {metric['unit']} with a value of {metric['value']} {metric['unit']}. The incident was resolved automatically or via engineer approval.

### 2. Timeline
* **{state['created_at']}**: Incident detected by OpenSRE monitor loop.
* **{state['created_at']}** (approx): Root cause analyzed and action recommendations generated.
* **{state['updated_at']}**: Remediation executed / incident closed.

### 3. Root Cause Analysis (RCA)
**Assessment**:
{state.get('root_cause', 'No root cause assessment available.')}

### 4. Remediation Executed
* **Action Recommended**: `{state.get('recommended_action', 'None')}`
* **Action Log**: `{state.get('action_taken', 'No actions logged.')}`
* **Result**: Incident resolved.

### 5. Prevention & Action Items
- [ ] Monitor thresholds adjustments if necessary.
- [ ] Implement permanent infrastructure patch to resolve root cause.
- [ ] Conduct team review of this automated remediation flow.
"""

    try:
        post_mortem_dir = Path("post_mortems")
        post_mortem_dir.mkdir(exist_ok=True)
        file_path = post_mortem_dir / f"incident_{incident_id}.md"
        file_path.write_text(post_mortem_content, encoding="utf-8")
        logger.info("Saved SRE post-mortem to %s", file_path)
        return str(file_path)
    except Exception as e:
        logger.error("Failed to save post-mortem to disk: %s", e)
        return ""
