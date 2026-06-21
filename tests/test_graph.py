"""End-to-end LangGraph pipeline tests with a mocked Claude client."""

import os

import pytest

from config import config
from agent.state import new_incident
import agent.nodes as nodes
from agent.graph import sre_graph, resume_incident

_ANALYSIS = (
    "ROOT CAUSE: Pod was OOMKilled after a memory leak in the request handler.\n"
    "RECOMMENDED ACTION: kubectl delete pod api-pod -n production\n"
    "RISK LEVEL: medium\n"
    "ESTIMATED FIX TIME: 2 minutes"
)


@pytest.fixture
def fake_claude(monkeypatch, tmp_path):
    """Mock the LLM provider call and isolate post-mortem output to a temp dir.

    Patching the provider-agnostic ``_complete`` seam means this test is
    independent of which LLM provider is configured.
    """
    monkeypatch.setattr(
        nodes, "_complete", lambda system, user, max_tokens=1024: _ANALYSIS
    )
    monkeypatch.chdir(tmp_path)  # post_mortems/ is written relative to cwd
    return tmp_path


def test_pipeline_parses_analysis_and_awaits_human(
    fake_claude, mock_metric, monkeypatch
):
    # Safe default: auto-remediation off -> the incident awaits human approval.
    monkeypatch.setattr(config, "auto_remediate", False)
    incident = new_incident(mock_metric, "high")

    result = sre_graph.invoke(incident)

    assert result["root_cause"].startswith("Pod was OOMKilled")
    assert "kubectl delete pod" in result["recommended_action"]
    # Self-critique (mock path) approved the safe command with high confidence.
    assert result["confidence_score"] >= 80
    assert result["status"] == "awaiting_approval"
    assert result["human_approved"] is None


def test_pipeline_autonomous_when_enabled(fake_claude, mock_metric, monkeypatch):
    monkeypatch.setattr(config, "auto_remediate", True)
    monkeypatch.setattr(config, "simulation_mode", True)
    incident = new_incident(mock_metric, "high")

    result = sre_graph.invoke(incident)

    # High-confidence, non-critical, auto-remediate on -> resolved in one pass.
    assert result["status"] == "resolved"
    assert "[SIMULATION]" in result["action_taken"]
    # Post-mortem written to the isolated temp dir.
    assert (
        fake_claude / "post_mortems" / f"incident_{result['incident_id']}.md"
    ).exists()


def test_resume_after_approval_executes(fake_claude, mock_metric):
    incident = new_incident(mock_metric, "critical")
    incident["recommended_action"] = "kubectl delete pod api-pod -n production"
    incident["status"] = "awaiting_approval"
    incident["human_approved"] = True

    result = resume_incident(incident)
    assert result["status"] == "resolved"
    assert "[SIMULATION]" in result["action_taken"]


def test_resume_after_ignore_marks_ignored(fake_claude, mock_metric):
    incident = new_incident(mock_metric, "critical")
    incident["status"] = "awaiting_approval"
    incident["human_approved"] = False

    result = resume_incident(incident)
    assert result["status"] == "ignored"
    assert "ignore" in result["action_taken"].lower()


def test_resume_without_decision_is_noop(fake_claude, mock_metric):
    incident = new_incident(mock_metric, "high")
    incident["status"] = "awaiting_approval"
    incident["human_approved"] = None

    result = resume_incident(incident)
    assert result["status"] == "awaiting_approval"


def test_resume_blocks_unsafe_command(fake_claude, mock_metric):
    incident = new_incident(mock_metric, "high")
    incident["recommended_action"] = "rm -rf /var/lib/data"
    incident["status"] = "awaiting_approval"
    incident["human_approved"] = True

    result = resume_incident(incident)
    # Guardrail blocks execution even though a human approved.
    assert result["status"] == "ignored"
    assert "BLOCKED BY SAFETY GUARDRAIL" in result["action_taken"]
