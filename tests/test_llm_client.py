import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.client import LLMClient, LLMError, mask_text  # noqa: E402


def test_mask_text_email_and_phone(tmp_path: Path) -> None:
    config = tmp_path / "masking.yaml"
    config.write_text(
        """
patterns:
  - name: email
    regex: "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]{2,}"
    replacement: "[EMAIL]"
  - name: phone
    regex: "\\\\+7\\\\d{10}"
    replacement: "[PHONE]"
""",
        encoding="utf-8",
    )
    masked = mask_text("Контакт: ivan@example.com, +71234567890", config_path=str(config))
    assert "[EMAIL]" in masked
    assert "[PHONE]" in masked


def _llm_config(retry_attempts: int = 1):
    return {
        "active_provider": "primary",
        "fallback_providers": ["primary", "secondary"],
        "providers": {
            "primary": {"priority": 1, "retry_attempts": retry_attempts},
            "secondary": {"priority": 2, "retry_attempts": retry_attempts},
        },
    }


def test_classify_requirement_uses_primary_provider() -> None:
    calls = {"primary": 0, "secondary": 0}

    def primary(system_prompt, user_message, cfg):
        calls["primary"] += 1
        return json.dumps(
            {
                "requirement_id": "1",
                "requirement_text": "test",
                "classification": "Да",
                "confidence": 0.9,
                "reasoning": "Документация подтверждает.",
                "citations": [
                    {"source": "doc.md", "section": "1.1", "quote": "поддерживается"}
                ],
                "requires_ba_review": False,
                "recommendations": "",
            },
            ensure_ascii=False,
        )

    def secondary(system_prompt, user_message, cfg):
        calls["secondary"] += 1
        raise AssertionError("Secondary should not be called when primary succeeds")

    client = LLMClient(
        llm_config=_llm_config(),
        provider_callers={"primary": primary, "secondary": secondary},
    )
    result = client.classify_requirement(
        "Поддержка SIP",
        context_chunks=[{"source": "doc.md", "text": "SIP поддерживается"}],
    )
    assert result.classification == "Да"
    assert result.provider == "primary"
    assert calls == {"primary": 1, "secondary": 0}


def test_classify_requirement_falls_back_to_secondary() -> None:
    def primary(system_prompt, user_message, cfg):
        raise RuntimeError("primary down")

    def secondary(system_prompt, user_message, cfg):
        return json.dumps(
            {
                "classification": "Частично",
                "confidence": 0.65,
                "reasoning": "Найдено частичное соответствие.",
                "citations": [{"source": "doc.md", "section": "1", "quote": "часть"}],
                "requires_ba_review": True,
                "recommendations": "Уточнить у вендора.",
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config=_llm_config(),
        provider_callers={"primary": primary, "secondary": secondary},
    )
    result = client.classify_requirement("Поддержка X", context_chunks=[])
    assert result.classification == "Частично"
    assert result.provider == "secondary"
    assert result.requires_ba_review is True


def test_classify_requirement_invalid_json_then_fallback() -> None:
    def primary(system_prompt, user_message, cfg):
        return "definitely not json"

    def secondary(system_prompt, user_message, cfg):
        return json.dumps(
            {
                "classification": "НД",
                "confidence": 0.1,
                "reasoning": "Нет данных.",
                "citations": [],
                "requires_ba_review": True,
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config=_llm_config(),
        provider_callers={"primary": primary, "secondary": secondary},
    )
    result = client.classify_requirement("Что-то", context_chunks=[])
    assert result.classification == "НД"


def test_classify_requirement_all_fail_raises() -> None:
    def fail(system_prompt, user_message, cfg):
        raise RuntimeError("nope")

    client = LLMClient(
        llm_config=_llm_config(),
        provider_callers={"primary": fail, "secondary": fail},
    )
    with pytest.raises(LLMError):
        client.classify_requirement("Что-то", context_chunks=[])


def test_classify_requirement_masks_requirement_and_context() -> None:
    """Test that both requirement text and RAG context chunks are masked before LLM call."""
    captured_messages = []

    def capture_provider(system_prompt, user_message, cfg):
        captured_messages.append({"system": system_prompt, "user": user_message})
        return json.dumps(
            {
                "classification": "НД",
                "confidence": 0.0,
                "reasoning": "Test masking verification",
                "citations": [],
                "requires_ba_review": True,
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config={"providers": {"test": {}}},
        masking_config_path="configs/masking_rules.yaml",
        provider_callers={"test": capture_provider},
    )

    # Requirement with sensitive data
    req_text = "Contact admin@example.com at +71234567890 for support"
    # Context chunks with sensitive data
    context_chunks = [
        {"text": "Server IP: 192.168.1.100 is responding", "source": "infra.md"},
        {"text": "API endpoint: api.mango.internal/docs", "source": "api.md"},
    ]

    result = client.classify_requirement(req_text, context_chunks)

    assert len(captured_messages) == 1
    user_msg = captured_messages[0]["user"]

    # Verify requirement text is masked
    assert "admin@example.com" not in user_msg
    assert "+71234567890" not in user_msg
    assert "[EMAIL]" in user_msg
    assert "[PHONE]" in user_msg

    # Verify context chunks are masked
    assert "192.168.1.100" not in user_msg
    assert "api.mango.internal" not in user_msg
    assert "[IP]" in user_msg
    assert "[DOMAIN]" in user_msg


def test_classify_requirement_fails_without_context_masking() -> None:
    """Test that would fail if context_chunks were not masked.
    
    This test verifies the mitigation of risk 9.1 from the audit:
    RAG context must be masked before sending to LLM.
    """
    captured_user_messages = []

    def capture_provider(system_prompt, user_message, cfg):
        captured_user_messages.append(user_message)
        return json.dumps(
            {
                "classification": "Да",
                "confidence": 0.9,
                "reasoning": "Confirmed",
                "citations": [{"source": "doc.md", "section": "1", "quote": "yes"}],
                "requires_ba_review": False,
            },
            ensure_ascii=False,
        )

    client = LLMClient(
        llm_config={"providers": {"test": {}}},
        provider_callers={"test": capture_provider},
    )

    # Context with sensitive internal domain that should be masked
    context_with_secret = [
        {"text": "Internal API: secret-api.internal.corp", "source": "internal.md"}
    ]

    client.classify_requirement("Test requirement", context_with_secret)

    # If masking was not applied to context, this assertion would fail
    user_msg = captured_user_messages[0]
    assert "secret-api.internal.corp" not in user_msg, \
        "Context chunk was not masked - sensitive data leaked to LLM!"
    assert "[DOMAIN]" in user_msg, "Domain masking was not applied to context"
