"""Tests for BL-04 RAG channel masking (issue #87).

``LLMClient.generate_rag_response`` MUST apply ``mask_text`` to the user
prompt before any provider is invoked, unless the caller explicitly opts out
with ``mask=False`` (only legal in offline evaluate_rag runs).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import client as client_module  # noqa: E402
from src.llm.client import LLMClient  # noqa: E402


def _capturing_client(monkeypatch, captured: list[str]) -> LLMClient:
    def gigachat_ok(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
        captured.append(user_prompt)
        return "ответ"

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_ok)
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
    return LLMClient(
        llm_config={"providers": {"gigachat": {"model": "GigaChat-Pro"}}},
        masking_config_path="configs/masking_rules.yaml",
    )


SENSITIVE_PROMPT = (
    "Ответь на вопрос. Контекст: связаться через ivan@example.com или +71234567890, "
    "API на api.corp.local, сервер 192.168.10.5."
)


def test_generate_rag_response_masks_user_prompt_by_default(monkeypatch) -> None:
    captured: list[str] = []
    client = _capturing_client(monkeypatch, captured)

    client.generate_rag_response("sys", SENSITIVE_PROMPT)

    assert captured, "Provider was never invoked"
    sent = captured[0]
    assert "ivan@example.com" not in sent
    assert "+71234567890" not in sent
    assert "api.corp.local" not in sent
    assert "192.168.10.5" not in sent
    assert "[EMAIL]" in sent
    assert "[PHONE]" in sent
    assert "[DOMAIN]" in sent
    assert "[IP]" in sent


def test_generate_rag_response_respects_explicit_mask_false(monkeypatch) -> None:
    """Offline ``evaluate_rag.py`` runs may opt out via ``mask=False``."""
    captured: list[str] = []
    client = _capturing_client(monkeypatch, captured)

    client.generate_rag_response("sys", SENSITIVE_PROMPT, mask=False)

    assert captured[0] == SENSITIVE_PROMPT


def test_mask_rag_context_disabled_via_config(monkeypatch) -> None:
    """When ``mask_rag_context: false`` is set in config, masking is off."""
    captured: list[str] = []

    def gigachat_ok(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
        captured.append(user_prompt)
        return "ok"

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_ok)
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
            "providers": {"gigachat": {"model": "GigaChat-Pro"}},
            "mask_rag_context": False,
        }
    )
    client.generate_rag_response("sys", SENSITIVE_PROMPT)

    assert captured[0] == SENSITIVE_PROMPT


def test_mask_rag_context_flag_read_from_embedding_config(monkeypatch) -> None:
    """``mask_rag_context`` may live in embedding_config (canonical home)."""
    captured: list[str] = []

    def gigachat_ok(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
        captured.append(user_prompt)
        return "ok"

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_ok)
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
        llm_config={"providers": {"gigachat": {"model": "GigaChat-Pro"}}},
        embedding_config={"mask_rag_context": False},
    )
    client.generate_rag_response("sys", SENSITIVE_PROMPT)

    assert captured[0] == SENSITIVE_PROMPT


def test_packaged_embedding_config_enables_rag_masking() -> None:
    """The shipped ``configs/embedding_config.yaml`` MUST default to True (BL-04)."""
    import yaml

    config = yaml.safe_load(
        Path("configs/embedding_config.yaml").read_text(encoding="utf-8")
    )
    assert config.get("mask_rag_context") is True
