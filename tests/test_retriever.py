import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.retriever import HybridRetriever, build_retriever  # noqa: E402


def _sample_docs():
    return [
        {
            "text": "MANGO CRM поддерживает коннектор Битрикс24 с синхронизацией контактов через REST API.",
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
    retriever = HybridRetriever()
    retriever.add_documents(_sample_docs())
    results = retriever.search("Битрикс24 синхронизация контактов", top_k=2)
    assert len(results) <= 2
    assert results[0]["source"] == "crm.md"
    assert results[0]["score"] > 0


def test_search_empty_query_returns_empty_list() -> None:
    retriever = HybridRetriever()
    retriever.add_documents(_sample_docs())
    assert retriever.search("") == []


def test_search_without_documents_returns_empty() -> None:
    retriever = HybridRetriever()
    assert retriever.search("anything") == []


def test_build_retriever_factory() -> None:
    retriever = build_retriever(documents=_sample_docs(), config_path="configs/embedding_config.yaml")
    results = retriever.search("протоколы интеграции SOAP")
    assert results
    assert results[0]["source"] == "integration.md"
