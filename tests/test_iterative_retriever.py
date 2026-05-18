"""Tests for BL-11 multi-hop retrieval (issue #123)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.retriever import IterativeRetriever  # noqa: E402


class _ScriptedRetriever:
    def __init__(self, responses: Dict[str, List[Dict[str, Any]]]) -> None:
        self.responses = responses
        self.queries: List[str] = []

    def search(
        self,
        query: str,
        top_k: int | None = None,
        use_parent_context: bool | None = None,
    ) -> List[Dict[str, Any]]:
        self.queries.append(query)
        return list(self.responses.get(query, []))


def test_iterative_retriever_stops_when_first_hop_is_sufficient() -> None:
    base = _ScriptedRetriever(
        {
            "original": [
                {
                    "text": "SSO setup",
                    "source": "sso.md",
                    "chunk_idx": 0,
                    "score": 0.9,
                }
            ]
        }
    )
    reflection_prompts: List[str] = []

    def reflect(prompt: str) -> str:
        reflection_prompts.append(prompt)
        return '{"sufficient": true, "follow_up": null, "confidence": 0.92}'

    retriever = IterativeRetriever(
        base,
        reflection_call=reflect,
        max_hops=2,
        min_confidence_to_stop=0.8,
    )

    results = retriever.search("original", top_k=3)

    assert [r["source"] for r in results] == ["sso.md"]
    assert base.queries == ["original"]
    assert len(reflection_prompts) == 1
    assert "<question>original</question>" in reflection_prompts[0]
    assert "SSO setup" in reflection_prompts[0]


def test_iterative_retriever_follows_up_and_deduplicates_chunks() -> None:
    base = _ScriptedRetriever(
        {
            "original": [
                {
                    "text": "SSO requires an identity provider.",
                    "source": "sso.md",
                    "chunk_idx": 1,
                    "score": 0.8,
                }
            ],
            "active directory integration": [
                {
                    "text": "SSO requires an identity provider.",
                    "source": "sso.md",
                    "chunk_idx": 1,
                    "score": 0.7,
                },
                {
                    "text": "Active Directory is supported through SAML.",
                    "source": "ad.md",
                    "chunk_idx": 4,
                    "score": 0.85,
                },
            ],
        }
    )
    responses = iter(
        [
            '{"sufficient": false, "follow_up": "active directory integration", "confidence": 0.35}',
            '{"sufficient": true, "follow_up": null, "confidence": 0.91}',
        ]
    )

    retriever = IterativeRetriever(
        base,
        reflection_call=lambda _prompt: next(responses),
        max_hops=2,
        min_confidence_to_stop=0.8,
    )

    results = retriever.search("original", top_k=3)

    assert base.queries == ["original", "active directory integration"]
    assert [(r["source"], r["chunk_idx"]) for r in results] == [
        ("sso.md", 1),
        ("ad.md", 4),
    ]


def test_iterative_retriever_reflection_failure_falls_back_to_hop_zero() -> None:
    base = _ScriptedRetriever(
        {
            "original": [
                {
                    "text": "First-hop context",
                    "source": "fallback.md",
                    "chunk_idx": 0,
                    "score": 0.5,
                }
            ]
        }
    )

    def reflect(_prompt: str) -> str:
        raise TimeoutError("reflection timed out")

    retriever = IterativeRetriever(
        base,
        reflection_call=reflect,
        max_hops=2,
        min_confidence_to_stop=0.8,
    )

    results = retriever.search("original", top_k=3)

    assert base.queries == ["original"]
    assert [r["text"] for r in results] == ["First-hop context"]


def test_iterative_retriever_invalid_json_falls_back_without_raising() -> None:
    base = _ScriptedRetriever(
        {
            "original": [
                {
                    "text": "Context",
                    "source": "doc.md",
                    "chunk_idx": 0,
                    "score": 0.5,
                }
            ]
        }
    )
    retriever = IterativeRetriever(
        base,
        reflection_call=lambda _prompt: "not json",
        max_hops=2,
        min_confidence_to_stop=0.8,
    )

    assert retriever.search("original", top_k=3)[0]["source"] == "doc.md"
