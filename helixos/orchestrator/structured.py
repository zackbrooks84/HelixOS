"""Structured output enforcement for Ollama-backed agent responses."""

from __future__ import annotations

from pydantic import BaseModel

import instructor
from openai import OpenAI

from helixos.exceptions import OllamaConnectionError


class StructuredOutputEnforcer:
    """Validate LLM responses against Pydantic models via Instructor.

    Inputs:
        ollama_base_url: OpenAI-compatible Ollama base URL.
        default_model: Default Ollama model name used when no override is
            supplied to ``enforce``.

    Outputs:
        An enforcer instance with an Instructor-patched OpenAI client stored on
        ``self.client``.

    Failure modes:
        Propagates client-construction errors from Instructor or OpenAI during
        initialization.
        Raises ``OllamaConnectionError`` from ``enforce`` when Ollama is
        unreachable.
    """

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434/v1",
        default_model: str = "qwen2.5:7b",
    ) -> None:
        """Initialize the Instructor-patched OpenAI client.

        Inputs:
            ollama_base_url: OpenAI-compatible Ollama base URL.
            default_model: Default model name used for structured generation.

        Outputs:
            None.

        Failure modes:
            Propagates exceptions raised while creating the OpenAI or
            Instructor client.
        """
        self.client = instructor.from_openai(
            OpenAI(base_url=ollama_base_url, api_key="ollama"),
            mode=instructor.Mode.JSON,
        )
        self.ollama_base_url = ollama_base_url
        self.default_model = default_model

    def enforce(
        self,
        model_class: type[BaseModel],
        messages: list[dict],
        ollama_model: str | None = None,
    ) -> BaseModel:
        """Return a validated structured response for the supplied messages.

        Inputs:
            model_class: Pydantic model type used to validate the response.
            messages: OpenAI-compatible chat message dictionaries.
            ollama_model: Optional Ollama model override.

        Outputs:
            A validated instance of ``model_class``.

        Failure modes:
            Raises ``OllamaConnectionError`` if the client reports a connection
            failure while contacting Ollama.
            Propagates other client and validation exceptions unchanged.
        """
        try:
            return self.client.chat.completions.create(
                model=ollama_model or self.default_model,
                response_model=model_class,
                messages=messages,
            )
        except Exception as exc:  # pragma: no cover - branch exercised in tests
            exc_type_name = type(exc).__name__
            exc_message = str(exc)
            if (
                "Connect" in exc_type_name
                or "Connection refused" in exc_message
                or "connect" in exc_message
            ):
                raise OllamaConnectionError(
                    f"Cannot connect to Ollama at {self.ollama_base_url}.\n"
                    "Make sure Ollama is running: ollama serve"
                ) from exc
            raise
