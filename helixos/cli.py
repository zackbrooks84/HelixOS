"""Click-based command line interface for HelixOS."""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from pathlib import Path

import click

from helixos.exceptions import ObserverHaltException
from helixos.orchestrator.router import IntelligentRouter


@click.group()
def cli() -> None:
    """Run the HelixOS CLI command group.

    Inputs:
        None.

    Outputs:
        None.

    Failure modes:
        Delegates failures to subcommands.
    """
    pass


@cli.command()
@click.option("--with-sandbox", is_flag=True, default=False)
def init(with_sandbox: bool) -> None:
    """Initialize local HelixOS directories and runtime integrations.

    Inputs:
        with_sandbox: Whether to print the Docker sandbox follow-up guidance.

    Outputs:
        None. Writes initialization status to stdout.

    Failure modes:
        Exits with status code 1 if ChromaDB initialization fails.
    """
    home = Path.home()
    helixos_root = home / ".helixos"
    agents_dir = helixos_root / "agents"
    models_dir = helixos_root / "models"
    chroma_dir = helixos_root / "chroma"

    for directory in (agents_dir, models_dir, chroma_dir):
        directory.mkdir(parents=True, exist_ok=True)

    default_models = Path(__file__).resolve().parent / "defaults" / "models.yaml"
    user_models = models_dir / "config.yaml"
    if not user_models.exists():
        shutil.copy2(default_models, user_models)

    source_agents_dir = Path.cwd() / "agents" / "core"
    if source_agents_dir.exists():
        for item in source_agents_dir.iterdir():
            destination = agents_dir / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)

    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(chroma_dir))
        client.get_or_create_collection(name="helixos_skills")
        click.echo("ChromaDB initialized at ~/.helixos/chroma/ [OK]")
    except Exception as exc:  # pragma: no cover - exercised in CLI tests
        click.echo(f"ERROR: ChromaDB failed to initialize: {exc}")
        click.echo("Skill discovery will not work. Re-run helixos init.")
        raise SystemExit(1) from exc

    try:
        ollama_result = subprocess.run(
            ["ollama", "list"],
            check=True,
            capture_output=True,
            text=True,
        )
        model_names = _parse_ollama_models(ollama_result.stdout)
        suggestions = IntelligentRouter().suggest_from_ollama(model_names)
        _print_model_suggestions(suggestions)
    except Exception:
        click.echo("Ollama not detected. Run: ollama serve")
        click.echo("Then run: helixos init again to detect models.")

    click.echo("")
    click.echo("HelixOS initialized.")
    click.echo("Run: helixos run repo_auditor")
    click.echo("Launch UI: helixos ui")
    click.echo("")
    click.echo("SANDBOX WARNING: The default sandbox (RestrictedPython)")
    click.echo("prevents accidental bad code but does NOT protect against")
    click.echo("network access, file system access outside the working")
    click.echo("directory, or adversarial inputs.")
    click.echo("If your agents touch real files or real APIs, run:")
    click.echo("  helixos init --with-sandbox")

    if with_sandbox:
        docker_available = shutil.which("docker") is not None
        sandbox_config = helixos_root / "sandbox.json"
        sandbox_config.write_text(
            json.dumps(
                {
                    "provider": "docker",
                    "enabled": docker_available,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        click.echo("")
        if docker_available:
            click.echo("Docker sandbox configured and enabled.")
        else:
            click.echo("Docker sandbox requested, but Docker is not installed.")
            click.echo("Install Docker Desktop, then re-run helixos init --with-sandbox.")


@cli.command()
@click.argument("skill_path")
def validate(skill_path: str) -> None:
    """Validate that a skill directory matches the required blueprint shape.

    Inputs:
        skill_path: Path to a candidate skill directory.

    Outputs:
        None. Writes validation results to stdout.

    Failure modes:
        Exits with status code 1 if required files are missing.
    """
    path = Path(skill_path)
    missing: list[str] = []

    if not (path / "system_prompt.md").exists():
        missing.append("system_prompt.md")
    if not (path / "test_cases").is_dir():
        missing.append("test_cases")

    if not missing:
        click.echo(f"PASS: skill at {skill_path} is valid.")
        return

    click.echo(f"FAIL: missing {', '.join(missing)}.")
    raise SystemExit(1)


@cli.command("new-skill")
@click.argument("skill_name")
def new_skill(skill_name: str) -> None:
    """Create a new skill scaffold in the current working directory.

    Inputs:
        skill_name: New skill folder name.

    Outputs:
        None. Writes scaffold files to disk and prints next steps.

    Failure modes:
        Propagates filesystem errors if directories or files cannot be created.
    """
    skill_root = Path.cwd() / "skills" / skill_name
    examples_dir = skill_root / "examples"
    test_cases_dir = skill_root / "test_cases"

    examples_dir.mkdir(parents=True, exist_ok=True)
    test_cases_dir.mkdir(parents=True, exist_ok=True)

    (skill_root / "system_prompt.md").write_text(
        "# {skill_name}\n"
        "You are now operating in {skill_name} mode.\n"
        "[Describe what this skill focuses on.]\n"
        "[List the specific checks or actions this skill performs.]\n"
        "[Define what outputs this skill should produce.]\n"
        "Output only findings and recommendations.\n".format(skill_name=skill_name),
        encoding="utf-8",
    )
    (examples_dir / "example_1.json").write_text(
        '{"input": "", "output": ""}',
        encoding="utf-8",
    )
    (test_cases_dir / "basic_test.yaml").write_text(
        "input: [describe your test input here]",
        encoding="utf-8",
    )
    (skill_root / "metadata.yaml").write_text("priority: 0.8", encoding="utf-8")

    click.echo(f"Skill scaffold created at skills/{skill_name}/")
    click.echo("Next: edit system_prompt.md to define what this skill does.")
    click.echo(f"Then run: helixos validate ./skills/{skill_name}")


@cli.command()
@click.argument("recipe_name")
def run(recipe_name: str) -> None:
    """Run a built-in HelixOS recipe module by name.

    Inputs:
        recipe_name: Module name under the ``recipes`` package.

    Outputs:
        None. Prints status messages and the recipe result.

    Failure modes:
        Prints a not-found message if the recipe module is unavailable.
        Prints observer halt guidance when ``ObserverHaltException`` is raised.
    """
    click.echo(f"Running recipe: {recipe_name}...")
    try:
        recipe_module = importlib.import_module(f"recipes.{recipe_name}")
    except ModuleNotFoundError:
        click.echo(f"Recipe not found: {recipe_name}")
        click.echo(
            "Available recipes: repo_auditor, frontend_builder, research_report"
        )
        return

    try:
        result = recipe_module.run()
    except ObserverHaltException as exc:
        click.echo(f"OBSERVER HALTED: {exc}")
        click.echo("Use the UI (helixos ui) to Approve or Reject.")
        return

    click.echo(str(result))


@cli.command()
def ui() -> None:
    """Launch the HelixOS canvas UI.

    Inputs:
        None.

    Outputs:
        None. Prints launch status and dispatches to the UI launcher.

    Failure modes:
        Propagates import or launch failures from ``helixos.ui.canvas``.
    """
    click.echo("Launching HelixOS UI...")
    from helixos.ui.canvas import launch

    launch()


def _parse_ollama_models(output: str) -> list[str]:
    """Parse ``ollama list`` output into model names.

    Inputs:
        output: Raw stdout emitted by ``ollama list``.

    Outputs:
        A list of model name strings, excluding the header row.

    Failure modes:
        Returns an empty list if stdout contains no parseable model rows.
    """
    model_names: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("name"):
            continue
        model_names.append(stripped.split()[0])
    return model_names


def _print_model_suggestions(suggestions: dict[str, str]) -> None:
    """Print model suggestions in a simple readable table.

    Inputs:
        suggestions: Mapping of HelixOS roles to suggested local model names.

    Outputs:
        None. Writes a table to stdout.

    Failure modes:
        None.
    """
    if not suggestions:
        return

    click.echo("")
    click.echo("Suggested model routing:")
    click.echo("ROLE       MODEL")
    for role, model in suggestions.items():
        click.echo(f"{role:<10} {model}")


if __name__ == "__main__":
    cli(prog_name="helixos")
