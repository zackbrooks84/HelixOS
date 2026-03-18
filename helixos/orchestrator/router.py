"""Role-based local model router for HelixOS agents."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from helixos.agents.loader import AgentDefinition


class IntelligentRouter:
    """Select default local models for agents based on role keywords.

    Inputs:
        config_path: Optional YAML path overriding the default role mapping.

    Outputs:
        A router instance with a parsed ``role_map`` dictionary.

    Failure modes:
        Raises ``ValueError`` when the selected configuration file does not
        contain a ``roles`` mapping.
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Load the model-role mapping from disk or packaged defaults.

        Inputs:
            config_path: Optional path to a YAML file. When omitted, the router
                checks ``~/.helixos/models/config.yaml`` and falls back to the
                packaged ``helixos/defaults/models.yaml`` file.

        Outputs:
            None.

        Failure modes:
            Raises ``ValueError`` if the YAML cannot be parsed into a ``roles``
            mapping.
        """

        resolved_path = (
            Path(config_path)
            if config_path is not None
            else Path.home() / ".helixos" / "models" / "config.yaml"
        )

        if resolved_path.exists():
            config_data = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
        else:
            default_text = resources.files("helixos.defaults").joinpath("models.yaml").read_text(encoding="utf-8")
            config_data = yaml.safe_load(default_text) or {}

        roles = config_data.get("roles")
        if not isinstance(roles, dict) or not roles:
            raise ValueError("Model configuration must define a non-empty roles mapping")

        self.role_map: dict[str, str] = {str(key): str(value) for key, value in roles.items()}

    def get_model(self, agent: AgentDefinition) -> str:
        """Return the preferred model for an agent definition.

        Inputs:
            agent: Agent definition whose name and description are inspected.

        Outputs:
            The model string selected for the matched role.

        Failure modes:
            Raises ``KeyError`` if the loaded configuration lacks a ``default``
            entry.
        """

        haystack = f"{agent.name} {agent.description}".lower()
        role = "default"

        keyword_roles = (
            (("code", "review", "reviewer"), "coding"),
            (("security", "audit", "vulnerability"), "security"),
            (("frontend", "ui", "css", "html"), "creative"),
            (("research", "analyst", "report"), "research"),
        )
        for keywords, candidate_role in keyword_roles:
            if any(keyword in haystack for keyword in keywords):
                role = candidate_role
                break

        return self.role_map.get(role, self.role_map["default"])

    def suggest_from_ollama(self, available_models: list[str]) -> dict[str, str]:
        """Suggest the best available model for each configured role.

        Inputs:
            available_models: Model identifiers reported by the local runtime.

        Outputs:
            A dictionary mapping each role in ``role_map`` to the preferred or
            best matching available model string.

        Failure modes:
            Returns configured model names unchanged when no substitute match is
            found for a role.
        """

        suggestions: dict[str, str] = {}
        normalized_models = {model.lower(): model for model in available_models}

        for role, preferred_model in self.role_map.items():
            preferred_lower = preferred_model.lower()
            if preferred_lower in normalized_models:
                suggestions[role] = normalized_models[preferred_lower]
                continue

            search_terms = [role] + [part for part in preferred_lower.replace("-", ":").split(":") if part]
            substitute = next(
                (
                    model
                    for model in available_models
                    if any(term in model.lower() for term in search_terms)
                ),
                available_models[0] if available_models else preferred_model,
            )
            suggestions[role] = substitute

        return suggestions
