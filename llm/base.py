"""Provider-agnostic LLM interface used by the OpenSRE agent.

Every provider implements a single ``complete(system, user, max_tokens) -> str``
method so the agent nodes never depend on a specific vendor SDK. Add a new
provider by subclassing :class:`LLMProvider` and registering it in
``llm/__init__.py``.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Minimal text-in / text-out chat completion interface."""

    #: short identifier, e.g. "anthropic", "openai", "google"
    name: str = "base"

    @property
    def is_mock(self) -> bool:
        """True when configured with the ``mock_key`` sentinel (offline tests)."""
        return False

    @property
    def model(self) -> str:
        """The concrete model id this provider will call."""
        return ""

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Return the model's text response to ``system`` + ``user`` prompts."""
        ...


class ProviderNotInstalled(RuntimeError):
    """Raised when a provider's optional SDK dependency is missing."""

    def __init__(self, provider: str, package: str, install: str):
        super().__init__(
            f"The '{provider}' LLM provider requires the '{package}' package, "
            f"which is not installed. Install it with: {install}"
        )
