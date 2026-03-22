"""HelixOS facade — single entry point for the entire system."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import httpx

from helixos.agents.loader import AgentDefinition, load_all_agents, load_agent
from helixos.exceptions import ObserverHaltException, OllamaConnectionError
from helixos.orchestrator.router import IntelligentRouter
from helixos.orchestrator.structured import StructuredOutputEnforcer
from helixos.pydantic_models.critic import CriticVerdict
from helixos.pydantic_models.handoff import HandoffPayload
from helixos.resources.monitor import ResourceMonitor


# Recipes ship as modules inside the ``recipes`` package.  The facade resolves
# them by name so callers don't need to know the module layout.
_KNOWN_RECIPES: list[str] = [
    "repo_auditor",
    "frontend_builder",
    "research_report",
]

# Required files that every valid skill folder must contain.
_REQUIRED_SKILL_FILES: list[str] = ["system_prompt.md"]


class HelixOS:
    """High-level facade over the HelixOS orchestration system.

    Inputs:
        agents_dir: Directory tree containing agent Markdown definitions.
        skills_dir: Root directory for skill subfolders used by semantic
            discovery.
        critics_dir: Directory containing critic skill folders consumed by
            ``ObserverCritic``.
        ollama_url: Base URL for the local Ollama server (no trailing slash).

    Outputs:
        A configured facade instance.  All components that require Ollama are
        **lazy-loaded** — the constructor never opens a network connection.

    Failure modes:
        Constructor never raises; broken configuration is surfaced only when
        the relevant method is called.
    """

    def __init__(
        self,
        agents_dir: str = "agents/core",
        skills_dir: str = "agents/core",
        critics_dir: str = "agents/core/critics",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self.agents_dir = agents_dir
        self.skills_dir = skills_dir
        self.critics_dir = critics_dir
        self.ollama_url = ollama_url

        # Components that are cheap to construct unconditionally.
        self.router = IntelligentRouter()
        self.monitor = ResourceMonitor()

        # Lazily initialised on first use to avoid hitting Ollama at startup.
        self._enforcer: StructuredOutputEnforcer | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_enforcer(self) -> StructuredOutputEnforcer:
        """Return a cached ``StructuredOutputEnforcer``, creating it on demand.

        Inputs:
            None.

        Outputs:
            A ``StructuredOutputEnforcer`` instance configured to talk to the
            Ollama server at ``self.ollama_url``.

        Failure modes:
            Propagates Instructor / OpenAI client construction errors.
        """
        if self._enforcer is None:
            self._enforcer = StructuredOutputEnforcer(
                ollama_base_url=f"{self.ollama_url}/v1"
            )
        return self._enforcer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, recipe_name: str, task: str) -> str:
        """Import and execute a named recipe, returning the final output.

        Inputs:
            recipe_name: Short name of the recipe module, e.g. ``repo_auditor``.
            task: Free-form task description forwarded to the recipe.

        Outputs:
            The string returned by the recipe's ``run`` function.

        Failure modes:
            Returns a user-facing error string when the recipe module cannot be
            imported, when Ollama is unreachable, or when the observer raises
            ``ObserverHaltException``.
        """
        try:
            module = importlib.import_module(f"recipes.{recipe_name}")
        except ModuleNotFoundError:
            return (
                f"Recipe '{recipe_name}' not found. "
                f"Available: {', '.join(self.list_recipes())}"
            )

        try:
            return module.run(task)
        except ObserverHaltException as exc:
            return (
                f"[HALTED] Observer stopped the workflow.\n"
                f"Failure: {exc.verdict.failure_mode}\n"
                f"Recommendation: {exc.verdict.recommendation}"
            )
        except OllamaConnectionError as exc:
            return f"[OLLAMA UNAVAILABLE] {exc}\nRun: ollama serve"
        except Exception as exc:  # pragma: no cover
            return f"[ERROR] Recipe '{recipe_name}' failed: {exc}"

    def list_agents(self) -> list[dict[str, str]]:
        """Return a summary list of all agents found under ``agents_dir``.

        Inputs:
            None.

        Outputs:
            A list of dictionaries with ``name``, ``description``, and
            ``version`` keys.  Returns an empty list when ``agents_dir`` does
            not exist.

        Failure modes:
            Returns an empty list rather than raising when the directory is
            missing.
        """
        try:
            agents: list[AgentDefinition] = load_all_agents(self.agents_dir)
        except FileNotFoundError:
            return []
        return [
            {
                "name": a.name,
                "description": a.description,
                "version": a.version,
            }
            for a in agents
        ]

    def list_recipes(self) -> list[str]:
        """Return the names of all known recipes.

        Inputs:
            None.

        Outputs:
            A list of recipe name strings.

        Failure modes:
            None.
        """
        return list(_KNOWN_RECIPES)

    def check_health(self) -> dict[str, Any]:
        """Probe Ollama and local resources, returning a status dictionary.

        Inputs:
            None.

        Outputs:
            A dictionary with keys:
              - ``ollama`` (bool): whether ``/api/tags`` responded successfully.
              - ``models`` (list[str]): model names reported by Ollama, or ``[]``
                when Ollama is unreachable.
              - ``ram_gb`` (float): available system RAM in gigabytes.
              - ``gpu`` (bool): whether a GPU was detected via pynvml.

        Failure modes:
            Never raises; all probes catch their own exceptions and surface
            failures through the returned dictionary values.
        """
        ollama_ok = False
        available_models: list[str] = []

        try:
            resp = httpx.get(f"{self.ollama_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                ollama_ok = True
                data = resp.json()
                available_models = [
                    m.get("name", "") for m in data.get("models", [])
                ]
        except Exception:
            pass

        try:
            ram_gb = self.monitor.get_available_ram_gb()
        except Exception:
            ram_gb = 0.0

        return {
            "ollama": ollama_ok,
            "models": available_models,
            "ram_gb": round(ram_gb, 1),
            "gpu": self.monitor.has_gpu,
        }

    def run_single_agent(
        self,
        agent_path: str,
        task: str,
        use_critic: bool = True,
    ) -> dict[str, Any]:
        """Load one agent, run structured enforcement, and optionally critique.

        Inputs:
            agent_path: Filesystem path to the agent Markdown file.
            task: User task string forwarded to the agent.
            use_critic: When ``True``, evaluate the output with
                ``ObserverCritic`` after enforcement.

        Outputs:
            A dictionary with:
              - ``output`` (HandoffPayload): the structured enforcement result.
              - ``verdict`` (CriticVerdict | None): critic verdict, or ``None``
                when ``use_critic`` is ``False`` or no critics directory exists.

        Failure modes:
            Propagates ``FileNotFoundError`` when ``agent_path`` is missing.
            Propagates ``OllamaConnectionError`` when Ollama is unreachable.
            Propagates ``ObserverHaltException`` from the critic evaluation.
        """
        agent = load_agent(agent_path)
        enforcer = self._get_enforcer()
        messages = [
            {"role": "system", "content": agent.body},
            {"role": "user", "content": task},
        ]
        handoff: HandoffPayload = enforcer.enforce(HandoffPayload, messages)

        verdict: CriticVerdict | None = None
        if use_critic:
            try:
                from helixos.agents.observer import ObserverCritic

                critic = ObserverCritic(
                    self.critics_dir,
                    enforcer=enforcer,
                )
                verdict = critic.evaluate(task, handoff.task_summary)
            except (FileNotFoundError, ValueError):
                verdict = None

        return {"output": handoff, "verdict": verdict}

    def validate_skill(self, skill_dir: str) -> dict[str, Any]:
        """Verify that a skill folder contains all required files.

        Inputs:
            skill_dir: Path to the skill folder to validate.

        Outputs:
            A dictionary with:
              - ``valid`` (bool): ``True`` when all required files are present.
              - ``errors`` (list[str]): description of each missing requirement.

        Failure modes:
            Never raises; a missing ``skill_dir`` is reported as an error.
        """
        errors: list[str] = []
        skill_path = Path(skill_dir)

        if not skill_path.exists():
            return {
                "valid": False,
                "errors": [f"Skill directory does not exist: {skill_dir}"],
            }

        if not skill_path.is_dir():
            return {
                "valid": False,
                "errors": [f"Path is not a directory: {skill_dir}"],
            }

        for required_file in _REQUIRED_SKILL_FILES:
            if not (skill_path / required_file).is_file():
                errors.append(f"Missing required file: {required_file}")

        return {"valid": len(errors) == 0, "errors": errors}
