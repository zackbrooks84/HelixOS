"""Custom exceptions for HelixOS runtime integrations."""

from __future__ import annotations

from helixos.pydantic_models.critic import CriticVerdict


class OllamaConnectionError(Exception):
    """Raised when HelixOS cannot connect to the configured Ollama server.

    Inputs:
        None directly. Raised in response to lower-level connection failures.

    Outputs:
        An exception instance describing how to restore Ollama connectivity.

    Failure modes:
        This exception is itself a failure signal and should be handled by
        callers that need to surface a user-facing remediation message.
    """

    pass


class ObserverHaltException(Exception):
    """Raised when the observer returns a halt verdict.

    Inputs:
        verdict: Structured critic verdict that triggered workflow halt.

    Outputs:
        An exception instance carrying the verdict on ``self.verdict``.

    Failure modes:
        This exception is itself the failure signal and should be handled by
        orchestrator layers that implement halt UX.
    """

    def __init__(self, verdict: CriticVerdict) -> None:
        """Store the critic verdict and construct a user-facing message.

        Inputs:
            verdict: Structured verdict with halt context.

        Outputs:
            None.

        Failure modes:
            None beyond standard exception construction.
        """
        self.verdict = verdict
        super().__init__(
            f"Observer halted workflow. "
            f"Failure: {verdict.failure_mode}. "
            f"Recommendation: {verdict.recommendation}"
        )
