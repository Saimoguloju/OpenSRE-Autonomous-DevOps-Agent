import os
import shutil

# Environment is configured in tests/conftest.py (simulation mode + mock key).
from config import config
from agent.state import new_incident
from agent.guardrails import RemediationGuardrail
from agent.nodes import decide_action, execute_action
from agent.metrics import INCIDENTS_TOTAL, CLAUDE_LATENCY, ACTION_DURATION

# `temp_db` and `mock_metric` fixtures are provided by tests/conftest.py.

# ── Safety Guardrail Tests ──────────────────────────────────────────────────


def test_guardrail_dangerous_commands():
    # Dangerous commands must be blocked
    bad_commands = [
        "rm -rf /",
        "rm -R /",
        "mkfs.ext4 /dev/sdb1",
        "kubectl delete namespace kube-system",
        "kubectl delete all -n production",
        "DROP DATABASE production;",
        "DROP TABLE users; SELECT * FROM logs;",
        "shred -u private.key",
    ]
    for cmd in bad_commands:
        is_safe, reason = RemediationGuardrail.validate_command(cmd)
        assert not is_safe, f"Expected command to be blocked: {cmd}. Reason: {reason}"


def test_guardrail_safe_commands():
    # Safe commands must be allowed
    safe_commands = [
        "kubectl restart pod api-deployment-7d9f8b-xk2p -n production",
        "kubectl scale deployment web-server --replicas=3 -n default",
        "kubectl logs api-deployment-7d9f8b-xk2p -n staging --tail=50",
        "SELECT * FROM pg_stat_activity WHERE query_start < NOW() - INTERVAL '5 minutes'",
    ]
    for cmd in safe_commands:
        is_safe, reason = RemediationGuardrail.validate_command(cmd)
        assert (
            is_safe
        ), f"Expected command to be allowed: {cmd}. Blocked because: {reason}"


def test_guardrail_forbidden_namespaces():
    # Kubectl commands targeting system namespaces must be blocked
    blocked_namespaces = [
        "kubectl delete pod api-pod -n kube-system",
        "kubectl restart pod security-pod -n security-system",
        "kubectl logs logger-pod --namespace kube-node-lease",
    ]
    for cmd in blocked_namespaces:
        is_safe, reason = RemediationGuardrail.validate_command(cmd)
        assert not is_safe, f"Expected system namespace command to be blocked: {cmd}"


# ── Storage Layer Tests ─────────────────────────────────────────────────────


def test_incident_store_lifecycle(temp_db, mock_metric):
    incident = new_incident(mock_metric, "critical")
    assert incident["status"] == "detected"

    # Save to SQLite
    temp_db.save(incident)

    # Retrieve from SQLite
    retrieved = temp_db.get(incident["incident_id"])
    assert retrieved is not None
    assert retrieved["incident_id"] == incident["incident_id"]
    assert retrieved["severity"] == "critical"
    assert retrieved["metric"]["name"] == "pod_crash_loop"

    # Update status
    temp_db.update_status(incident["incident_id"], "acting", human_approved=True)
    updated = temp_db.get(incident["incident_id"])
    assert updated["status"] == "acting"
    assert updated["human_approved"] is True

    # List recent
    recent = temp_db.list_recent(limit=5)
    assert len(recent) == 1
    assert recent[0]["incident_id"] == incident["incident_id"]


# ── Agent State Nodes Tests ─────────────────────────────────────────────────


def test_decide_action_safe_default(mock_metric, monkeypatch):
    # Default posture: auto-remediation OFF -> everything awaits a human,
    # even a high-confidence, low-severity incident.
    monkeypatch.setattr(config, "auto_remediate", False)
    inc = new_incident(mock_metric, "low")
    inc["confidence_score"] = 99
    res = decide_action(inc)
    assert res["status"] == "awaiting_approval"
    assert res["human_approved"] is None


def test_decide_action_auto_remediate_high_confidence(mock_metric, monkeypatch):
    # With auto-remediation enabled in simulation mode, a non-critical,
    # high-confidence incident is acted on autonomously.
    monkeypatch.setattr(config, "auto_remediate", True)
    monkeypatch.setattr(config, "simulation_mode", True)
    inc = new_incident(mock_metric, "high")
    inc["confidence_score"] = 92
    res = decide_action(inc)
    assert res["status"] == "acting"
    assert res["human_approved"] is True


def test_decide_action_low_confidence_escalates(mock_metric, monkeypatch):
    # Even with auto-remediation on, a low-confidence analysis must escalate.
    monkeypatch.setattr(config, "auto_remediate", True)
    inc = new_incident(mock_metric, "high")
    inc["confidence_score"] = 40
    res = decide_action(inc)
    assert res["status"] == "awaiting_approval"
    assert res["human_approved"] is None


def test_decide_action_critical_never_auto(mock_metric, monkeypatch):
    # Critical incidents always require a human, regardless of confidence.
    monkeypatch.setattr(config, "auto_remediate", True)
    inc = new_incident(mock_metric, "critical")
    inc["confidence_score"] = 100
    res = decide_action(inc)
    assert res["status"] == "awaiting_approval"


