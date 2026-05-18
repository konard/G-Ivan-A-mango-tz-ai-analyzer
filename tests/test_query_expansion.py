from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.rag.query_expansion import (
    QueryExpansionConfig,
    QueryExpansionRetriever,
    parse_expansion_response,
)


class _FakeLLM:
    def __init__(self, response: str = "[]", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: List[Dict[str, Any]] = []

    def generate_rag_response(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        mask: bool = True,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "mask": mask,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class _FakeRetriever:
    def __init__(self, hits_by_query: Dict[str, List[Dict[str, Any]]]) -> None:
        self.hits_by_query = hits_by_query
        self.queries: List[str] = []
        self.top_k = 5
        self.config = {
            "rrf_k": 60,
            "rag": {"query_expansion_enabled": True, "expansion_count": 3},
        }

    def search(
        self,
        query: str,
        top_k: int | None = None,
        **_kwargs: Any,
    ) -> List[Dict[str, Any]]:
        self.queries.append(query)
        hits = [dict(item) for item in self.hits_by_query.get(query, [])]
        return hits[:top_k] if top_k is not None else hits


def test_parse_expansion_response_accepts_array_and_deduplicates_original() -> None:
    response = json.dumps(
        ["ВАТС подключение", "исходный запрос", "SIP Trunk настройка"],
        ensure_ascii=False,
    )

    expansions = parse_expansion_response(
        response,
        original_query="исходный запрос",
        max_count=3,
    )

    assert expansions == ["ВАТС подключение", "SIP Trunk настройка"]


def test_parse_expansion_response_accepts_queries_object() -> None:
    response = '{"queries": [{"query": "VPBX настройка"}, "SIP-транк ВАТС"]}'

    expansions = parse_expansion_response(
        response,
        original_query="облачная телефония",
        max_count=3,
    )

    assert expansions == ["VPBX настройка", "SIP-транк ВАТС"]


def test_query_expansion_retriever_generates_searches_and_deduplicates_hits() -> None:
    retriever = _FakeRetriever(
        {
            "IP телефония": [
                {"id": "a", "source": "ats.md", "chunk_idx": 1, "text": "original"}
            ],
            "SIP Trunk": [
                {"id": "a", "source": "ats.md", "chunk_idx": 1, "text": "duplicate"},
                {"id": "b", "source": "sip.md", "chunk_idx": 2, "text": "sip"},
            ],
            "ВАТС": [
                {"id": "c", "source": "vpbx.md", "chunk_idx": 3, "text": "vpbx"}
            ],
            "VPBX": [
                {"id": "b", "source": "sip.md", "chunk_idx": 2, "text": "sip duplicate"}
            ],
        }
    )
    llm = _FakeLLM(json.dumps(["SIP Trunk", "ВАТС", "VPBX"], ensure_ascii=False))

    wrapped = QueryExpansionRetriever(retriever, llm, config=retriever.config)
    results = wrapped.search("IP телефония", top_k=5)

    assert retriever.queries == ["IP телефония", "SIP Trunk", "ВАТС", "VPBX"]
    assert {item["id"] for item in results} == {"a", "b", "c"}
    assert len(results) == 3
    assert results[0]["id"] == "a"
    assert llm.calls and llm.calls[0]["mask"] is True


def test_query_expansion_falls_back_to_original_on_llm_error() -> None:
    retriever = _FakeRetriever(
        {
            "IP телефония": [
                {"id": "a", "source": "ats.md", "chunk_idx": 1, "text": "original"}
            ]
        }
    )
    llm = _FakeLLM(error=RuntimeError("provider down"))

    wrapped = QueryExpansionRetriever(retriever, llm, config=retriever.config)
    results = wrapped.search("IP телефония", top_k=5)

    assert retriever.queries == ["IP телефония"]
    assert results == [
        {"id": "a", "source": "ats.md", "chunk_idx": 1, "text": "original"}
    ]


def test_query_expansion_falls_back_to_original_on_invalid_json() -> None:
    retriever = _FakeRetriever(
        {
            "IP телефония": [
                {"id": "a", "source": "ats.md", "chunk_idx": 1, "text": "original"}
            ]
        }
    )
    llm = _FakeLLM("this is not json")

    wrapped = QueryExpansionRetriever(retriever, llm, config=retriever.config)
    results = wrapped.search("IP телефония", top_k=5)

    assert retriever.queries == ["IP телефония"]
    assert results == [
        {"id": "a", "source": "ats.md", "chunk_idx": 1, "text": "original"}
    ]


def test_shipped_embedding_config_disables_query_expansion_by_default() -> None:
    config_path = (
        Path(__file__).resolve().parents[1] / "configs" / "embedding_config.yaml"
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    expansion_config = QueryExpansionConfig.from_mapping(config)

    assert config["rag"]["query_expansion_enabled"] is False
    assert config["rag"]["expansion_count"] == 3
    assert expansion_config.enabled is False
    assert expansion_config.expansion_count == 3
