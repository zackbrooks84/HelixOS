from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from helixos.exceptions import OllamaConnectionError
from helixos.orchestrator.structured import StructuredOutputEnforcer
from helixos.pydantic_models import CriticVerdict, HandoffPayload


@patch("helixos.orchestrator.structured.instructor.from_openai")
def test_enforce_returns_critic_verdict(mock_from_openai: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = CriticVerdict(status="pass")
    mock_from_openai.return_value = mock_client
    enforcer = StructuredOutputEnforcer()

    result = enforcer.enforce(
        CriticVerdict,
        messages=[{"role": "user", "content": "Review the workflow."}],
    )

    assert isinstance(result, CriticVerdict)
    assert result.status == "pass"


@patch("helixos.orchestrator.structured.instructor.from_openai")
def test_enforce_returns_handoff_payload(mock_from_openai: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = HandoffPayload(
        target_agent="Security Auditor",
        task_summary="Review complete",
        context={},
    )
    mock_from_openai.return_value = mock_client
    enforcer = StructuredOutputEnforcer()

    result = enforcer.enforce(
        HandoffPayload,
        messages=[{"role": "user", "content": "Prepare the handoff."}],
    )

    assert isinstance(result, HandoffPayload)
    assert result.target_agent == "Security Auditor"
    assert result.task_summary == "Review complete"
    assert result.context == {}


@patch("helixos.orchestrator.structured.instructor.from_openai")
def test_enforce_raises_on_connection_error(mock_from_openai: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = ConnectionRefusedError()
    mock_from_openai.return_value = mock_client
    enforcer = StructuredOutputEnforcer()

    with pytest.raises(OllamaConnectionError) as error_info:
        enforcer.enforce(
            CriticVerdict,
            messages=[{"role": "user", "content": "Validate the verdict."}],
        )

    assert "ollama serve" in str(error_info.value)


@patch("helixos.orchestrator.structured.instructor.from_openai")
def test_default_model_used_when_none_passed(mock_from_openai: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = CriticVerdict(status="pass")
    mock_from_openai.return_value = mock_client
    enforcer = StructuredOutputEnforcer(default_model="qwen2.5:7b")

    enforcer.enforce(
        CriticVerdict,
        messages=[{"role": "user", "content": "Use the default model."}],
        ollama_model=None,
    )

    create_call = mock_client.chat.completions.create.call_args
    assert create_call.kwargs["model"] == enforcer.default_model
