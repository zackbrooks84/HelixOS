"""Repo auditor recipe with observer-enforced handoffs."""

from __future__ import annotations

from helixos.agents.loader import load_agent
from helixos.agents.observer import ObserverCritic
from helixos.exceptions import ObserverHaltException
from helixos.orchestrator.structured import StructuredOutputEnforcer
from helixos.pydantic_models.critic import CriticVerdict
from helixos.pydantic_models.handoff import HandoffPayload


def _handle_verdict(verdict: CriticVerdict) -> None:
    """Handle an observer verdict for a pending handoff.

    Inputs:
        verdict: Structured critic result returned by ``ObserverCritic``.

    Outputs:
        None.

    Failure modes:
        Raises ``ObserverHaltException`` when the verdict status is ``halt``.
    """
    if verdict.status == "pass":
        print("Observer: PASS")
        return
    if verdict.status == "warn":
        print(f"Observer: WARN - {verdict.failure_mode}")
        return
    raise ObserverHaltException(verdict)


def run(task: str) -> str:
    """Run the repo auditor recipe chain.

    Inputs:
        task: User task to route through the review, security, and research
            chain.

    Outputs:
        The final task summary returned by the Research Analyst handoff.

    Failure modes:
        Raises ``ObserverHaltException`` when the observer returns a halt
        verdict for any handoff in the chain.
        Propagates agent loading and structured output enforcement errors.
    """
    observer = ObserverCritic("agents/core/critics")
    enforcer = StructuredOutputEnforcer()

    code_reviewer = load_agent("agents/core/code_reviewer.md")
    handoff_1 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": code_reviewer.body},
            {"role": "user", "content": task},
        ],
    )
    verdict_1 = observer.evaluate(task, handoff_1.task_summary)
    _handle_verdict(verdict_1)

    security_auditor = load_agent("agents/core/security_auditor.md")
    handoff_2 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": security_auditor.body},
            {
                "role": "user",
                "content": (
                    f"Original task: {task}\n\n"
                    f"Previous handoff summary: {handoff_1.task_summary}\n\n"
                    f"Previous handoff context: {handoff_1.context}"
                ),
            },
        ],
    )
    verdict_2 = observer.evaluate(handoff_1.task_summary, handoff_2.task_summary)
    _handle_verdict(verdict_2)

    research_analyst = load_agent("agents/core/research_analyst.md")
    handoff_3 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": research_analyst.body},
            {
                "role": "user",
                "content": (
                    f"Original task: {task}\n\n"
                    f"Code review summary: {handoff_1.task_summary}\n"
                    f"Code review context: {handoff_1.context}\n\n"
                    f"Security summary: {handoff_2.task_summary}\n"
                    f"Security context: {handoff_2.context}"
                ),
            },
        ],
    )
    verdict_3 = observer.evaluate(handoff_2.task_summary, handoff_3.task_summary)
    _handle_verdict(verdict_3)

    return handoff_3.task_summary
