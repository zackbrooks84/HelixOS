from __future__ import annotations

from helixos.agents.loader import AgentDefinition
from helixos.orchestrator.router import IntelligentRouter


def test_code_reviewer_routes_to_coding_model() -> None:
    router = IntelligentRouter()
    agent = AgentDefinition(
        name="Code Reviewer",
        description="Reviews code for defects.",
        version="1.0",
    )

    assert router.get_model(agent) == router.role_map["coding"]


def test_security_auditor_routes_to_security_model() -> None:
    router = IntelligentRouter()
    agent = AgentDefinition(
        name="Security Auditor",
        description="Performs vulnerability audits.",
        version="1.0",
    )

    assert router.get_model(agent) == router.role_map["security"]


def test_unknown_agent_routes_to_default() -> None:
    router = IntelligentRouter()
    agent = AgentDefinition(
        name="Workflow Helper",
        description="Coordinates tasks.",
        version="1.0",
    )

    assert router.get_model(agent) == router.role_map["default"]


def test_suggest_from_ollama_returns_dict() -> None:
    router = IntelligentRouter()

    suggestions = router.suggest_from_ollama(["qwen2.5:7b"])

    assert isinstance(suggestions, dict)
