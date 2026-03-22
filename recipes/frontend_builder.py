"""Frontend builder recipe with observer-enforced handoffs."""

from __future__ import annotations

from helixos.agents.loader import load_agent
from helixos.agents.observer import ObserverCritic
from helixos.exceptions import ObserverHaltException
from helixos.orchestrator.structured import StructuredOutputEnforcer
from helixos.pydantic_models.critic import CriticVerdict
from helixos.pydantic_models.handoff import HandoffPayload
from helixos.workflow import HelixWorkflow, WorkflowState, WorkflowStep


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
    """Run the frontend builder recipe chain.

    Inputs:
        task: User task to route through frontend implementation and code
            review.

    Outputs:
        The final task summary returned by the Code Reviewer handoff.

    Failure modes:
        Raises ``ObserverHaltException`` when the observer returns a halt
        verdict for any handoff in the chain.
        Propagates agent loading and structured output enforcement errors.
    """
    observer = ObserverCritic("agents/core/critics")
    enforcer = StructuredOutputEnforcer()

    frontend_builder = load_agent("agents/core/frontend_builder.md")
    handoff_1 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": frontend_builder.body},
            {"role": "user", "content": task},
        ],
    )
    verdict_1 = observer.evaluate(task, handoff_1.task_summary)
    _handle_verdict(verdict_1)

    code_reviewer = load_agent("agents/core/code_reviewer.md")
    handoff_2 = enforcer.enforce(
        HandoffPayload,
        [
            {"role": "system", "content": code_reviewer.body},
            {
                "role": "user",
                "content": (
                    f"Original task: {task}\n\n"
                    f"Frontend summary: {handoff_1.task_summary}\n"
                    f"Frontend context: {handoff_1.context}"
                ),
            },
        ],
    )
    verdict_2 = observer.evaluate(handoff_1.task_summary, handoff_2.task_summary)
    _handle_verdict(verdict_2)

    return handoff_2.task_summary


def run_v2(task: str) -> WorkflowState:
    """Run the frontend builder recipe chain via the LangGraph workflow engine.

    Inputs:
        task: User task to route through frontend implementation and code
            review.

    Outputs:
        A ``WorkflowState`` containing all executed step records, the final
        task summary, and halt information if applicable.

    Failure modes:
        Returns a halted ``WorkflowState`` instead of raising
        ``ObserverHaltException``. Propagates agent loading and structured
        output enforcement errors.
    """
    workflow = HelixWorkflow(
        steps=[
            WorkflowStep(
                agent_path="agents/core/frontend_builder.md",
                name="frontend_builder",
            ),
            WorkflowStep(
                agent_path="agents/core/code_reviewer.md",
                name="code_reviewer",
            ),
        ],
        critic_skills_dir="agents/core/critics",
    )
    return workflow.run(task)
