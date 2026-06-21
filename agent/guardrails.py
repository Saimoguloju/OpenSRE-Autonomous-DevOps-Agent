import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# List of dangerous patterns to reject
DANGEROUS_PATTERNS = [
    r"\brm\b\s+-[rfRF]+",  # rm -rf or similar
    r"\bmkfs\b",  # Filesystem formatting
    r"\bdrop\b\s+\bdatabase\b",  # DB drop
    r"\bdrop\b\s+\btable\b",  # Table drop
    r"\bdelete\b\s+namespace\b",  # Kubernetes namespace deletion
    r"\bdelete\b\s+all\b",  # Kubernetes delete all
    r"\btruncate\b\s+\btable\b",  # Table truncation
    r"\bdd\b\s+if=",  # Raw disk writing dd
    r">/dev/sd[a-z]",  # Writing to raw disk blocks
    r"\bshred\b",  # Shred file destruction
]

# Namespaces that are strictly forbidden to modify
FORBIDDEN_NAMESPACES = [
    "kube-system",
    "kube-public",
    "kube-node-lease",
    "kube-node",
    "security-system",
]


class RemediationGuardrail:
    """
    Validates and sanitizes proposed SRE execution commands.
    Ensures that AI recommendations do not introduce security issues, command injections,
    or catastrophic actions.
    """

    @staticmethod
    def validate_command(command: str) -> Tuple[bool, str]:
        """
        Validates the command against safety rules.
        Returns:
            (is_safe, error_reason)
        """
        if not command:
            return False, "Command is empty"

        cmd_lower = command.lower().strip()

        # 1. Check for command chaining attempts (injection vectors)
        # We allow simple kubectl pipes (e.g., to grep or tail), but reject general chaining
        if ";" in cmd_lower or "&&" in cmd_lower or "||" in cmd_lower:
            # Check if they are part of safe commands
            # For SRE tools, we should be conservative. Reject overall chaining.
            return False, "Command chaining (;, &&, ||) is forbidden for safety"

        # 2. Check blocklisted patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, cmd_lower):
                return False, f"Dangerous command pattern matched: '{pattern}'"

        # 3. Check for namespace access in kubectl commands
        if "kubectl" in cmd_lower:
            # Extract namespace if present: -n <namespace> or --namespace=<namespace> or --namespace <namespace>
            ns_match = re.search(
                r"(?:-n\s+|--namespace=|\s+--namespace\s+)([a-zA-Z0-9_-]+)", cmd_lower
            )
            if ns_match:
                ns = ns_match.group(1).strip()
                if ns in FORBIDDEN_NAMESPACES:
                    return False, f"Access to system namespace '{ns}' is forbidden"
            else:
                # If no namespace is specified, check if namespace flag is completely missing
                # and if we should enforce that default kubectl target isn't system-wide
                if "delete" in cmd_lower and "all" in cmd_lower:
                    return (
                        False,
                        "Kubectl delete all without explicit namespace is forbidden",
                    )

        # 4. Check for SQL Injection risks in database tool inputs
        if any(
            keyword in cmd_lower for keyword in ["select", "update", "delete", "insert"]
        ):
            # Check if it contains multiple queries separated by a semicolon
            # We want to be safe when execution occurs
            if ";" in cmd_lower and not cmd_lower.endswith(";"):
                return False, "Multiple SQL queries in a single string are forbidden"

        return True, ""
