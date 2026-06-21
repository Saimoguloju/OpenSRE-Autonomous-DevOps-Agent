import logging
from datetime import datetime, UTC

from agent.state import IncidentState
from config import config
from llm import get_provider

logger = logging.getLogger(__name__)


def _complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Send a prompt to the active LLM provider and return its text response."""
    return get_provider().complete(system=system, user=user, max_tokens=max_tokens)


def _is_mock() -> bool:
    """True when the active provider is configured with the mock_key sentinel."""
    return get_provider().is_mock


def analyze_root_cause(state: IncidentState) -> IncidentState:
    """Call Claude to analyze the incident and suggest a fix."""
    metric = state["metric"]

    # Local SRE RAG: Fetch similar past resolved incidents to feed as context
    past_context = ""
    try:
        from storage.incidents import IncidentStore

        store = IncidentStore(config.db_path)
        past_incidents = store.get_similar_resolved(
            metric["source"], metric["name"], limit=3
        )
        if past_incidents:
            past_context = (
                "\n\n=== PAST SIMILAR RESOLVED INCIDENTS (HISTORICAL CONTEXT) ===\n"
            )
            for idx, past in enumerate(past_incidents, 1):
                past_context += f"[{idx}] Incident ID: {past['incident_id']}\n"
                past_context += f"    Root Cause: {past.get('root_cause', 'N/A')}\n"
                past_context += f"    Remediation Action Executed: {past.get('action_taken', 'N/A')}\n"
            past_context += (
                "===========================================================\n"
            )
    except Exception as e:
        logger.warning("Failed to fetch past resolved incidents for RAG: %s", e)

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
Severity: {state['severity']}{past_context}

Analyze this incident and provide your root cause assessment and recommended action. If past similar incidents are listed, use them as guidance to maintain remediation consistency."""

    try:
        from agent.metrics import CLAUDE_LATENCY

        with CLAUDE_LATENCY.time():
            analysis = _complete(system_prompt, user_message, max_tokens=512)

        # Robust regex-based parsing to handle bold tags and spacing variations from the model
        import re

        rc_match = re.search(r"ROOT\s*CAUSE:\s*(.*)", analysis, re.IGNORECASE)
        ra_match = re.search(r"RECOMMENDED\s*ACTION:\s*(.*)", analysis, re.IGNORECASE)

        root_cause = rc_match.group(1).strip() if rc_match else ""
        recommended_action = ra_match.group(1).strip() if ra_match else ""

        # Remove markdown decorations (bold markup/backticks)
        if root_cause:
            root_cause = root_cause.replace("**", "").replace("`", "").strip()
        if recommended_action:
            recommended_action = (
                recommended_action.replace("**", "").replace("`", "").strip()
            )

        state["root_cause"] = root_cause or analysis[:200]
        state["recommended_action"] = (
            recommended_action or "Manual investigation required."
        )
    except Exception as e:
        logger.error("Root cause analysis failed: %s", e)
        state["root_cause"] = "Analysis unavailable — LLM provider error."
        state["recommended_action"] = "Manual investigation required."

    state["status"] = "awaiting_approval"
    state["updated_at"] = datetime.now(UTC).isoformat()
    return state


def decide_action(state: IncidentState) -> IncidentState:
    """
    Decide whether the agent may act autonomously or must escalate to a human.

    Default posture is SAFE: unless ``AUTO_REMEDIATE`` is explicitly enabled,
    every incident requires human approval. When auto-remediation is enabled
    (simulation mode only), the agent may act on its own *only* when the
    incident is non-critical AND the self-critique confidence score clears the
    configured threshold — tying the decision to the ``critique_remediation``
    node's audit instead of severity alone.
    """
    severity = state["severity"]
    confidence = state.get("confidence_score")
    high_confidence = (
        confidence is not None and confidence >= config.auto_approve_min_confidence
    )

    auto_ok = (
        config.simulation_mode
        and config.auto_remediate
        and severity != "critical"
        and high_confidence
    )

    if auto_ok:
        state["human_approved"] = True
        state["status"] = "acting"
        logger.info(
            "Incident %s auto-approved (severity=%s, confidence=%s) — acting autonomously.",
            state["incident_id"],
            severity,
            confidence,
        )
    else:
        state["status"] = "awaiting_approval"

    state["updated_at"] = datetime.now(UTC).isoformat()
    return state


