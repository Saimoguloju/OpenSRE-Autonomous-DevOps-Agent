"""
Shared pytest configuration for the OpenSRE test suite.

These environment variables MUST be set before `config` is imported anywhere,
because `config.config` is a module-level singleton built from the environment
at import time. Setting them here (conftest is imported before any test module)
guarantees every test runs fully offline in simulation mode with a mock API key.
"""

import os

# Force (not setdefault) so the unit suite is hermetic and CI-independent: the
# self-critique node's mock path keys off the exact "mock_key" sentinel, so a
# real key in the environment must not leak in and trigger live API calls.
os.environ["SIMULATION_MODE"] = "true"
os.environ["ANTHROPIC_API_KEY"] = "mock_key"
os.environ.setdefault("OPENSRE_DB_PATH", "test_incidents.db")

from datetime import datetime, UTC  # noqa: E402

import pytest  # noqa: E402

from agent.state import Metric  # noqa: E402
from storage.incidents import IncidentStore  # noqa: E402


@pytest.fixture
def temp_db(tmp_path):
    """A fresh, isolated SQLite IncidentStore per test."""
    return IncidentStore(str(tmp_path / "incidents.db"))


@pytest.fixture
def mock_metric() -> Metric:
    """A representative Kubernetes crash-loop breach."""
    return Metric(
        source="kubernetes",
        name="pod_crash_loop",
        value=8.0,
        threshold=5.0,
        unit="count",
        host="production/api-deployment-7d9f8b-xk2p",
        timestamp=datetime.now(UTC).isoformat(),
    )
