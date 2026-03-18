from __future__ import annotations

from unittest.mock import MagicMock, patch

from helixos.agents.observer import ObserverCritic
from helixos.exceptions import ObserverHaltException
from helixos.pydantic_models.critic import CriticVerdict


MOCK_SKILLS = [
    {
        'id': 'reliability_check',
        'system_prompt': 'You are a reliability critic...',
        'tools_yaml': None,
    }
]


@patch('helixos.agents.observer.StructuredOutputEnforcer')
@patch('helixos.agents.observer.SemanticSkillDiscovery')
def test_evaluate_returns_pass_verdict(
    mock_skill_discovery_class: MagicMock,
    mock_enforcer_class: MagicMock,
) -> None:
    mock_skill_discovery = mock_skill_discovery_class.return_value
    mock_skill_discovery.get_skills.return_value = MOCK_SKILLS
    mock_enforcer = mock_enforcer_class.return_value
    mock_enforcer.enforce.return_value = CriticVerdict(status='pass')

    observer = ObserverCritic('agents/core/critics')
    verdict = observer.evaluate('Review my authentication code', 'Looks good.')

    assert isinstance(verdict, CriticVerdict)
    assert verdict.status == 'pass'


@patch('helixos.agents.observer.SemanticSkillDiscovery')
def test_evaluate_returns_warn_verdict(
    mock_skill_discovery_class: MagicMock,
) -> None:
    mock_skill_discovery = mock_skill_discovery_class.return_value
    mock_skill_discovery.get_skills.return_value = MOCK_SKILLS
    mock_enforcer = MagicMock()
    mock_enforcer.enforce.return_value = CriticVerdict(
        status='warn',
        failure_mode='Minor concern',
        recommendation='Double-check the output',
    )

    observer = ObserverCritic('agents/core/critics', enforcer=mock_enforcer)
    verdict = observer.evaluate('Review my authentication code', 'Mostly okay.')

    assert verdict.status == 'warn'
    assert verdict.failure_mode == 'Minor concern'
    assert verdict.recommendation == 'Double-check the output'


@patch('helixos.agents.observer.SemanticSkillDiscovery')
def test_evaluate_returns_halt_verdict(
    mock_skill_discovery_class: MagicMock,
) -> None:
    mock_skill_discovery = mock_skill_discovery_class.return_value
    mock_skill_discovery.get_skills.return_value = MOCK_SKILLS
    mock_enforcer = MagicMock()
    mock_enforcer.enforce.return_value = CriticVerdict(
        status='halt',
        failure_mode='Hallucinated CVE',
        recommendation='Verify all CVE references',
    )

    observer = ObserverCritic('agents/core/critics', enforcer=mock_enforcer)
    verdict = observer.evaluate('Review my authentication code', 'CVE-9999 issue.')

    assert verdict.status == 'halt'


def test_observer_halt_exception_message() -> None:
    verdict = CriticVerdict(
        status='halt',
        failure_mode='Hallucinated CVE',
        recommendation='Verify all CVE references',
    )

    exception = ObserverHaltException(verdict)

    assert 'Hallucinated CVE' in str(exception)
    assert 'Verify all CVE references' in str(exception)


@patch('helixos.agents.observer.SemanticSkillDiscovery')
def test_evaluate_builds_correct_messages(
    mock_skill_discovery_class: MagicMock,
) -> None:
    mock_skill_discovery = mock_skill_discovery_class.return_value
    mock_skill_discovery.get_skills.return_value = MOCK_SKILLS
    mock_enforcer = MagicMock()
    mock_enforcer.enforce.return_value = CriticVerdict(status='pass')
    task_description = 'Review my authentication code'
    agent_output = 'The login flow checks passwords.'

    observer = ObserverCritic('agents/core/critics', enforcer=mock_enforcer)
    observer.evaluate(task_description, agent_output)

    enforce_call = mock_enforcer.enforce.call_args
    messages = enforce_call.args[1]

    assert MOCK_SKILLS[0]['system_prompt'] in messages[0]['content']
    assert task_description in messages[1]['content']
    assert agent_output in messages[1]['content']
