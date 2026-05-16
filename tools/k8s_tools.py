import logging
import subprocess
from typing import List

from config import config

logger = logging.getLogger(__name__)


def _kubectl(args: List[str]) -> str:
    """Run a kubectl command and return stdout."""
    if config.simulation_mode:
        cmd_str = "kubectl " + " ".join(args)
        logger.info("[SIMULATION] %s", cmd_str)
        return f"[SIMULATION] {cmd_str} → OK"
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return f"kubectl error: {result.stderr.strip()}"
        return result.stdout.strip()
    except FileNotFoundError:
        return "kubectl not found — install kubectl or enable SIMULATION_MODE=true"
    except subprocess.TimeoutExpired:
        return "kubectl timed out"


def restart_pod(pod_name: str, namespace: str = "production") -> str:
    result = _kubectl(["delete", "pod", pod_name, "-n", namespace, "--grace-period=0"])
    return f"Restarted pod {pod_name}: {result}"


def scale_deployment(deployment: str, replicas: int, namespace: str = "production") -> str:
    result = _kubectl(["scale", "deployment", deployment, f"--replicas={replicas}", "-n", namespace])
    return f"Scaled {deployment} to {replicas} replicas: {result}"


def get_pod_logs(pod_name: str, namespace: str = "production", tail: int = 50) -> str:
    return _kubectl(["logs", pod_name, "-n", namespace, f"--tail={tail}"])


def get_pods(namespace: str = "production") -> str:
    return _kubectl(["get", "pods", "-n", namespace, "-o", "wide"])


def rollout_restart(deployment: str, namespace: str = "production") -> str:
    result = _kubectl(["rollout", "restart", f"deployment/{deployment}", "-n", namespace])
    return f"Rollout restart of {deployment}: {result}"
