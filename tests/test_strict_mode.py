"""Tests for STRICT_MODE (BL-03, issue #87).

When ``strict_rag_mode: true`` and the retriever returns no chunks (or every
chunk scores below ``strict_min_score``), ``LLMClient.classify_requirement``
must return a deterministic ``НД`` fallback **without** invoking any LLM
provider. This protects CONCEPT §7 R-01 (hallucination risk).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.client import LLMClient  # noqa: E402


def _provider_factory(call_log: List[str]):
    def provider(system_prompt: str, user_message: str, cfg: Dict[str, Any]) -> str:
        call_log.append("called")
        return json.dumps(
            {
                "classification": "Да",
                "confidence": 0.99,
                "reasoning": "Should not be reached when STRICT_MODE blocks.",
                "citations": [{"source": "x", "section": "1", "quote": "y"}],
                "requires_ba_review": False,
            },
            ensure_ascii=False,
        )

    return provider


def _strict_client(call_log: List[str], min_score: float = 0.30) -> LLMClient:
    return LLMClient(
        llm_config={
            "active_provider": "primary",
            "providers": {"primary": {"priority": 1, "retry_attempts": 1}},
        },
        embedding_config={"strict_rag_mode": True, "strict_min_score": min_score},
        provider_callers={"primary": _provider_factory(call_log)},
    )


def test_strict_mode_blocks_llm_call_when_context_is_empty() -> None:
    """Empty retriever result MUST short-circuit to a deterministic НД."""
    calls: List[str] = []
    client = _strict_client(calls)

    result = client.classify_requirement("Out-of-domain question", context_chunks=[])

    assert result.classification == "НД"
    assert result.provider == "strict_mode"
    assert result.requires_ba_review is True
    assert "STRICT_MODE" in result.reasoning
    assert result.raw.get("strict_mode") is True
    assert calls == [], "LLM provider must NOT be called when STRICT_MODE triggers"


def test_strict_mode_blocks_llm_call_when_top_score_below_threshold() -> None:
    """All chunks below ``strict_min_score`` MUST also trigger the fallback."""
    calls: List[str] = []
    client = _strict_client(calls, min_score=0.30)

    weak_chunks = [
        {"text": "irrelevant 1", "source": "a.md", "score": 0.12},
        {"text": "irrelevant 2", "source": "b.md", "score": 0.05},
    ]

    result = client.classify_requirement("Question", context_chunks=weak_chunks)

    assert result.classification == "НД"
    assert result.provider == "strict_mode"
    assert "low_score" in result.reasoning
    assert calls == []


def test_strict_mode_allows_llm_when_at_least_one_chunk_passes_threshold() -> None:
    """If any chunk scores ≥ threshold the LLM call proceeds normally."""
    calls: List[str] = []
    client = _strict_client(calls, min_score=0.30)

    chunks = [
        {"text": "weak", "source": "a.md", "score": 0.10},
        {"text": "strong", "source": "b.md", "score": 0.42},
    ]

    result = client.classify_requirement("Question", context_chunks=chunks)

    assert result.provider == "primary", "LLM provider must be called"
    assert result.classification == "Да"
    assert calls == ["called"]


def test_strict_mode_disabled_keeps_legacy_behaviour() -> None:
    """With ``strict_rag_mode: false`` the LLM is invoked even on empty context."""
    calls: List[str] = []
    client = LLMClient(
        llm_config={
            "active_provider": "primary",
            "providers": {"primary": {"priority": 1, "retry_attempts": 1}},
        },
        embedding_config={"strict_rag_mode": False},
        provider_callers={"primary": _provider_factory(calls)},
    )

    result = client.classify_requirement("Question", context_chunks=[])

    assert result.classification == "Да"
    assert calls == ["called"]


def test_strict_mode_supports_chroma_similarity_field() -> None:
    """ChromaRetriever uses ``similarity`` rather than ``score`` — both must work."""
    calls: List[str] = []
    client = _strict_client(calls, min_score=0.30)

    chunks = [{"text": "good", "source": "a.md", "similarity": 0.41}]

    result = client.classify_requirement("Question", context_chunks=chunks)

    assert result.provider == "primary"
    assert calls == ["called"]
