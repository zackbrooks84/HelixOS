"""LangGraph-based workflow engine for HelixOS recipe orchestration.

Provides a StateGraph-backed workflow that replaces manual sequential recipe
calls with checkpointed, halt/resumable multi-step execution.

LangGraph is an optional dependency. When it is not installed, ``HelixWorkflow``
falls back to sequential execution identical to the existing recipe pattern.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from helixos.agents.loader import AgentDefinition, load_agent
from helixos.agents.observer import ObserverCritic
from helixos.exceptions import ObserverHaltException
from helixos.orchestrator.structured import StructuredOutputEnforcer
from helixos.pydantic_models.critic import CriticVerdict
from helixos.pydantic_models.handoff import HandoffPayload

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    _LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGGRAPH_AVAILABLE = False


# ---------------------------------------------------------------------------
# State & step descriptors
# ---------------------------------------------------------------------------


class WorkflowState(TypedDict):
    """Typed dict representing the mutable state threaded through the graph.

    Fields:
        task: Original user task string.
        steps: Accumulated step records, each containing agent_name, handoff
            dict, verdict dict, and timestamp.
        current_step: Index of the step currently being executed.
        halted: True when the observer issued a halt verdict.
        halt_verdict: The ``CriticVerdict`` that triggered the halt, or None.
        final_output: Task summary produced by the last successful step.
    """

    task: str
    steps: list[dict[str, Any]]
    current_step: int
    halted: bool
    halt_verdict: Optional[CriticVerdict]
    final_output: Optional[str]


@dataclass
class WorkflowStep:
    """Describe a single agent step in a workflow.

    Inputs:
        agent_path: Filesystem path to the agent Markdown definition.
        name: Human-readable label for this step (used in logs and history).

    Outputs:
        A descriptor consumed by ``HelixWorkflow`` when building the graph.

    Failure modes:
        None. Validation of ``agent_path`` is deferred to ``load_agent``.
    """

    agent_path: str
    name: str


# ---------------------------------------------------------------------------
# Core workflow engine
# ---------------------------------------------------------------------------


class HelixWorkflow:
    """StateGraph-backed workflow engine with checkpoint and halt/resume support.

    Inputs:
        steps: Ordered list of ``WorkflowStep`` instances defining the chain.
        critic_skills_dir: Directory that ``ObserverCritic`` uses to discover
            critic skills. Defaults to ``"agents/core/critics"``.

    Outputs:
        An initialized workflow engine whose ``run`` and ``resume`` methods
        return a populated ``WorkflowState``.

    Failure modes:
        Propagates ``load_agent``, ``StructuredOutputEnforcer.enforce``, and
        ``ObserverCritic.evaluate`` errors unless the observer halts first.
        When langgraph is unavailable a warning is printed and execution falls
        back to the sequential strategy.
    """

    def __init__(
        self,
        steps: list[WorkflowStep],
        critic_skills_dir: str = "agents/core/critics",
    ) -> None:
        """Store configuration and initialise shared dependencies.

        Inputs:
            steps: Ordered workflow steps to execute.
            critic_skills_dir: Critic skills directory path.

        Outputs:
            None.

        Failure modes:
            Propagates ``ObserverCritic`` and ``StructuredOutputEnforcer``
            initialisation errors.
        """
        self.steps = steps
        self.critic_skills_dir = critic_skills_dir
        self.enforcer = StructuredOutputEnforcer()
        self.observer = ObserverCritic(critic_skills_dir, enforcer=self.enforcer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, task: str) -> WorkflowState:
        """Build the StateGraph and execute all workflow steps from scratch.

        Inputs:
            task: User task string forwarded to every agent in the chain.

        Outputs:
            A ``WorkflowState`` with all executed steps recorded. When a step
            produces a halt verdict the state has ``halted=True`` and
            ``halt_verdict`` set.

        Failure modes:
            Propagates agent-loading and enforcer errors from individual steps.
            Falls back to sequential execution when langgraph is not installed.
        """
        initial: WorkflowState = {
            "task": task,
            "steps": [],
            "current_step": 0,
            "halted": False,
            "halt_verdict": None,
            "final_output": None,
        }

        if not _LANGGRAPH_AVAILABLE:
            print(
                "Warning: langgraph is not installed. "
                "Falling back to sequential execution. "
                "Install langgraph to enable checkpointing: pip install langgraph"
            )
            return self._run_sequential(initial)

        return self._run_graph(initial)

    def resume(self, state: WorkflowState) -> WorkflowState:
        """Resume execution from a previously halted state.

        The caller is responsible for deciding whether halted state should be
        continued (e.g. after human review). Execution restarts from
        ``state["current_step"]``.

        Inputs:
            state: A ``WorkflowState`` previously returned by ``run`` or
                ``resume`` with ``halted=True``.

        Outputs:
            Updated ``WorkflowState`` after continuing execution.

        Failure modes:
            Returns the state unchanged when it is not in a halted condition.
            Propagates the same errors as ``run``.
        """
        if not state["halted"]:
            return state

        # Clear halt markers so execution proceeds
        resumed: WorkflowState = {
            **state,
            "halted": False,
            "halt_verdict": None,
        }

        if not _LANGGRAPH_AVAILABLE:
            print(
                "Warning: langgraph is not installed. "
                "Falling back to sequential execution. "
                "Install langgraph to enable checkpointing: pip install langgraph"
            )
            return self._run_sequential(resumed)

        return self._run_graph(resumed)

    def get_history(self, state: WorkflowState) -> list[dict[str, Any]]:
        """Return a copy of the executed steps for debugging or display.

        Inputs:
            state: Any ``WorkflowState`` returned by ``run`` or ``resume``.

        Outputs:
            A list of step dicts, each with keys: ``agent_name``, ``handoff``,
            ``verdict``, and ``timestamp``.

        Failure modes:
            None.
        """
        return list(state["steps"])

    # ------------------------------------------------------------------
    # Graph construction (langgraph path)
    # ------------------------------------------------------------------

    def _run_graph(self, initial_state: WorkflowState) -> WorkflowState:
        """Build a ``StateGraph`` and run it from ``initial_state``.

        Each workflow step becomes a named node. A routing function after each
        node directs the graph to the next step on pass/warn or to END on halt.

        Inputs:
            initial_state: Starting ``WorkflowState`` (may have steps already
                populated when resuming).

        Outputs:
            Final ``WorkflowState`` after graph execution completes.

        Failure modes:
            Propagates agent and enforcer errors from node functions.
        """
        graph: StateGraph = StateGraph(WorkflowState)
        checkpointer = MemorySaver()

        node_names: list[str] = []
        for i, step in enumerate(self.steps):
            node_name = f"step_{i}_{step.name}"
            node_names.append(node_name)
            # Capture loop variables explicitly for the closure
            graph.add_node(node_name, self._make_node(i, step))

        # Wire edges: each node routes to next or END based on halt flag
        for idx, node_name in enumerate(node_names):
            is_last = idx == len(node_names) - 1
            next_node = node_names[idx + 1] if not is_last else None

            graph.add_conditional_edges(
                node_name,
                self._make_router(next_node),
            )

        if node_names:
            graph.set_entry_point(node_names[0])
        else:
            graph.set_entry_point(END)  # type: ignore[arg-type]

        compiled = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": "workflow-run"}}

        # Skip steps that were already completed (resume scenario)
        start_step = initial_state["current_step"]
        if start_step > 0 and node_names:
            # Replay completed steps as no-ops by fast-forwarding state
            entry = node_names[min(start_step, len(node_names) - 1)]
            graph.set_entry_point(entry)
            compiled = graph.compile(checkpointer=checkpointer)

        final = compiled.invoke(initial_state, config=config)
        return final  # type: ignore[return-value]

    def _make_node(self, step_index: int, step: WorkflowStep):
        """Return a node function for the given step index and descriptor.

        Inputs:
            step_index: Zero-based position in the workflow.
            step: ``WorkflowStep`` containing agent path and name.

        Outputs:
            A callable ``(WorkflowState) -> WorkflowState`` suitable for use as
            a LangGraph node.

        Failure modes:
            The returned callable propagates agent loading and enforcer errors.
        """
        enforcer = self.enforcer
        observer = self.observer

        def node_fn(state: WorkflowState) -> WorkflowState:
            # Skip if we are past this step already (resume path)
            if state["current_step"] > step_index:
                return state

            agent: AgentDefinition = load_agent(step.agent_path)

            # Build context from all previously executed steps
            prior_steps = state["steps"]
            if prior_steps:
                last = prior_steps[-1]
                user_content = (
                    f"Original task: {state['task']}\n\n"
                    f"Previous step ({last['agent_name']}) summary: "
                    f"{last['handoff'].get('task_summary', '')}\n"
                    f"Previous step context: {last['handoff'].get('context', {})}"
                )
            else:
                user_content = state["task"]

            messages = [
                {"role": "system", "content": agent.body},
                {"role": "user", "content": user_content},
            ]

            handoff: HandoffPayload = enforcer.enforce(HandoffPayload, messages)

            task_for_critic = (
                prior_steps[-1]["handoff"].get("task_summary", state["task"])
                if prior_steps
                else state["task"]
            )
            verdict: CriticVerdict = observer.evaluate(
                task_for_critic, handoff.task_summary
            )

            step_record: dict[str, Any] = {
                "agent_name": step.name,
                "handoff": handoff.model_dump(),
                "verdict": verdict.model_dump(),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }

            new_steps = list(state["steps"]) + [step_record]
            new_halted = verdict.status == "halt"
            new_halt_verdict = verdict if new_halted else state["halt_verdict"]
            new_output = handoff.task_summary if not new_halted else state["final_output"]
            new_current = step_index + 1

            if verdict.status == "warn":
                print(f"Observer: WARN [{step.name}] - {verdict.failure_mode}")
            elif verdict.status == "pass":
                print(f"Observer: PASS [{step.name}]")

            return {
                **state,
                "steps": new_steps,
                "current_step": new_current,
                "halted": new_halted,
                "halt_verdict": new_halt_verdict,
                "final_output": new_output,
            }

        return node_fn

    def _make_router(self, next_node: Optional[str]):
        """Return a routing function that sends the graph to the next node or END.

        Inputs:
            next_node: Name of the next graph node, or ``None`` when this is
                the last step.

        Outputs:
            A callable ``(WorkflowState) -> str`` returning the node name to
            transition to.

        Failure modes:
            None.
        """
        def router(state: WorkflowState) -> str:
            if state["halted"]:
                return END  # type: ignore[return-value]
            if next_node is None:
                return END  # type: ignore[return-value]
            return next_node

        return router

    # ------------------------------------------------------------------
    # Sequential fallback (no langgraph)
    # ------------------------------------------------------------------

    def _run_sequential(self, state: WorkflowState) -> WorkflowState:
        """Execute workflow steps sequentially without LangGraph.

        Mirrors the logic of the existing recipe pattern: load agent, enforce
        structured output, evaluate with critic, halt or continue.

        Inputs:
            state: Starting ``WorkflowState``.

        Outputs:
            Final ``WorkflowState`` after all steps or a halt.

        Failure modes:
            Propagates agent loading and enforcer errors.
        """
        current = dict(state)
        start_index = current["current_step"]

        for i, step in enumerate(self.steps):
            if i < start_index:
                continue

            agent: AgentDefinition = load_agent(step.agent_path)

            prior_steps = current["steps"]
            if prior_steps:
                last = prior_steps[-1]
                user_content = (
                    f"Original task: {current['task']}\n\n"
                    f"Previous step ({last['agent_name']}) summary: "
                    f"{last['handoff'].get('task_summary', '')}\n"
                    f"Previous step context: {last['handoff'].get('context', {})}"
                )
            else:
                user_content = current["task"]

            messages = [
                {"role": "system", "content": agent.body},
                {"role": "user", "content": user_content},
            ]

            handoff: HandoffPayload = self.enforcer.enforce(HandoffPayload, messages)

            task_for_critic = (
                prior_steps[-1]["handoff"].get("task_summary", current["task"])
                if prior_steps
                else current["task"]
            )
            verdict: CriticVerdict = self.observer.evaluate(
                task_for_critic, handoff.task_summary
            )

            step_record: dict[str, Any] = {
                "agent_name": step.name,
                "handoff": handoff.model_dump(),
                "verdict": verdict.model_dump(),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }

            current["steps"] = list(current["steps"]) + [step_record]
            current["current_step"] = i + 1

            if verdict.status == "warn":
                print(f"Observer: WARN [{step.name}] - {verdict.failure_mode}")
            elif verdict.status == "pass":
                print(f"Observer: PASS [{step.name}]")
            else:
                current["halted"] = True
                current["halt_verdict"] = verdict
                return WorkflowState(**current)  # type: ignore[misc]

            current["final_output"] = handoff.task_summary

        return WorkflowState(**current)  # type: ignore[misc]
