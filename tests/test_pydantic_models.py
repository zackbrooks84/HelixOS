import pytest
from pydantic import ValidationError

from helixos.pydantic_models import CriticVerdict, HandoffPayload


def test_handoff_payload_valid_construction_with_all_fields() -> None:
    payload = HandoffPayload(
        target_agent="observer",
        task_summary="Review the workflow state.",
        context={"ticket": "HX-123"},
        artifacts=["report.md"],
        priority=3,
    )

    assert payload.target_agent == "observer"
    assert payload.task_summary == "Review the workflow state."
    assert payload.context == {"ticket": "HX-123"}
    assert payload.artifacts == ["report.md"]
    assert payload.priority == 3



def test_handoff_payload_defaults_for_artifacts_and_priority() -> None:
    payload = HandoffPayload(
        target_agent="critic",
        task_summary="Inspect changes.",
        context={"scope": "tests"},
    )

    assert payload.artifacts == []
    assert payload.priority == 1



def test_handoff_payload_context_accepts_nested_dicts() -> None:
    payload = HandoffPayload(
        target_agent="router",
        task_summary="Route nested context.",
        context={"outer": {"inner": {"value": 1}}},
    )

    assert payload.context == {"outer": {"inner": {"value": 1}}}



def test_critic_verdict_valid_with_pass_status() -> None:
    verdict = CriticVerdict(status="pass")

    assert verdict.status == "pass"



def test_critic_verdict_valid_with_warn_status() -> None:
    verdict = CriticVerdict(status="warn")

    assert verdict.status == "warn"



def test_critic_verdict_valid_with_halt_status() -> None:
    verdict = CriticVerdict(status="halt")

    assert verdict.status == "halt"



def test_critic_verdict_raises_validation_error_for_invalid_status() -> None:
    with pytest.raises(ValidationError):
        CriticVerdict(status="invalid")



def test_critic_verdict_defaults_failure_mode_and_recommendation_to_none() -> None:
    verdict = CriticVerdict(status="warn")

    assert verdict.failure_mode is None
    assert verdict.recommendation is None
