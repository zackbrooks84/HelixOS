"""Custom exceptions for HelixOS runtime integrations."""

from __future__ import annotations


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
