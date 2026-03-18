"""Semantic skill discovery backed by ChromaDB and Ollama embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
import httpx


class SemanticSkillDiscovery:
    """Index and retrieve skill prompts using ChromaDB cosine similarity.

    Inputs:
        skills_dir: Root directory that contains skill subfolders.
        chroma_collection_name: Collection name used for indexed skill vectors.
        min_distance: Minimum cosine distance threshold for returned matches.
        diversity_penalty: Similarity threshold modifier used to suppress near-
            duplicate results.
        chroma_path: Optional persistent ChromaDB path. When omitted, an
            in-memory EphemeralClient is used.

    Outputs:
        An initialized discovery instance with indexed skills available through
        ``get_skills``.

    Failure modes:
        Raises ``FileNotFoundError`` if ``skills_dir`` does not exist.
        Propagates ``httpx`` request errors if Ollama embedding generation
        fails during initialization or querying.
        Propagates ChromaDB errors if the collection cannot be created or
        queried.
    """

    def __init__(
        self,
        skills_dir: str,
        chroma_collection_name: str = "helixos_skills",
        min_distance: float = 0.25,
        diversity_penalty: float = 0.15,
        chroma_path: str | None = None,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        if not self.skills_dir.exists():
            raise FileNotFoundError(
                f"Skills directory does not exist: {self.skills_dir}"
            )

        self.min_distance = min_distance
        self.diversity_penalty = diversity_penalty
        self.client = (
            chromadb.EphemeralClient()
            if chroma_path is None
            else chromadb.PersistentClient(path=chroma_path)
        )
        self.collection = self.client.get_or_create_collection(
            name=chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._index_skills()

    def get_skills(self, context: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Return the top surviving semantic skill matches for a context.

        Inputs:
            context: Free-form task context to embed and search against.
            top_k: Number of nearest results to request from ChromaDB before
                post-processing.

        Outputs:
            Up to two dictionaries with ``id``, ``system_prompt``, and
            ``tools_yaml`` keys.

        Failure modes:
            Propagates ``httpx`` request errors if Ollama embedding generation
            fails.
            Propagates ChromaDB errors if querying fails.
        """
        query_embedding = self._embed_text(context)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["distances", "metadatas"],
        )

        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        ranked_results: list[dict[str, Any]] = []
        for skill_id, distance, metadata in zip(ids, distances, metadatas):
            if distance is None or distance < self.min_distance:
                continue
            ranked_results.append(
                {
                    "id": skill_id,
                    "distance": float(distance),
                    "system_prompt": metadata["system_prompt"],
                    "tools_yaml": metadata.get("tools_yaml"),
                }
            )

        surviving_results: list[dict[str, Any]] = []
        similarity_cutoff = 1 - self.diversity_penalty
        for candidate in ranked_results:
            candidate_similarity = 1 - candidate["distance"]
            if any(
                candidate_similarity > similarity_cutoff
                and abs(candidate_similarity - (1 - kept["distance"]))
                < 1e-12
                for kept in surviving_results
            ):
                continue
            surviving_results.append(candidate)

        return [
            {
                "id": item["id"],
                "system_prompt": item["system_prompt"],
                "tools_yaml": item["tools_yaml"],
            }
            for item in surviving_results[:2]
        ]

    def _index_skills(self) -> None:
        """Walk the skills tree and index each skill folder with a prompt.

        Inputs:
            None.

        Outputs:
            None. Indexed skills are written to the configured ChromaDB
            collection.

        Failure modes:
            Propagates ``httpx`` request errors if Ollama embedding generation
            fails for a discovered skill.
            Propagates ChromaDB errors if upserting fails.
        """
        skill_dirs = sorted(
            path for path in self.skills_dir.rglob("*") if path.is_dir()
        )
        for subfolder in skill_dirs:
            system_prompt_path = subfolder / "system_prompt.md"
            if not system_prompt_path.is_file():
                continue

            system_prompt = system_prompt_path.read_text(encoding="utf-8")
            embedding = self._embed_text(system_prompt)
            tools_yaml_path = subfolder / "tools.yaml"
            metadata = self._sanitize_metadata(
                {
                    "system_prompt": system_prompt,
                    "tools_yaml": (
                        str(tools_yaml_path) if tools_yaml_path.is_file() else None
                    ),
                }
            )
            self.collection.upsert(
                ids=[subfolder.name],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[system_prompt],
            )

    def _sanitize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Remove unsupported Chroma metadata values before persistence.

        Inputs:
            metadata: Metadata dictionary assembled for a skill record.

        Outputs:
            A new dictionary containing only Chroma-compatible values of type
            ``str``, ``int``, ``float``, or ``bool``.

        Failure modes:
            None. Unsupported keys are dropped instead of raising.
        """
        allowed_types = (str, int, float, bool)
        return {
            key: value
            for key, value in metadata.items()
            if isinstance(value, allowed_types)
        }

    def _embed_text(self, text: str) -> list[float]:
        """Generate an embedding from Ollama's nomic-embed-text model.

        Inputs:
            text: The raw text to embed.

        Outputs:
            A list of float embedding values.

        Failure modes:
            Propagates ``httpx`` request errors if Ollama is unavailable.
            Raises ``ValueError`` if the Ollama response does not contain an
            ``embedding`` payload.
        """
        response = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
        )
        payload = response.json()
        embedding = payload.get("embedding")
        if embedding is None:
            raise ValueError("Ollama embedding response did not include 'embedding'.")
        return embedding
