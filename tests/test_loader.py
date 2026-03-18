from __future__ import annotations

import re
from pathlib import Path

import pytest

from helixos.agents.loader import AgentDefinition, load_agent, load_all_agents


def test_load_agent_returns_agent_definition() -> None:
    agent = load_agent("agents/core/code_reviewer.md")

    assert isinstance(agent, AgentDefinition)
    assert agent.name == "Code Reviewer"
    assert agent.version == "1.0"


def test_load_agent_body_populated() -> None:
    agent = load_agent("agents/core/security_auditor.md")

    assert isinstance(agent.body, str)
    assert agent.body.strip()


def test_load_all_agents_finds_five() -> None:
    agents = load_all_agents("agents/core/")

    assert len(agents) == 5


def test_load_agent_missing_name_raises(tmp_path: Path) -> None:
    agent_path = tmp_path / "missing_name.md"
    agent_path.write_text(
        "---\ndescription: Missing name\nversion: '1.0'\n---\n## Body\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=(
            rf"Agent file {re.escape(str(agent_path))} missing required field: name"
        ),
    ):
        load_agent(str(agent_path))


def test_handoffs_is_list() -> None:
    agent = load_agent("agents/core/frontend_builder.md")

    assert isinstance(agent.handoffs, list)
    assert agent.handoffs == ["Code Reviewer"]
