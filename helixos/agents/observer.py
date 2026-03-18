"""Observer critic orchestration for structured reliability verdicts."""

from __future__ import annotations

from helixos.agents.semantic_loader import SemanticSkillDiscovery
from helixos.orchestrator.structured import StructuredOutputEnforcer
from helixos.pydantic_models.critic import CriticVerdict


class ObserverCritic:
    """Evaluate agent outputs with observer-only critic skills.

    Inputs:
        critic_skills_dir: Directory containing critic skill folders that follow
            the blueprint skill format.
        enforcer: Optional structured output enforcer. When omitted, a default
            ``StructuredOutputEnforcer`` is created.
        chroma_path: Optional persistent ChromaDB path forwarded to semantic
            skill discovery.

    Outputs:
        An initialized observer critic that can produce ``CriticVerdict``
        instances via ``evaluate``.

    Failure modes:
        Raises ``FileNotFoundError`` if the critic skills directory is missing.
        Propagates discovery errors if semantic skill lookup fails.
        Raises ``ValueError`` if no critic skill is returned for evaluation.
        Propagates structured enforcement errors if verdict generation fails.
    """

    def __init__(
        self,
        critic_skills_dir: str,
        enforcer: StructuredOutputEnforcer | None = None,
        chroma_path: str | None = None,
    ) -> None:
        """Initialize observer dependencies.

        Inputs:
            critic_skills_dir: Directory containing critic skill definitions.
            enforcer: Optional preconfigured structured output enforcer.
            chroma_path: Optional persistent ChromaDB path for skill indexing.

        Outputs:
            None.

        Failure modes:
            Raises ``FileNotFoundError`` if ``critic_skills_dir`` does not
            exist.
            Propagates exceptions from dependency initialization.
        """
        self.skill_discovery = SemanticSkillDiscovery(
            critic_skills_dir,
            chroma_path=chroma_path,
        )
        self.enforcer = enforcer or StructuredOutputEnforcer()

    def evaluate(self, task_description: str, agent_output: str) -> CriticVerdict:
        """Evaluate an agent output against the best matching critic skill.

        Inputs:
            task_description: User or workflow task description used to retrieve
                the most relevant critic skill.
            agent_output: Agent output string to be evaluated.

        Outputs:
            A structured ``CriticVerdict``.

        Failure modes:
            Raises ``ValueError`` if no critic skill is available.
            Propagates semantic discovery and structured enforcement errors.
        """
        critic_skills = self.skill_discovery.get_skills(task_description, top_k=1)
        if not critic_skills:
            raise ValueError(
                "ObserverCritic could not find a critic skill for the task."
            )

        messages = [
            {"role": "system", "content": critic_skills[0]["system_prompt"]},
            {
                "role": "user",
                "content": "TASK: "
                + task_description
                + "\n\nAGENT OUTPUT TO EVALUATE:\n"
                + agent_output,
            },
        ]
        return self.enforcer.enforce(CriticVerdict, messages)
