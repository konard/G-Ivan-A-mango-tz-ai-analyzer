"""Tests for the BL-22 temperature lock (issue #87).

``LLMClient`` must read the ``decoding:`` block from
``configs/llm_config.yaml`` once and inject it into the per-provider config
on every call to ``classify_requirement`` and ``generate_rag_response``.
Provider-level overrides for the four locked keys (``temperature``,
``top_p``, ``seed``, ``max_tokens``) MUST lose to the decoding block.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import client as client_module  # noqa: E402
from src.llm.client import (  # noqa: E402
    DECODING_PARAM_KEYS,
    LLMClient,
    _decoding_overrides,
)


def test_decoding_param_keys_match_spec() -> None:
    """BL-22 fixes exactly four keys in the decoding lock."""
    assert DECODING_PARAM_KEYS == ("temperature", "top_p", "seed", "max_tokens")


def test_decoding_block_injected_into_classify_provider_cfg() -> None:
    """The decoding block from llm_config overrides per-provider temperature."""
    captured: Dict[str, Any] = {}

    def capture_provider(system_prompt: str, user_message: str, cfg: Dict[str, Any]) -> str:
        captured.update(cfg)
        return json.dumps(
            {
                "classification": "Да",
                "confidence": 0.9,
                "reasoning": "ok",
                "citations": [{"source": "x", "section": "1", "quote": "y"}],
                "requires_ba_review": False,
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config={
            "active_provider": "primary",
            "providers": {
                "primary": {
                    "priority": 1,
                    "retry_attempts": 1,
                    "temperature": 0.9,  # MUST be beaten by the decoding lock
                }
            },
            "decoding": {
                "temperature": 0.1,
                "top_p": 0.9,
                "seed": 42,
                "max_tokens": 1024,
            },
        },
        provider_callers={"primary": capture_provider},
    )

    client.classify_requirement(
        "Что-то",
        context_chunks=[{"text": "rel", "source": "a.md", "score": 0.5}],
    )

    assert captured["temperature"] == 0.1
    assert captured["top_p"] == 0.9
    assert captured["seed"] == 42
    assert captured["max_tokens"] == 1024


def test_decoding_block_absent_keeps_legacy_provider_cfg() -> None:
    """When llm_config has no `decoding:` block the caller cfg is unchanged.

    Guards the legacy contract exercised by
    ``test_generate_rag_response_passes_provider_config``.
    """
    captured: Dict[str, Any] = {}

    def capture_provider(system_prompt: str, user_message: str, cfg: Dict[str, Any]) -> str:
        captured.update(cfg)
        return json.dumps(
            {
                "classification": "Да",
                "confidence": 0.9,
                "reasoning": "ok",
                "citations": [{"source": "x", "section": "1", "quote": "y"}],
                "requires_ba_review": False,
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config={
            "active_provider": "primary",
            "providers": {"primary": {"priority": 1, "retry_attempts": 1, "model": "demo"}},
        },
        provider_callers={"primary": capture_provider},
    )

    client.classify_requirement(
        "Что-то",
        context_chunks=[{"text": "rel", "source": "a.md", "score": 0.5}],
    )

    assert re.fullmatch(r"[0-9a-f]{12}", captured.pop("run_id"))
    assert captured == {"priority": 1, "retry_attempts": 1, "model": "demo"}


def test_decoding_block_injected_into_rag_provider_cfg(monkeypatch) -> None:
    """``generate_rag_response`` also propagates the locked decoding params."""
    captured: Dict[str, Any] = {}

    def gigachat_capture(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
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

    client = LLMClient(
        llm_config={
            "providers": {"gigachat": {"model": "GigaChat-Pro", "temperature": 0.7}},
            "decoding": {
                "temperature": 0.1,
                "top_p": 0.9,
                "seed": 42,
                "max_tokens": 1024,
            },
        }
    )

    client.generate_rag_response("sys", "user", mask=False)

    assert captured["temperature"] == 0.1
    assert captured["top_p"] == 0.9
    assert captured["seed"] == 42
    assert captured["max_tokens"] == 1024
    assert captured["model"] == "GigaChat-Pro"


def test_decoding_overrides_returns_only_set_keys() -> None:
    """``_decoding_overrides`` MUST NOT inject ``None``/missing keys."""
    assert _decoding_overrides({"temperature": 0.1}) == {}
    assert _decoding_overrides({"top_p": 0.9, "seed": 42, "max_tokens": 1024}) == {
        "top_p": 0.9,
        "seed": 42,
        "max_tokens": 1024,
    }
    assert _decoding_overrides({"top_p": None, "seed": None}) == {}


def test_packaged_llm_config_carries_decoding_block() -> None:
    """The shipped ``configs/llm_config.yaml`` MUST declare the lock (BL-22)."""
    import yaml

    config = yaml.safe_load(
        Path("configs/llm_config.yaml").read_text(encoding="utf-8")
    )
    decoding = config.get("decoding")
    assert isinstance(decoding, dict)
    assert decoding["temperature"] == 0.1
    assert decoding["top_p"] == 0.9
    assert decoding["seed"] == 42
    assert decoding["max_tokens"] == 1024
