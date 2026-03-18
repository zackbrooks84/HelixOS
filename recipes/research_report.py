"""Research report recipe with observer-enforced handoffs."""

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
    """Run the research report recipe chain.

    Inputs:
        task: User task to route through research and orchestration.

    Outputs:
        The final task summary returned by the Automation Orchestrator handoff.

    Failure modes:
        Raises ``ObserverHaltException`` when the observer returns a halt
        verdict for any handoff in the chain.
        Propagates agent loading and structured output enforcement errors.
    """
    observer = ObserverCritic("agents/core/critics")
    enforcer = StructuredOutputEnforcer()

    research_analyst = load_agent("agents/core/research_analyst.md")
    handoff_1 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": research_analyst.body},
            {"role": "user", "content": task},
        ],
    )
    verdict_1 = observer.evaluate(task, handoff_1.task_summary)
    _handle_verdict(verdict_1)

    automation_orchestrator = load_agent("agents/core/automation_orchestrator.md")
    handoff_2 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": automation_orchestrator.body},
            {
                "role": "user",
                "content": (
                    f"Original task: {task}\n\n"
                    f"Research summary: {handoff_1.task_summary}\n"
                    f"Research context: {handoff_1.context}"
                ),
            },
        ],
    )
    verdict_2 = observer.evaluate(handoff_1.task_summary, handoff_2.task_summary)
    _handle_verdict(verdict_2)

    return handoff_2.task_summary
