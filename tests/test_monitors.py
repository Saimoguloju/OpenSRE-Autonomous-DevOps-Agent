"""Tests for the monitor layer: severity formula and per-monitor polling."""

import pytest

from monitors.base import BaseMonitor
from monitors.cpu import CpuMonitor
from monitors.database import DatabaseMonitor
from monitors.kubernetes import KubernetesMonitor

# ── Severity formula (static) ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,threshold,expected",
    [
        (40, 100, "low"),  # ratio 0.4
        (100, 100, "medium"),  # ratio 1.0 (boundary)
        (125, 100, "high"),  # ratio 1.25 (boundary)
        (150, 100, "critical"),  # ratio 1.5 (boundary)
        (300, 100, "critical"),
    ],
)
def test_severity_classification(value, threshold, expected):
    assert BaseMonitor.severity(value, threshold) == expected


def test_severity_is_static():
    # Callable without an instance (no ABC/__new__ tricks).
    assert BaseMonitor.severity(9, 5) == "critical"


def test_severity_zero_threshold_guard():
    # Must not raise ZeroDivisionError.
    assert BaseMonitor.severity(1, 0) == "critical"
    assert BaseMonitor.severity(0, 0) == "low"


# ── CPU / memory monitor ─────────────────────────────────────────────────────


def test_cpu_monitor_emits_when_over_threshold(monkeypatch):
    import monitors.cpu as cpu_mod

    monkeypatch.setattr(cpu_mod.psutil, "cpu_percent", lambda interval=1: 99.0)

    class _Mem:
        percent = 95.0

    monkeypatch.setattr(cpu_mod.psutil, "virtual_memory", lambda: _Mem())

    alerts = CpuMonitor().poll()
    sources = {a["source"] for a in alerts}
    assert "cpu" in sources and "memory" in sources
    cpu_alert = next(a for a in alerts if a["source"] == "cpu")
    assert cpu_alert["value"] == 99.0
    assert cpu_alert["unit"] == "percent"


def test_cpu_monitor_silent_when_healthy(monkeypatch):
    import monitors.cpu as cpu_mod

    monkeypatch.setattr(cpu_mod.psutil, "cpu_percent", lambda interval=1: 5.0)

    class _Mem:
        percent = 10.0

    monkeypatch.setattr(cpu_mod.psutil, "virtual_memory", lambda: _Mem())
    assert CpuMonitor().poll() == []


# ── Database monitor (simulation) ────────────────────────────────────────────


def test_database_monitor_triggers_on_fifth_poll():
    mon = DatabaseMonitor()
    results = [mon.poll() for _ in range(5)]
    # Polls 1-4 are quiet; the 5th surfaces a simulated slow query.
    assert all(r == [] for r in results[:4])
    assert len(results[4]) == 1
    alert = results[4][0]
    assert alert["source"] == "database"
    assert alert["value"] >= alert["threshold"]


def test_database_call_count_is_per_instance():
    a, b = DatabaseMonitor(), DatabaseMonitor()
    a.poll()
    assert b._call_count == 0  # not shared across instances


# ── Kubernetes monitor (simulation) ──────────────────────────────────────────


def test_kubernetes_monitor_triggers_on_eighth_poll():
    mon = KubernetesMonitor()
    results = [mon.poll() for _ in range(8)]
    assert all(r == [] for r in results[:7])
    assert len(results[7]) == 1
    alert = results[7][0]
    assert alert["source"] == "kubernetes"
    assert alert["name"] == "pod_crash_loop"
    assert alert["host"].startswith("production/")
