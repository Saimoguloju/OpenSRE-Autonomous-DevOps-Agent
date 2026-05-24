import os
import shutil
import pytest
from datetime import datetime

# Setup environment variables for testing
os.environ["SIMULATION_MODE"] = "true"
os.environ["OPENSRE_DB_PATH"] = "test_incidents.db"
os.environ["ANTHROPIC_API_KEY"] = "mock_key"

from config import config
from agent.state import new_incident, IncidentState, Metric
from agent.guardrails import RemediationGuardrail
from storage.incidents import IncidentStore
from agent.nodes import decide_action, execute_action
from agent.metrics import INCIDENTS_TOTAL, CLAUDE_LATENCY, ACTION_DURATION

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_incidents.db"
    store = IncidentStore(str(db_path))
    yield store

@pytest.fixture
def mock_metric() -> Metric:
    return Metric(
        source="kubernetes",
        name="pod_crash_loop",
        value=8.0,
        threshold=5.0,
        unit="count",
        host="production/api-deployment-7d9f8b-xk2p",
        timestamp=datetime.utcnow().isoformat()
    )

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
        "shred -u private.key"
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
        "SELECT * FROM pg_stat_activity WHERE query_start < NOW() - INTERVAL '5 minutes'"
    ]
    for cmd in safe_commands:
        is_safe, reason = RemediationGuardrail.validate_command(cmd)
        assert is_safe, f"Expected command to be allowed: {cmd}. Blocked because: {reason}"

def test_guardrail_forbidden_namespaces():
    # Kubectl commands targeting system namespaces must be blocked
    blocked_namespaces = [
        "kubectl delete pod api-pod -n kube-system",
        "kubectl restart pod security-pod -n security-system",
        "kubectl logs logger-pod --namespace kube-node-lease"
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

def test_decide_action_routing(mock_metric):
    # Low severity in simulation mode should auto-act
    low_incident = new_incident(mock_metric, "low")
    res = decide_action(low_incident)
    assert res["status"] == "acting"
    assert res["human_approved"] is True
    
    # High severity must await approval
    high_incident = new_incident(mock_metric, "high")
    res_high = decide_action(high_incident)
    assert res_high["status"] == "awaiting_approval"
    assert res_high["human_approved"] is None

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
    assert INCIDENTS_TOTAL.labels(source="cpu", severity="low", status="resolved")._value.get() == 1.0
