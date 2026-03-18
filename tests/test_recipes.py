from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from helixos.exceptions import ObserverHaltException
from helixos.pydantic_models.critic import CriticVerdict
from helixos.pydantic_models.handoff import HandoffPayload
from recipes import frontend_builder, repo_auditor, research_report


def _handoff(
    target_agent: str,
    task_summary: str,
    context: dict[str, str] | None = None,
) -> HandoffPayload:
    """Build a test handoff payload.

    Inputs:
        target_agent: Agent that should receive the handoff.
        task_summary: Summary text used by the next step.
        context: Optional structured context.

    Outputs:
        A valid ``HandoffPayload`` instance.

    Failure modes:
        Propagates Pydantic validation errors if invalid values are supplied.
    """
    return HandoffPayload(
        target_agent=target_agent,
        task_summary=task_summary,
        context=context or {},
    )


@patch("recipes.repo_auditor.ObserverCritic.__init__", return_value=None)
@patch("recipes.repo_auditor.ObserverCritic.evaluate")
@patch("recipes.repo_auditor.StructuredOutputEnforcer.enforce")
def test_repo_auditor_pass_completes(
    mock_enforce: MagicMock,
    mock_evaluate: MagicMock,
    mock_observer_init: MagicMock,
) -> None:
    mock_enforce.side_effect = [
        _handoff("Security Auditor", "Code review complete"),
        _handoff("Research Analyst", "Security review complete"),
        _handoff("Done", "Research summary complete"),
    ]
    mock_evaluate.side_effect = [
        CriticVerdict(status="pass"),
        CriticVerdict(status="pass"),
        CriticVerdict(status="pass"),
    ]

    result = repo_auditor.run("review my auth module")

    assert result
    assert result == "Research summary complete"


@patch("recipes.repo_auditor.ObserverCritic.__init__", return_value=None)
@patch("recipes.repo_auditor.ObserverCritic.evaluate")
@patch("recipes.repo_auditor.StructuredOutputEnforcer.enforce")
def test_repo_auditor_warn_continues(
    mock_enforce: MagicMock,
    mock_evaluate: MagicMock,
    mock_observer_init: MagicMock,
) -> None:
    mock_enforce.side_effect = [
        _handoff("Security Auditor", "Code review complete"),
        _handoff("Research Analyst", "Security review complete"),
        _handoff("Done", "Research summary complete"),
    ]
    mock_evaluate.side_effect = [
        CriticVerdict(
            status="warn",
            failure_mode="Needs a second look",
            recommendation="Proceed carefully",
        ),
        CriticVerdict(status="pass"),
        CriticVerdict(status="pass"),
    ]

    result = repo_auditor.run("review my auth module")

    assert result == "Research summary complete"


@patch("recipes.repo_auditor.ObserverCritic.__init__", return_value=None)
@patch("recipes.repo_auditor.ObserverCritic.evaluate")
@patch("recipes.repo_auditor.StructuredOutputEnforcer.enforce")
def test_repo_auditor_halt_raises(
    mock_enforce: MagicMock,
    mock_evaluate: MagicMock,
    mock_observer_init: MagicMock,
) -> None:
    mock_enforce.side_effect = [
        _handoff("Security Auditor", "Code review complete"),
    ]
    mock_evaluate.return_value = CriticVerdict(
        status="halt",
        failure_mode="Bug found",
        recommendation="Fix it",
    )

    with pytest.raises(ObserverHaltException) as error_info:
        repo_auditor.run("review my auth module")

    assert "Bug found" in str(error_info.value)


@patch("recipes.frontend_builder.ObserverCritic.__init__", return_value=None)
@patch("recipes.frontend_builder.ObserverCritic.evaluate")
@patch("recipes.frontend_builder.StructuredOutputEnforcer.enforce")
def test_frontend_builder_pass_completes(
    mock_enforce: MagicMock,
    mock_evaluate: MagicMock,
    mock_observer_init: MagicMock,
) -> None:
    mock_enforce.side_effect = [
        _handoff("Code Reviewer", "Frontend changes prepared"),
        _handoff("Done", "Frontend review complete"),
    ]
    mock_evaluate.side_effect = [
        CriticVerdict(status="pass"),
        CriticVerdict(status="pass"),
    ]

    result = frontend_builder.run("build a responsive dashboard")

    assert result == "Frontend review complete"


@patch("recipes.research_report.ObserverCritic.__init__", return_value=None)
@patch("recipes.research_report.ObserverCritic.evaluate")
@patch("recipes.research_report.StructuredOutputEnforcer.enforce")
def test_research_report_pass_completes(
    mock_enforce: MagicMock,
    mock_evaluate: MagicMock,
    mock_observer_init: MagicMock,
) -> None:
    mock_enforce.side_effect = [
        _handoff("Automation Orchestrator", "Research collected"),
        _handoff("Done", "Execution plan prepared"),
    ]
    mock_evaluate.side_effect = [
        CriticVerdict(status="pass"),
        CriticVerdict(status="pass"),
    ]

    result = research_report.run("compare local vector stores")

    assert result == "Execution plan prepared"
