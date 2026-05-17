"""Regression tests for BL-23 LLM audit trail (issue #103)."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import client as client_module  # noqa: E402
from src.llm.client import LLMClient  # noqa: E402


RUN_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def _classification_payload(**overrides: Any) -> str:
    payload: Dict[str, Any] = {
        "classification": "Да",
        "confidence": 0.9,
        "reasoning": "Связаться с admin@example.com нельзя логировать raw.",
        "citations": [{"source": "doc.md", "section": "1", "quote": "ok"}],
        "requires_ba_review": False,
        "recommendations": "",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _audit_records(caplog: pytest.LogCaptureFixture, event: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if getattr(record, "event", None) == event]


def test_classify_audit_trail_masks_logs_and_preserves_run_id_on_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider_run_ids: list[tuple[str, str]] = []

    def primary(system_prompt: str, user_message: str, cfg: Dict[str, Any]) -> str:
        provider_run_ids.append(("primary", cfg["run_id"]))
        raise RuntimeError("primary unavailable")

    def secondary(system_prompt: str, user_message: str, cfg: Dict[str, Any]) -> str:
        provider_run_ids.append(("secondary", cfg["run_id"]))
        return _classification_payload()

    client = LLMClient(
        llm_config={
            "active_provider": "primary",
            "fallback_providers": ["primary", "secondary"],
            "providers": {
                "primary": {"priority": 1, "retry_attempts": 1, "temperature": 0.2},
                "secondary": {"priority": 2, "retry_attempts": 1, "temperature": 0.2},
            },
        },
        provider_callers={"primary": primary, "secondary": secondary},
    )

    with caplog.at_level(logging.INFO, logger="src.llm.client"):
        result = client.classify_requirement(
            "Contact admin@example.com via +71234567890",
            context_chunks=[
                {"source": "kb.md", "text": "Internal host api.corp.local", "score": 0.8}
            ],
            requirement_id="REQ-42",
        )

    assert result.classification == "Да"
    assert len(provider_run_ids) == 2
    run_id = provider_run_ids[0][1]
    assert RUN_ID_RE.match(run_id)
    assert provider_run_ids == [("primary", run_id), ("secondary", run_id)]

    requests = _audit_records(caplog, "LLM_REQUEST")
    responses = _audit_records(caplog, "LLM_RESPONSE")
    assert [getattr(record, "provider", None) for record in requests] == [
        "primary",
        "secondary",
    ]
    assert {getattr(record, "run_id", None) for record in requests + responses} == {
        run_id
    }

    request_text = repr([getattr(record, "user_prompt", "") for record in requests])
    assert "admin@example.com" not in request_text
    assert "+71234567890" not in request_text
    assert "api.corp.local" not in request_text
    assert "[EMAIL]" in request_text
    assert "[PHONE]" in request_text
    assert "[DOMAIN]" in request_text

    success = next(
        record for record in responses if getattr(record, "status", None) == "success"
    )
    assert getattr(success, "requirement_id", None) == "REQ-42"
    assert getattr(success, "prompt_version", None) == "v1.0"
    assert re.fullmatch(r"[0-9a-f]{64}", getattr(success, "prompt_hash", ""))
    assert getattr(success, "classification", None) == "Да"
    assert getattr(success, "latency_ms", None) >= 0.0
    assert "admin@example.com" not in repr(getattr(success, "response", ""))
    assert "[EMAIL]" in repr(getattr(success, "response", ""))


def test_rag_audit_trail_masks_prompt_and_preserves_run_id_on_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider_run_ids: list[tuple[str, str]] = []

    def gigachat_fail(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
        provider_run_ids.append(("gigachat", cfg["run_id"]))
        raise RuntimeError("GigaChat unavailable")

    def openrouter_ok(system_prompt: str, user_prompt: str, cfg: Dict[str, Any]) -> str:
        provider_run_ids.append(("openrouter", cfg["run_id"]))
        return "Ответ отправлен на support@example.com"

    def ollama_fail(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("Ollama should not be reached")

    monkeypatch.setattr(client_module, "_call_gigachat_rag", gigachat_fail)
    monkeypatch.setattr(client_module, "_call_openrouter_rag", openrouter_ok)
    monkeypatch.setattr(client_module, "_call_ollama_rag", ollama_fail)

    client = LLMClient(
        llm_config={
            "providers": {
                "gigachat": {"priority": 1, "retry_attempts": 1},
                "openrouter": {"priority": 2, "retry_attempts": 1},
            }
        }
    )

    with caplog.at_level(logging.INFO, logger="src.llm.client"):
        answer = client.generate_rag_response(
            "system",
            "Контекст: admin@example.com, +71234567890, api.corp.local",
        )

    assert answer == "Ответ отправлен на support@example.com"
    run_id = provider_run_ids[0][1]
    assert RUN_ID_RE.match(run_id)
    assert provider_run_ids == [("gigachat", run_id), ("openrouter", run_id)]

    requests = _audit_records(caplog, "LLM_REQUEST")
    responses = _audit_records(caplog, "LLM_RESPONSE")
    assert [getattr(record, "provider", None) for record in requests] == [
        "gigachat",
        "openrouter",
    ]
    assert {getattr(record, "run_id", None) for record in requests + responses} == {
        run_id
    }
    assert "admin@example.com" not in repr([getattr(r, "user_prompt", "") for r in requests])
    assert "+71234567890" not in repr([getattr(r, "user_prompt", "") for r in requests])
    assert "api.corp.local" not in repr([getattr(r, "user_prompt", "") for r in requests])
    assert "[EMAIL]" in repr([getattr(r, "user_prompt", "") for r in requests])

    success = next(
        record for record in responses if getattr(record, "status", None) == "success"
    )
    assert getattr(success, "provider", None) == "openrouter"
    assert getattr(success, "latency_ms", None) >= 0.0
    assert "support@example.com" not in repr(getattr(success, "response", ""))
    assert "[EMAIL]" in repr(getattr(success, "response", ""))


def test_logger_failures_do_not_break_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def capture_provider(system_prompt: str, user_message: str, cfg: Dict[str, Any]) -> str:
        return _classification_payload(reasoning="ok")

    def broken_info(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("logger sink is down")

    monkeypatch.setattr(client_module.logger, "info", broken_info)

    client = LLMClient(
        llm_config={
            "active_provider": "primary",
            "providers": {"primary": {"priority": 1, "retry_attempts": 1}},
            "decoding": {"temperature": 0.1, "top_p": 0.9, "seed": 42, "max_tokens": 1024},
        },
        provider_callers={"primary": capture_provider},
    )

    result = client.classify_requirement(
        "Requirement",
        context_chunks=[{"source": "doc.md", "text": "Supported", "score": 0.7}],
    )

    assert result.classification == "Да"
