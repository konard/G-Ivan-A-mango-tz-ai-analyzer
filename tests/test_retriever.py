import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.retriever import (  # noqa: E402
    HybridRetriever,
    _hash_embedding,
    build_retriever,
)


def _sample_docs():
    return [
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


def test_search_returns_top_k() -> None:
    retriever = HybridRetriever(embedder=_hash_embedding)
    retriever.add_documents(_sample_docs())
    results = retriever.search("Битрикс24 синхронизация контактов", top_k=2)
    assert len(results) <= 2
    assert results[0]["source"] == "crm.md"
    assert results[0]["score"] > 0


def test_search_empty_query_returns_empty_list() -> None:
    retriever = HybridRetriever(embedder=_hash_embedding)
    retriever.add_documents(_sample_docs())
    assert retriever.search("") == []


def test_search_without_documents_returns_empty() -> None:
    retriever = HybridRetriever(embedder=_hash_embedding)
    assert retriever.search("anything") == []


def test_build_retriever_factory() -> None:
    retriever = build_retriever(
        documents=_sample_docs(),
        config_path="configs/embedding_config.yaml",
        embedder=_hash_embedding,
    )
    results = retriever.search("протоколы интеграции SOAP")
    assert results
    assert results[0]["source"] == "integration.md"


def test_strict_embedder_mode_raises_without_dependencies(monkeypatch) -> None:
    """Without sentence-transformers installed, the retriever MUST fail loudly."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise ImportError("simulated missing dep")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="Embedding model unavailable. Strict mode enabled."):
        HybridRetriever()
