"""Tests for ``LLMClient.generate_rag_response`` (issue #73).

The new RAG response path must:

- Walk the fallback chain in the order GigaChat → OpenRouter → Ollama.
- Return free text (no JSON validation, no ``response_format`` constraint).
- Treat any exception from a provider as a non-fatal warning and fall through.
- Raise ``LLMError`` only when every provider has failed.

These tests patch the module-level provider callers so they exercise the
orchestration logic without making real HTTP calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import client as client_module  # noqa: E402
from src.llm.client import (  # noqa: E402
    RAG_FALLBACK_CHAIN,
    LLMClient,
    LLMError,
)


def _make_client(config: Dict[str, Any] | None = None) -> LLMClient:
    return LLMClient(llm_config=config or {})


def test_rag_fallback_chain_order() -> None:
    """Issue #73 mandates the GigaChat → OpenRouter → Ollama order."""
    assert RAG_FALLBACK_CHAIN == ("gigachat", "openrouter", "ollama")


def test_generate_rag_response_first_provider_returns_text(monkeypatch) -> None:
    calls: list[str] = []

    def gigachat_ok(system_prompt, user_prompt, cfg):
        calls.append("gigachat")
        return "Привет, это ответ от GigaChat."

    def openrouter_fail(*args, **kwargs):
        calls.append("openrouter")
        raise AssertionError("Should not be called when GigaChat succeeds")

    def ollama_fail(*args, **kwargs):
        calls.append("ollama")
        raise AssertionError("Should not be called when GigaChat succeeds")

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_ok)
    monkeypatch.setattr(client_module, "_call_openrouter_rag", openrouter_fail)
    monkeypatch.setattr(client_module, "_call_ollama_rag", ollama_fail)

    answer = _make_client().generate_rag_response("sys", "вопрос")
    assert answer == "Привет, это ответ от GigaChat."
    assert calls == ["gigachat"]


def test_generate_rag_response_falls_through_to_openrouter(monkeypatch) -> None:
    calls: list[str] = []

    def gigachat_fail(*args, **kwargs):
        calls.append("gigachat")
        raise RuntimeError("HTTP 403: forbidden")

    def openrouter_ok(system_prompt, user_prompt, cfg):
        calls.append("openrouter")
        return "OpenRouter answer"

    def ollama_fail(*args, **kwargs):
        calls.append("ollama")
        raise AssertionError("Should not be reached")

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_fail)
    monkeypatch.setattr(client_module, "_call_openrouter_rag", openrouter_ok)
    monkeypatch.setattr(client_module, "_call_ollama_rag", ollama_fail)

    answer = _make_client().generate_rag_response("sys", "вопрос")
    assert answer == "OpenRouter answer"
    assert calls == ["gigachat", "openrouter"]


def test_generate_rag_response_falls_through_to_ollama(monkeypatch) -> None:
    calls: list[str] = []

    def gigachat_fail(*args, **kwargs):
        calls.append("gigachat")
        raise RuntimeError("SSL error")

    def openrouter_fail(*args, **kwargs):
        calls.append("openrouter")
        raise RuntimeError("HTTP 429: rate limited")

    def ollama_ok(system_prompt, user_prompt, cfg):
        calls.append("ollama")
        return "Local Ollama answer"

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_fail)
    monkeypatch.setattr(client_module, "_call_openrouter_rag", openrouter_fail)
    monkeypatch.setattr(client_module, "_call_ollama_rag", ollama_ok)

    answer = _make_client().generate_rag_response("sys", "вопрос")
    assert answer == "Local Ollama answer"
    assert calls == ["gigachat", "openrouter", "ollama"]


def test_generate_rag_response_raises_when_all_fail(monkeypatch) -> None:
    def fail_with(name: str):
        def _fail(*args, **kwargs):
            raise RuntimeError(f"{name} down")

        return _fail

    monkeypatch.setattr(client_module, "_call_gigachat_rag", fail_with("gigachat"))
    monkeypatch.setattr(client_module, "_call_openrouter_rag", fail_with("openrouter"))
    monkeypatch.setattr(client_module, "_call_ollama_rag", fail_with("ollama"))

    with pytest.raises(LLMError, match="All RAG providers failed"):
        _make_client().generate_rag_response("sys", "вопрос")


def test_generate_rag_response_passes_provider_config(monkeypatch) -> None:
    """Per-provider sections of llm_config.yaml are forwarded to the caller."""
    captured: Dict[str, Any] = {}

    def gigachat_capture(system_prompt, user_prompt, cfg):
        captured.update(cfg)
        return "ok"

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_capture)
    monkeypatch.setattr(
        client_module,
        "_call_openrouter_rag",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError),
    )
    monkeypatch.setattr(
        client_module,
        "_call_ollama_rag",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError),
    )

    client = _make_client(
        {
            "providers": {
                "gigachat": {"model": "GigaChat-Pro", "temperature": 0.2},
            }
        }
    )
    client.generate_rag_response("sys", "user")
    assert captured == {"model": "GigaChat-Pro", "temperature": 0.2}


def test_generate_rag_response_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="user_prompt must not be empty"):
        _make_client().generate_rag_response("sys", "")
    with pytest.raises(ValueError, match="user_prompt must not be empty"):
        _make_client().generate_rag_response("sys", "   ")


def test_classify_requirement_still_works_after_rag_addition(monkeypatch) -> None:
    """The legacy classifier must keep its DeepSeek→GigaChat behaviour intact."""
    import json

    def deepseek_ok(system_prompt, user_message, cfg):
        return json.dumps(
            {
                "classification": "Да",
                "confidence": 0.9,
                "reasoning": "Документация подтверждает.",
                "citations": [{"source": "doc.md", "section": "1", "quote": "ok"}],
                "requires_ba_review": False,
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config={
            "active_provider": "deepseek",
            "fallback_providers": ["deepseek"],
            "providers": {"deepseek": {"priority": 1, "retry_attempts": 1}},
        },
        provider_callers={"deepseek": deepseek_ok},
    )
    result = client.classify_requirement("Что-то", context_chunks=[])
    assert result.classification == "Да"
    assert result.provider == "deepseek"