def execute_action(state: IncidentState) -> IncidentState:
    """Execute the remediation action (tools called here)."""
    metric = state["metric"]
    action_log = []

    # 1. Run Safety Guardrails before execution
    from agent.guardrails import RemediationGuardrail

    is_safe, reason = RemediationGuardrail.validate_command(
        state.get("recommended_action", "")
    )
    if not is_safe:
        logger.warning(
            "Incident %s remediation blocked by guardrails: %s",
            state["incident_id"],
            reason,
        )
        state["action_taken"] = f"BLOCKED BY SAFETY GUARDRAIL: {reason}"
        state["status"] = "ignored"
        state["updated_at"] = datetime.now(UTC).isoformat()
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
    state["updated_at"] = datetime.now(UTC).isoformat()

    # 3. Generate SRE Post-Mortem Report
    _generate_post_mortem(state)

    return state


def mark_ignored(state: IncidentState) -> IncidentState:
    state["status"] = "ignored"
    state["action_taken"] = "Human chose to ignore this incident."
    state["updated_at"] = datetime.now(UTC).isoformat()
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
        # Try the LLM provider first
        post_mortem_content = _complete(system_prompt, user_message, max_tokens=1024)
    except Exception as e:
        logger.warning(
            "Could not generate SRE post-mortem via the LLM provider: %s. Falling back to template.",
            e,
        )

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


def critique_remediation(state: IncidentState) -> IncidentState:
    """
    Self-reflection node: audits Claude's recommended action using a separate auditor prompt.
    Scores confidence and writes critique notes.
    """
    import re

    recommended_action = state.get("recommended_action", "")
    root_cause = state.get("root_cause", "")
    metric = state["metric"]

    if not recommended_action or recommended_action == "Manual investigation required.":
        state["confidence_score"] = 0
        state["critique"] = "No recommended action was generated."
        state["status"] = "awaiting_approval"
        state["updated_at"] = datetime.now(UTC).isoformat()
        return state

    # Mock evaluation for simulation / unit tests (any provider with a mock key)
    if _is_mock():
        from agent.guardrails import RemediationGuardrail

        is_safe, reason = RemediationGuardrail.validate_command(recommended_action)
        if not is_safe:
            state["confidence_score"] = 15
            state["critique"] = f"[MOCK AUDIT] Command rejected by guardrails: {reason}"
        else:
            state["confidence_score"] = 95
            state["critique"] = (
                "[MOCK AUDIT] Command checked against guardrails and approved."
            )

        # Routing safety rule: low confidence forces manual approval
        if state["confidence_score"] < 80:
            state["status"] = "awaiting_approval"

        state["updated_at"] = datetime.now(UTC).isoformat()
        return state

    system_prompt = """You are OpenSRE Auditor, an expert SRE Auditor.
Audit the proposed remediation action and root cause.
Assign a Confidence Score (integer between 0 and 100) reflecting how safe, relevant, and correct the action is.
Write a brief critique.
Format your output exactly as:

CONFIDENCE SCORE: <score>
CRITIQUE: <one sentence>"""

    user_message = f"""Incident Host: {metric['host']}
Metric: {metric['name']}
Severity: {state['severity']}
Proposed Root Cause: {root_cause}
Proposed Command/Remediation: {recommended_action}"""

    try:
        audit_output = _complete(system_prompt, user_message, max_tokens=256)

        score_match = re.search(
            r"CONFIDENCE\s*SCORE:\s*(\d+)", audit_output, re.IGNORECASE
        )
        crit_match = re.search(r"CRITIQUE:\s*(.*)", audit_output, re.IGNORECASE)

        confidence_score = int(score_match.group(1)) if score_match else 75
        critique = crit_match.group(1).strip() if crit_match else audit_output[:200]

        state["confidence_score"] = confidence_score
        state["critique"] = critique

        # Safety Fallback: low confidence forces manual human verification
        if confidence_score < 80:
            logger.warning(
                "Audit confidence score for incident %s is low (%d): %s",
                state["incident_id"],
                confidence_score,
                critique,
            )
            state["status"] = "awaiting_approval"

    except Exception as e:
        logger.error("Self-critique auditing failed: %s", e)
        state["confidence_score"] = 50
        state["critique"] = "Auditing failed — LLM provider error."
        state["status"] = "awaiting_approval"

    state["updated_at"] = datetime.now(UTC).isoformat()
    return state
