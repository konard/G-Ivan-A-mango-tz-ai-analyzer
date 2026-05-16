"""Tests for vector-store path resolution and the ChromaDB retriever wrapper.

Issue #73 requires:
1. ``persist_directory`` is read from ``configs/embedding_config.yaml`` and
   falls back to ``./chroma_data`` when missing.
2. The retriever encodes the query and calls ChromaDB with ``query_embeddings``
   so the 384-dim built-in embedding function is not used on a 1024-dim
   collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.retriever import (  # noqa: E402
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_VECTOR_STORE_DIR,
    ChromaRetriever,
    load_embedding_config,
    resolve_collection_name,
    resolve_embedding_model_name,
    resolve_vector_store_path,
)


def test_resolve_vector_store_path_reads_config() -> None:
    config = {"vector_store": {"persist_directory": "./chroma_data"}}
    path = resolve_vector_store_path(config)
    assert path == Path("./chroma_data")


def test_resolve_vector_store_path_anchors_relative_path_at_project_root(
    tmp_path: Path,
) -> None:
    config = {"vector_store": {"persist_directory": "./chroma_data"}}
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "chroma_data").mkdir()
    path = resolve_vector_store_path(config, project_root=project_root)
    assert path == (project_root / "chroma_data").resolve()


def test_resolve_vector_store_path_falls_back_to_default(tmp_path: Path) -> None:
    """Missing/empty config → ``./chroma_data`` is used."""
    assert resolve_vector_store_path({}) == Path(DEFAULT_VECTOR_STORE_DIR)
    assert resolve_vector_store_path({"vector_store": {}}) == Path(
        DEFAULT_VECTOR_STORE_DIR
    )
    assert resolve_vector_store_path({"vector_store": None}) == Path(
        DEFAULT_VECTOR_STORE_DIR
    )


def test_resolve_collection_name_default() -> None:
    assert resolve_collection_name({}) == DEFAULT_COLLECTION_NAME
    assert (
        resolve_collection_name({"vector_store": {"collection_name": "custom_kb"}})
        == "custom_kb"
    )


def test_resolve_embedding_model_name_default() -> None:
    assert resolve_embedding_model_name({}) == DEFAULT_EMBEDDING_MODEL
    assert (
        resolve_embedding_model_name({"model_name": "intfloat/multilingual-e5-base"})
        == "intfloat/multilingual-e5-base"
    )


def test_load_embedding_config_uses_real_yaml() -> None:
    """The repository config exposes the canonical persist_directory."""
    config = load_embedding_config("configs/embedding_config.yaml")
    assert config.get("vector_store", {}).get("persist_directory") == "./chroma_data"
    assert config.get("model_name") == "BAAI/bge-m3"


class _StubCollection:
    def __init__(self, payload):
        self.payload = payload
        self.received: dict = {}

    def query(self, *, query_embeddings, n_results, include):
        self.received = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": include,
        }
        return self.payload


class _StubClient:
    def __init__(self, collection):
        self._collection = collection
        self.requested_collections: list = []

    def get_or_create_collection(self, *, name: str):
        self.requested_collections.append(name)
        return self._collection


def test_chroma_retriever_uses_query_embeddings_not_query_texts() -> None:
    """Bypasses ChromaDB's default 384-dim embedder by sending query_embeddings."""
    payload = {
        "documents": [["chunk A", "chunk B"]],
        "metadatas": [[{"source": "doc.pdf", "chunk_idx": 0}, {"source": "doc.pdf", "chunk_idx": 1}]],
        "distances": [[0.42, 1.7]],
    }
    stub_collection = _StubCollection(payload)
    stub_client = _StubClient(stub_collection)

    captured_queries: list = []

    def fake_embedder(text: str):
        captured_queries.append(text)
        # Pretend this is a 1024-dim bge-m3 vector — only the length matters.
        return [0.1] * 1024

    retriever = ChromaRetriever(
        config={
            "model_name": "BAAI/bge-m3",
            "normalize_embeddings": True,
            "vector_store": {
                "persist_directory": "./chroma_data",
                "collection_name": "clarify_engine_kb",
            },
        },
        embedder=fake_embedder,
        client_factory=lambda path: stub_client,
    )

    chunks = retriever.search("как настроить SIP?", top_k=2)

    assert captured_queries == ["как настроить SIP?"]
    assert "query_embeddings" in stub_collection.received
    assert len(stub_collection.received["query_embeddings"]) == 1
    assert len(stub_collection.received["query_embeddings"][0]) == 1024
    assert stub_collection.received["n_results"] == 2
    assert stub_client.requested_collections == ["clarify_engine_kb"]

    assert len(chunks) == 2
    assert chunks[0]["source"] == "doc.pdf"
    assert chunks[0]["chunk_idx"] == 0
    assert chunks[0]["distance"] == pytest.approx(0.42)
    assert chunks[0]["similarity"] == pytest.approx(1.0 / (1.0 + 0.42))


def test_chroma_retriever_empty_query_returns_empty() -> None:
    retriever = ChromaRetriever(
        config={},
        embedder=lambda text: [0.0],
        client_factory=lambda path: _StubClient(_StubCollection({})),
    )
    assert retriever.search("") == []
    assert retriever.search("   ") == []


def test_chroma_retriever_falls_back_to_default_persist_dir(tmp_path: Path) -> None:
    """Missing config → persist_directory resolves to ./chroma_data."""
    retriever = ChromaRetriever(
        config={},
        embedder=lambda text: [0.0],
        client_factory=lambda path: _StubClient(_StubCollection({})),
    )
    assert retriever.persist_directory == Path(DEFAULT_VECTOR_STORE_DIR)
    assert retriever.collection_name == DEFAULT_COLLECTION_NAME
    assert retriever.model_name == DEFAULT_EMBEDDING_MODEL
