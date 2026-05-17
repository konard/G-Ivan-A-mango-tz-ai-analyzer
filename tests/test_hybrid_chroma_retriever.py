"""Tests for BL-01 production hybrid retriever (issue #87).

``HybridChromaRetriever`` is the retrieval entry point used by the Streamlit
UI. It combines BM25 lexical recall with bge-m3 dense recall over the
persistent ChromaDB collection and fuses the two ranked lists with RRF
(k=60).

These tests use a fake Chroma client + a deterministic hash embedder so the
retriever exercises its full code path without requiring the real ML stack
or a populated ``./chroma_data`` directory.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.retriever import (  # noqa: E402
    HybridChromaRetriever,
    _hash_embedding,
)


# ----------------------------------------------------- Fake Chroma in-memory --
class _FakeCollection:
    def __init__(self, embedder) -> None:
        self.embedder = embedder
        self._ids: List[str] = []
        self._documents: List[str] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._embeddings: List[Sequence[float]] = []

    def add(self, *, ids, documents, metadatas, embeddings=None):
        self._ids.extend(ids)
        self._documents.extend(documents)
        self._metadatas.extend(metadatas)
        if embeddings is None:
            embeddings = [self.embedder(doc) for doc in documents]
        self._embeddings.extend(embeddings)

    def get(self, *, include=None):
        return {
            "ids": list(self._ids),
            "documents": list(self._documents),
            "metadatas": list(self._metadatas),
        }

    def query(self, *, query_embeddings, n_results, include=None):
        q = query_embeddings[0]

        def _dist(vec: Sequence[float]) -> float:
            return sum((a - b) ** 2 for a, b in zip(q, vec)) ** 0.5

        ranked = sorted(range(len(self._documents)), key=lambda i: _dist(self._embeddings[i]))
        top = ranked[:n_results]
        return {
            "ids": [[self._ids[i] for i in top]],
            "documents": [[self._documents[i] for i in top]],
            "metadatas": [[self._metadatas[i] for i in top]],
            "distances": [[_dist(self._embeddings[i]) for i in top]],
        }


class _FakeClient:
    def __init__(self, embedder) -> None:
        self.embedder = embedder
        self._collections: Dict[str, _FakeCollection] = {}

    def get_or_create_collection(self, *, name: str) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection(self.embedder)
        return self._collections[name]


def _retriever_with_docs(docs: List[Dict[str, Any]], top_k: int = 3) -> HybridChromaRetriever:
    client = _FakeClient(_hash_embedding)
    config = {
        "top_k": top_k,
        "rrf_k": 60,
        "vector_store": {"collection_name": "kb_test"},
    }
    retriever = HybridChromaRetriever(
        config=config,
        embedder=_hash_embedding,
        client_factory=lambda _path: client,
    )
    collection = client.get_or_create_collection(name="kb_test")
    for idx, doc in enumerate(docs):
        collection.add(
            ids=[f"{doc['source']}__{idx}"],
            documents=[doc["text"]],
            metadatas=[{"source": doc["source"], "chunk_idx": idx, **doc.get("metadata", {})}],
            embeddings=[_hash_embedding(doc["text"])],
        )
    return retriever


SAMPLE_DOCS = [
    {
        "text": "Внутренняя CRM поддерживает коннектор Битрикс24 с синхронизацией контактов через REST API.",
        "source": "crm.md",
        "metadata": {"section": "Раздел 4.2"},
    },
    {
        "text": "Запись звонков и расшифровка STT доступны в постобработке.",
        "source": "ai.md",
        "metadata": {"section": "Раздел 3.1"},
    },
    {
        "text": "Поддерживаются протоколы интеграции: REST API, SOAP, Webhooks, SFTP.",
        "source": "integration.md",
        "metadata": {"section": "Раздел 5"},
    },
]


def test_hybrid_chroma_returns_unified_chunks() -> None:
    retriever = _retriever_with_docs(SAMPLE_DOCS, top_k=2)
    results = retriever.search("Битрикс24 синхронизация контактов", top_k=2)
    assert results, "Hybrid retriever returned no results"
    assert len(results) <= 2
    top = results[0]
    for key in ("text", "source", "chunk_idx", "score", "metadata", "similarity"):
        assert key in top, f"Missing key {key} in hybrid result"
    assert top["source"] == "crm.md"
    assert isinstance(top["score"], float)
    assert top["score"] > 0


def test_hybrid_chroma_bm25_lexical_hit_survives_fusion() -> None:
    """BM25 must contribute: a rare token hit ranks the right doc even when dense is noisy."""
    retriever = _retriever_with_docs(SAMPLE_DOCS, top_k=3)
    results = retriever.search("SOAP", top_k=3)
    sources = [r["source"] for r in results]
    assert "integration.md" in sources


def test_hybrid_chroma_empty_query_returns_empty() -> None:
    retriever = _retriever_with_docs(SAMPLE_DOCS)
    assert retriever.search("") == []
    assert retriever.search("   ") == []


def test_hybrid_chroma_empty_collection_returns_empty() -> None:
    retriever = _retriever_with_docs([], top_k=3)
    assert retriever.search("anything") == []


def test_hybrid_chroma_exposes_collection_info() -> None:
    retriever = _retriever_with_docs(SAMPLE_DOCS)
    assert retriever.collection_name == "kb_test"
    assert isinstance(retriever.persist_directory, Path)
    assert retriever.model_name


def test_hybrid_chroma_score_is_rrf_not_raw_distance() -> None:
    """Fused score should differ from raw similarity (RRF rescales contributions)."""
    retriever = _retriever_with_docs(SAMPLE_DOCS, top_k=3)
    results = retriever.search("REST API интеграция", top_k=3)
    assert results
    top = results[0]
    if top["similarity"] is not None:
        assert top["score"] != top["similarity"]


def test_hybrid_chroma_search_logs_fusion_breakdown(caplog) -> None:
    """DoD (issue #91): a search must emit a log line that proves RRF fusion ran.

    The line includes BM25 hits, dense hits, fused count, ``rrf_k`` and
    ``top_k`` so an operator can confirm both branches contributed and that
    the configured RRF constant was honoured.
    """
    retriever = _retriever_with_docs(SAMPLE_DOCS, top_k=2)
    caplog.set_level(logging.INFO, logger="src.rag.retriever")
    retriever.search("REST API SOAP", top_k=2)
    fusion_logs = [
        record for record in caplog.records
        if "HybridChromaRetriever.search" in record.getMessage()
    ]
    assert fusion_logs, "Expected a fusion log line from HybridChromaRetriever.search"
    message = fusion_logs[-1].getMessage()
    assert "bm25_hits=" in message
    assert "dense_hits=" in message
    assert "fused=" in message
    assert "rrf_k=60" in message
    assert "top_k=2" in message
