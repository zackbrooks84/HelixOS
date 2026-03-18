from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from helixos.agents.semantic_loader import SemanticSkillDiscovery


def _mock_embedding_response(*args: object, **kwargs: object) -> Mock:
    response = Mock()
    response.json.return_value = {"embedding": [0.1] * 128}
    return response


def _write_skill(base_dir: Path, name: str, content: str) -> Path:
    skill_dir = base_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "system_prompt.md").write_text(content, encoding="utf-8")
    return skill_dir


@patch(
    "helixos.agents.semantic_loader.httpx.post",
    side_effect=_mock_embedding_response,
)
def test_indexes_skills_on_init(mock_post: Mock, tmp_path: Path) -> None:
    _write_skill(tmp_path, "security_review", "Security skill prompt")
    _write_skill(tmp_path, "code_review", "Code review skill prompt")

    loader = SemanticSkillDiscovery(
        skills_dir=str(tmp_path),
        chroma_collection_name=f"test_{uuid4().hex}",
        chroma_path=None,
    )
    collection_snapshot = loader.collection.get()

    assert collection_snapshot["ids"] == ["code_review", "security_review"]
    assert len(collection_snapshot["documents"]) == 2
    assert mock_post.call_count == 2


@patch(
    "helixos.agents.semantic_loader.httpx.post",
    side_effect=_mock_embedding_response,
)
def test_get_skills_returns_list(mock_post: Mock, tmp_path: Path) -> None:
    _write_skill(tmp_path, "security_review", "Security skill prompt")
    _write_skill(tmp_path, "code_review", "Code review skill prompt")

    loader = SemanticSkillDiscovery(
        skills_dir=str(tmp_path),
        chroma_collection_name=f"test_{uuid4().hex}",
        min_distance=-1.0,
        chroma_path=None,
    )

    skills = loader.get_skills("Review this code for security issues")

    assert isinstance(skills, list)
    assert skills
    assert all(
        set(skill.keys()) == {"id", "system_prompt", "tools_yaml"}
        for skill in skills
    )
    assert mock_post.call_count == 3


@patch(
    "helixos.agents.semantic_loader.httpx.post",
    side_effect=_mock_embedding_response,
)
def test_get_skills_max_two(mock_post: Mock, tmp_path: Path) -> None:
    _write_skill(tmp_path, "security_review", "Security skill prompt")
    _write_skill(tmp_path, "code_review", "Code review skill prompt")
    _write_skill(tmp_path, "maintainability_review", "Maintainability skill prompt")

    loader = SemanticSkillDiscovery(
        skills_dir=str(tmp_path),
        chroma_collection_name=f"test_{uuid4().hex}",
        min_distance=-1.0,
        chroma_path=None,
    )

    skills = loader.get_skills("Review this codebase", top_k=3)

    assert len(skills) <= 2
    assert mock_post.call_count == 4


@patch(
    "helixos.agents.semantic_loader.httpx.post",
    side_effect=_mock_embedding_response,
)
def test_missing_system_prompt_skipped(mock_post: Mock, tmp_path: Path) -> None:
    _write_skill(tmp_path, "security_review", "Security skill prompt")
    missing_dir = tmp_path / "empty_skill"
    missing_dir.mkdir(parents=True, exist_ok=True)

    loader = SemanticSkillDiscovery(
        skills_dir=str(tmp_path),
        chroma_collection_name=f"test_{uuid4().hex}",
        chroma_path=None,
    )
    collection_snapshot = loader.collection.get()

    assert collection_snapshot["ids"] == ["security_review"]
    assert mock_post.call_count == 1


@patch(
    "helixos.agents.semantic_loader.httpx.post",
    side_effect=_mock_embedding_response,
)
def test_configurable_min_distance(mock_post: Mock, tmp_path: Path) -> None:
    _write_skill(tmp_path, "security_review", "Security skill prompt")
    _write_skill(tmp_path, "code_review", "Code review skill prompt")

    loader = SemanticSkillDiscovery(
        skills_dir=str(tmp_path),
        chroma_collection_name=f"test_{uuid4().hex}",
        min_distance=0.5,
        diversity_penalty=0.05,
        chroma_path=None,
    )

    assert loader.min_distance == 0.5
    assert loader.diversity_penalty == 0.05
    assert mock_post.call_count == 2


@patch(
    "helixos.agents.semantic_loader.httpx.post",
    side_effect=_mock_embedding_response,
)
def test_indexing_filters_none_metadata_values(mock_post: Mock, tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "security_review", "Security skill prompt")
    (skill_dir / "tools.yaml").unlink(missing_ok=True)

    loader = SemanticSkillDiscovery(
        skills_dir=str(tmp_path),
        chroma_collection_name=f"test_{uuid4().hex}",
        chroma_path=None,
    )
    collection_snapshot = loader.collection.get(include=["metadatas"])

    assert collection_snapshot["metadatas"][0] == {
        "system_prompt": "Security skill prompt"
    }
    assert mock_post.call_count == 1
