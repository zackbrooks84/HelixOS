from __future__ import annotations

from pathlib import Path
import subprocess

import pytest
from click.testing import CliRunner

from helixos.cli import cli


@pytest.fixture()
def runner() -> CliRunner:
    """Provide a CLI runner for command invocation tests."""
    return CliRunner()


@pytest.fixture()
def mock_init_dependencies(mocker: pytest.MockFixture) -> None:
    """Mock filesystem and Chroma dependencies for init command tests."""
    mocker.patch("helixos.cli.shutil.copy2")
    mocker.patch("helixos.cli.shutil.copytree")
    mocker.patch("helixos.cli.Path.home", return_value=Path("/tmp/test-home"))
    mocker.patch("helixos.cli.Path.exists", return_value=False)
    collection = mocker.Mock()
    client = mocker.Mock()
    client.get_or_create_collection.return_value = collection
    mocker.patch("helixos.cli.chromadb.PersistentClient", return_value=client)



def test_init_creates_helixos_dir(
    runner: CliRunner, mocker: pytest.MockFixture, mock_init_dependencies: None
) -> None:
    """Init should attempt to create the HelixOS home directory structure."""
    mkdir_mock = mocker.patch("helixos.cli.Path.mkdir", autospec=True)
    mocker.patch(
        "helixos.cli.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["ollama", "list"],
            returncode=0,
            stdout="NAME ID SIZE\nqwen2.5:7b abc 1 GB\n",
            stderr="",
        ),
    )
    mocker.patch(
        "helixos.cli.IntelligentRouter.suggest_from_ollama",
        return_value={"coding": "qwen2.5:7b"},
    )

    result = runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    created_dirs = [Path(call.args[0]) for call in mkdir_mock.call_args_list]
    assert Path("/tmp/test-home/.helixos/agents") in created_dirs
    assert Path("/tmp/test-home/.helixos/models") in created_dirs
    assert Path("/tmp/test-home/.helixos/chroma") in created_dirs



def test_init_handles_ollama_not_running(
    runner: CliRunner, mocker: pytest.MockFixture, mock_init_dependencies: None
) -> None:
    """Init should print the Ollama guidance when ollama is unavailable."""
    mocker.patch("helixos.cli.subprocess.run", side_effect=FileNotFoundError())
    mocker.patch("helixos.cli.Path.mkdir")

    result = runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    assert "Ollama not detected" in result.output



def test_init_chroma_failure_exits_with_error(
    runner: CliRunner, mocker: pytest.MockFixture
) -> None:
    """Init should stop immediately when ChromaDB initialization fails."""
    mocker.patch("helixos.cli.Path.home", return_value=Path("/tmp/test-home"))
    mocker.patch("helixos.cli.Path.mkdir")
    mocker.patch("helixos.cli.Path.exists", return_value=False)
    mocker.patch("helixos.cli.shutil.copy2")
    mocker.patch(
        "helixos.cli.chromadb.PersistentClient", side_effect=Exception("disk error")
    )

    result = runner.invoke(cli, ["init"])

    assert result.exit_code == 1
    assert "ERROR: ChromaDB failed to initialize" in result.output



def test_init_prints_sandbox_warning(
    runner: CliRunner, mocker: pytest.MockFixture, mock_init_dependencies: None
) -> None:
    """Init should always print the Section 7 sandbox warning block."""
    mocker.patch("helixos.cli.subprocess.run", side_effect=FileNotFoundError())
    mocker.patch("helixos.cli.Path.mkdir")

    result = runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    assert "SANDBOX WARNING" in result.output



def test_validate_pass(runner: CliRunner, tmp_path: Path) -> None:
    """Validate should pass when required skill files are present."""
    (tmp_path / "system_prompt.md").write_text("# test", encoding="utf-8")
    (tmp_path / "test_cases").mkdir()

    result = runner.invoke(cli, ["validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "PASS" in result.output



def test_validate_fail_missing_files(runner: CliRunner, tmp_path: Path) -> None:
    """Validate should fail when the test_cases directory is missing."""
    (tmp_path / "system_prompt.md").write_text("# test", encoding="utf-8")

    result = runner.invoke(cli, ["validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "test_cases" in result.output



def test_run_unknown_recipe(runner: CliRunner) -> None:
    """Run should print the built-in recipe list for unknown recipes."""
    result = runner.invoke(cli, ["run", "nonexistent"])

    assert result.exit_code == 0
    assert "Recipe not found" in result.output



def test_new_skill_creates_scaffold(runner: CliRunner, tmp_path: Path) -> None:
    """New-skill should create the expected scaffold files in cwd."""
    with runner.isolated_filesystem(temp_dir=str(tmp_path)):
        result = runner.invoke(cli, ["new-skill", "my_test_skill"], catch_exceptions=False)
        skill_root = Path("skills") / "my_test_skill"
        assert (skill_root / "system_prompt.md").exists()
        assert (skill_root / "test_cases" / "basic_test.yaml").exists()
        assert "Skill scaffold created" in result.output