def test_execute_action_with_guardrail_failure(mock_metric):
    incident = new_incident(mock_metric, "high")
    # Set an unsafe recommended action
    incident["recommended_action"] = "rm -rf /var/log"
    incident["status"] = "acting"

    # Should trigger guardrail and block execution
    result = execute_action(incident)
    assert result["status"] == "ignored"
    assert "BLOCKED BY SAFETY GUARDRAIL" in result["action_taken"]


def test_execute_action_successful_simulated(mock_metric):
    incident = new_incident(mock_metric, "low")
    incident["recommended_action"] = "kubectl delete pod api-pod -n production"
    incident["status"] = "acting"

    # Run execute node
    result = execute_action(incident)
    assert result["status"] == "resolved"
    assert "[SIMULATION]" in result["action_taken"]

    # Verify post-mortem report creation
    post_mortem_file = f"post_mortems/incident_{incident['incident_id']}.md"
    assert os.path.exists(post_mortem_file)

    # Clean up post-mortem
    if os.path.exists("post_mortems"):
        shutil.rmtree("post_mortems")


# ── Observability Metrics Tests ─────────────────────────────────────────────


def test_prometheus_metrics_creation():
    assert INCIDENTS_TOTAL is not None
    assert CLAUDE_LATENCY is not None
    assert ACTION_DURATION is not None

    # Increment metric to verify it works
    INCIDENTS_TOTAL.labels(source="cpu", severity="low", status="resolved").inc()
    assert (
        INCIDENTS_TOTAL.labels(
            source="cpu", severity="low", status="resolved"
        )._value.get()
        == 1.0
    )


# ── Local RAG Tests ─────────────────────────────────────────────────────────


def test_similar_resolved_query(temp_db, mock_metric):
    # Populate the DB with resolved incidents
    inc1 = new_incident(mock_metric, "critical")
    inc1["status"] = "resolved"
    inc1["root_cause"] = "Heavy database lock on master database"
    inc1["action_taken"] = "Killed query"
    temp_db.save(inc1)

    inc2 = new_incident(mock_metric, "low")
    inc2["status"] = "resolved"
    inc2["root_cause"] = "Kubernetes pods crashing continuously"
    inc2["action_taken"] = "Restarted pod"
    temp_db.save(inc2)

    # Query with semantic tokens matching inc2
    similar = temp_db.get_similar_resolved("kubernetes", "pod_crash_loop", limit=2)
    assert len(similar) >= 1
    # Semantic match order: pods crashing has higher overlap with kubernetes/pod_crash_loop than database lock
    assert "Kubernetes" in similar[0]["root_cause"]


def test_tfidf_ranking_logic(temp_db, mock_metric):
    # Empty DB
    assert temp_db.get_similar_resolved("cpu", "cpu_leak", limit=2) == []

    # Insert distinct metrics
    cpu_metric = mock_metric.copy()
    cpu_metric["source"] = "cpu"
    cpu_metric["name"] = "high_cpu_usage"

    inc_cpu = new_incident(cpu_metric, "medium")
    inc_cpu["status"] = "resolved"
    inc_cpu["root_cause"] = "CPU usage spiked from background thread"
    inc_cpu["action_taken"] = "Restarted process"
    temp_db.save(inc_cpu)

    db_metric = mock_metric.copy()
    db_metric["source"] = "database"
    db_metric["name"] = "slow_queries_detected"

    inc_db = new_incident(db_metric, "high")
    inc_db["status"] = "resolved"
    inc_db["root_cause"] = "Database connection pool saturated with locks"
    inc_db["action_taken"] = "Killed connections"
    temp_db.save(inc_db)

    # Query for database
    res = temp_db.get_similar_resolved("database", "slow_queries", limit=1)
    assert len(res) == 1
    assert res[0]["metric"]["source"] == "database"
    assert "Database" in res[0]["root_cause"]


# ── Self-Reflection & Critique Tests ────────────────────────────────────────


def test_critique_remediation_approved(mock_metric):
    from agent.nodes import critique_remediation

    incident = new_incident(mock_metric, "low")
    incident["recommended_action"] = "kubectl restart pod api-pod -n production"
    incident["status"] = "analyzing"

    # Safe command -> Mock critique approves it
    res = critique_remediation(incident)
    assert res["confidence_score"] >= 80
    assert "approved" in res["critique"]
    # Should keep status (decide_action will evaluate it next)
    assert res["status"] == "analyzing"


def test_critique_remediation_rejected(mock_metric):
    from agent.nodes import critique_remediation

    incident = new_incident(mock_metric, "low")
    incident["recommended_action"] = "rm -rf /"
    incident["status"] = "analyzing"

    # Unsafe command -> Mock critique blocks it and lowers confidence
    res = critique_remediation(incident)
    assert res["confidence_score"] < 80
    assert "rejected" in res["critique"]
    # Routing fallback: Low confidence overrides status to awaiting_approval
    assert res["status"] == "awaiting_approval"
