"""Markdown agent definition loading utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml


FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(?P<frontmatter>.*?)\n---\s*\n?(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass
class AgentDefinition:
    """Represent a HelixOS agent loaded from Markdown frontmatter.

    Inputs:
        name: Human-readable agent name.
        description: Short summary of the agent's role.
        version: Schema or content version string.
        tools: Tool identifiers available to the agent.
        handoffs: Agent names that may receive handoffs.
        skills: Semantic skill discovery configuration entries.
        structured_output_schema: Structured output binding name.
        body: Markdown body after the YAML frontmatter.

    Outputs:
        A dataclass instance that can be consumed by the orchestrator.

    Failure modes:
        This dataclass does not raise on its own, but loader helpers raise
        ``ValueError`` when required fields are missing or the file format is
        invalid.
    """

    name: str
    description: str
    version: str
    tools: list[str] = field(default_factory=list)
    handoffs: list[str] = field(default_factory=list)
    skills: list[dict] = field(default_factory=list)
    structured_output_schema: str = ""
    body: str = ""


def load_agent(path: str) -> AgentDefinition:
    """Load a single Markdown agent definition from disk.

    Inputs:
        path: Filesystem path to an agent Markdown file with YAML frontmatter.

    Outputs:
        A populated ``AgentDefinition`` instance.

    Failure modes:
        Raises ``FileNotFoundError`` if ``path`` does not exist.
        Raises ``ValueError`` if the file is missing frontmatter, contains
        invalid YAML, or omits a required ``name``, ``description``, or
        ``version`` field.
    """

    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(content)
    if match is None:
        raise ValueError(
            f"Agent file {path} missing required frontmatter delimiters"
        )

    try:
        frontmatter = yaml.safe_load(match.group("frontmatter")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Agent file {path} contains invalid YAML frontmatter") from exc

    for required_field in ("name", "description", "version"):
        if not frontmatter.get(required_field):
            raise ValueError(
                f"Agent file {path} missing required field: {required_field}"
            )

    tools = frontmatter.get("tools") or []
    handoffs = frontmatter.get("handoffs") or []
    skills = frontmatter.get("skills") or []

    return AgentDefinition(
        name=str(frontmatter["name"]),
        description=str(frontmatter["description"]),
        version=str(frontmatter["version"]),
        tools=list(tools),
        handoffs=list(handoffs),
        skills=list(skills),
        structured_output_schema=str(
            frontmatter.get("structured_output_schema") or ""
        ),
        body=match.group("body").strip(),
    )


def load_all_agents(agents_dir: str) -> list[AgentDefinition]:
    """Load every valid agent definition beneath a directory tree.

    Inputs:
        agents_dir: Root directory to search for Markdown agent definitions.

    Outputs:
        A list of successfully loaded ``AgentDefinition`` objects sorted by
        path name.

    Failure modes:
        Raises ``FileNotFoundError`` if ``agents_dir`` does not exist.
        Skips Markdown files that are not agent definitions because they lack
        valid HelixOS frontmatter.
    """

    root_dir = Path(agents_dir)
    if not root_dir.exists():
        raise FileNotFoundError(f"Agents directory does not exist: {agents_dir}")

    agents: list[AgentDefinition] = []
    for markdown_path in sorted(root_dir.rglob("*.md")):
        try:
            agents.append(load_agent(str(markdown_path)))
        except ValueError:
            continue
    return agents
