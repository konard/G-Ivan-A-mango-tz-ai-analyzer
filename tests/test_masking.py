"""Tests for data masking functionality.

Tests cover the MVP patterns from ``configs/masking_rules.yaml`` (issue #45):
- Email addresses
- Russian phone numbers (+7 format)
- IP addresses
- Internal domains (internal, corp, local)

ФИО / legal entity / ИП masking is intentionally OUT OF SCOPE for MVP — the
former regression tests for ``[LEGAL_ENTITY]`` / ``[IE_SURNAME]`` have been
replaced by a single guard test (:class:`TestDeferredPatterns`) that asserts
those tokens never appear in masking output.
"""

import logging
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.masking import (  # noqa: E402
    DEFAULT_PAYLOAD_TRUNCATE_BYTES,
    REDACTED_MARKER,
    Masker,
    mask_context_chunks,
    mask_text,
    sanitize_log_record,
)


class TestEmailMasking:
    """Test email address masking."""

    def test_mask_single_email(self):
        """Test masking a single email address."""
        text = "Contact: admin@example.com for support"
        result = mask_text(text)
        assert "[EMAIL]" in result
        assert "admin@example.com" not in result

    def test_mask_multiple_emails(self):
        """Test masking multiple email addresses."""
        text = "Send to user@test.org and copy to admin@company.ru"
        result = mask_text(text)
        assert result.count("[EMAIL]") == 2
        assert "user@test.org" not in result
        assert "admin@company.ru" not in result

    def test_email_with_subdomain(self):
        """Test email with subdomain is masked."""
        text = "Reach out to dev.team@sub.domain.example.com"
        result = mask_text(text)
        assert "[EMAIL]" in result
        assert "dev.team@sub.domain.example.com" not in result


class TestPhoneRUMasking:
    """Test Russian phone number masking."""

    def test_mask_phone_standard_format(self):
        """Test masking standard +7 phone format."""
        text = "Call +71234567890 for assistance"
        result = mask_text(text)
        assert "[PHONE]" in result
        assert "+71234567890" not in result

    def test_mask_phone_with_spaces(self):
        """Test masking phone with spaces."""
        text = "Phone: +7 123 456 78 90"
        result = mask_text(text)
        assert "[PHONE]" in result

    def test_mask_phone_with_dashes(self):
        """Test masking phone with dashes."""
        text = "Contact +7-123-456-78-90"
        result = mask_text(text)
        assert "[PHONE]" in result

    def test_mask_phone_with_parentheses(self):
        """Test masking phone with parentheses around area code."""
        text = "Call +7(123)456-78-90"
        result = mask_text(text)
        assert "[PHONE]" in result


class TestIPMasking:
    """Test IP address masking."""

    def test_mask_ipv4_address(self):
        """Test masking IPv4 address."""
        text = "Server at 192.168.1.100 is down"
        result = mask_text(text)
        assert "[IP]" in result
        assert "192.168.1.100" not in result

    def test_mask_multiple_ips(self):
        """Test masking multiple IP addresses."""
        text = "From 10.0.0.1 to 172.16.0.254"
        result = mask_text(text)
        assert result.count("[IP]") == 2
        assert "10.0.0.1" not in result
        assert "172.16.0.254" not in result

    def test_ip_in_url_context(self):
        """Test IP address in URL-like context."""
        text = "Access http://192.168.0.1:8080/admin"
        result = mask_text(text)
        assert "[IP]" in result


class TestInternalDomainMasking:
    """Test internal domain masking."""

    def test_mask_internal_subdomain(self):
        """Test masking a subdomain of an internal TLD."""
        text = "See docs at docs.internal.example for details"
        result = mask_text(text)
        assert "[DOMAIN]" in result

    def test_mask_internal_domain(self):
        """Test masking internal domain."""
        text = "API endpoint: api.internal.company"
        result = mask_text(text)
        assert "[DOMAIN]" in result

    def test_mask_corp_domain(self):
        """Test masking corp domain."""
        text = "Intranet at portal.corp.local"
        result = mask_text(text)
        assert "[DOMAIN]" in result

    def test_mask_local_domain(self):
        """Test masking local domain."""
        # Pattern matches domains like corp.local, internal.example where the
        # keyword (internal|corp|local) is part of the TLD structure
        text = "Dev server: portal.corp.local or api.internal.example"
        result = mask_text(text)
        assert "[DOMAIN]" in result
        assert "portal.corp.local" not in result
        assert "api.internal.example" not in result


class TestContextChunksMasking:
    """Test masking of RAG context chunks."""

    def test_mask_context_chunk_with_email(self):
        """Test that context chunk text is masked."""
        chunks = [
            {"text": "Contact admin@example.com for help", "source": "doc.md"}
        ]
        result = mask_context_chunks(chunks)
        assert "[EMAIL]" in result[0]["text"]
        assert "admin@example.com" not in result[0]["text"]

    def test_mask_context_chunk_with_ip(self):
        """Test that context chunk with IP is masked."""
        chunks = [
            {"text": "Server 192.168.1.1 responded", "source": "log.txt"}
        ]
        result = mask_context_chunks(chunks)
        assert "[IP]" in result[0]["text"]
        assert "192.168.1.1" not in result[0]["text"]

    def test_mask_multiple_context_chunks(self):
        """Test masking multiple context chunks."""
        chunks = [
            {"text": "Email: test@example.com", "source": "a.md"},
            {"text": "Phone: +71234567890", "source": "b.md"},
        ]
        result = mask_context_chunks(chunks)
        assert "[EMAIL]" in result[0]["text"]
        assert "[PHONE]" in result[1]["text"]

    def test_empty_context_chunks(self):
        """Test handling empty context chunks list."""
        result = mask_context_chunks([])
        assert result == []

    def test_context_chunk_without_text(self):
        """Test handling chunk without text field."""
        chunks = [{"source": "doc.md"}]
        result = mask_context_chunks(chunks)
        assert result == chunks

    def test_context_chunk_preserves_metadata(self):
        """Test that metadata is preserved after masking."""
        chunks = [
            {
                "text": "Contact user@test.org",
                "source": "doc.md",
                "metadata": {"section": "contacts"}
            }
        ]
        result = mask_context_chunks(chunks)
        assert result[0]["source"] == "doc.md"
        assert result[0]["metadata"]["section"] == "contacts"
        assert "[EMAIL]" in result[0]["text"]


class TestMaskerClass:
    """Test the Masker class interface."""

    def test_masker_instance(self):
        """Test Masker class instantiation and usage."""
        masker = Masker()
        result = masker.mask("Email: test@example.com")
        assert "[EMAIL]" in result

    def test_masker_with_custom_config(self, tmp_path):
        """Test Masker with custom config path."""
        config = tmp_path / "custom_masking.yaml"
        config.write_text(
            """
patterns:
  - name: test_pattern
    regex: "TEST"
    replacement: "[REDACTED]"
""",
            encoding="utf-8",
        )
        masker = Masker(config_path=str(config))
        result = masker.mask("This is TEST data")
        assert "[REDACTED]" in result


class TestCombinedSensitiveData:
    """Test masking of combined sensitive data."""

    def test_mask_all_patterns_in_one_text(self):
        """Test masking all pattern types in single text."""
        text = (
            "Contact admin@internal.example at +71234567890. "
            "Server: 192.168.1.1. Backup: backup@corp.local"
        )
        result = mask_text(text)
        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[IP]" in result
        # Note: internal domains in email addresses are masked as [EMAIL] first,
        # so [DOMAIN] won't appear for those specific cases
        # Test domain separately where it's not part of an email
        domain_text = "Access portal.corp.local for docs"
        domain_result = mask_text(domain_text)
        assert "[DOMAIN]" in domain_result


class TestDeferredPatterns:
    """ФИО / legal-entity / ИП masking is deferred (issue #45).

    These tests guard against regressions that would re-introduce the
    out-of-scope replacements. The masker must leave such tokens untouched.
    """

    def test_legal_entity_token_is_not_emitted(self):
        result = mask_text('Соглашение с ООО "СекретКомпани"')
        assert "[LEGAL_ENTITY]" not in result
        assert 'ООО "СекретКомпани"' in result

    def test_ie_token_is_not_emitted(self):
        result = mask_text("Контрагент ИП Сидоров подписал")
        assert "[IE_SURNAME]" not in result
        assert "ИП Сидоров" in result


class TestMaskingLogging:
    """Test that masking emits debug log events without leaking data."""

    def test_debug_log_does_not_contain_original_value(self, caplog):
        """Debug logs must reference pattern name only, never the secret."""
        caplog.set_level(logging.DEBUG, logger="src.llm.masking")
        mask_text("Контакт admin@secret-corp.io req-42", context="req-42")
        joined = "\n".join(record.getMessage() for record in caplog.records)
        assert "admin@secret-corp.io" not in joined
        assert "email" in joined
        assert "req-42" in joined


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self):
        """Test masking empty string."""
        assert mask_text("") == ""

    def test_no_sensitive_data(self):
        """Test text without sensitive data passes through unchanged."""
        text = "This is a normal requirement without sensitive data"
        result = mask_text(text)
        assert result == text

    def test_none_like_input(self):
        """Test handling of None-like input (empty string)."""
        assert mask_text("") == ""


class TestLogSanitization:
    """BL-23 (issue #87) — log/report sanitiser used by pipeline logs and
    ``evaluate_rag.py`` artifacts. Contract documented in
    ``docs/audit/data-masking_v1.md`` §8 and ``docs/ADR/003-…`` §4.3.
    """

    def test_sanitize_log_record_masks_message_field(self):
        record = {
            "timestamp": "2026-05-17T10:00:00",
            "level": "INFO",
            "logger": "src.pipeline",
            "message": "Contacted admin@example.com via +71234567890",
            "run_id": "abc123",
        }
        sanitized = sanitize_log_record(record)

        assert sanitized["message"].count("[EMAIL]") == 1
        assert sanitized["message"].count("[PHONE]") == 1
        assert "admin@example.com" not in sanitized["message"]
        assert "+71234567890" not in sanitized["message"]
        # Trace identifiers MUST be preserved verbatim.
        assert sanitized["run_id"] == "abc123"
        assert sanitized["level"] == "INFO"
        assert sanitized["logger"] == "src.pipeline"
        assert sanitized["timestamp"] == "2026-05-17T10:00:00"

    def test_sanitize_log_record_masks_payload_question_and_answer(self):
        record = {
            "level": "INFO",
            "logger": "src.rag",
            "message": "rag_eval_completed",
            "payload": {
                "question": "Как связаться: ivan@example.com?",
                "answer": "Позвоните +71234567890 или зайдите на api.corp.local",
                "context": "Сервер 192.168.10.5 доступен для интеграции",
            },
        }
        sanitized = sanitize_log_record(record)

        joined = repr(sanitized)
        assert "ivan@example.com" not in joined
        assert "+71234567890" not in joined
        assert "api.corp.local" not in joined
        assert "192.168.10.5" not in joined
        assert "[EMAIL]" in sanitized["payload"]["question"]
        assert "[PHONE]" in sanitized["payload"]["answer"]
        assert "[DOMAIN]" in sanitized["payload"]["answer"]
        assert "[IP]" in sanitized["payload"]["context"]

    def test_sanitize_log_record_masks_nested_chunks(self):
        record = {
            "level": "INFO",
            "message": "retrieved chunks",
            "chunks": [
                {"text": "Owner: owner@example.com", "source": "kb1.md", "score": 0.91},
                {"text": "Внутренний сервер api.internal.example", "source": "kb2.md"},
            ],
        }
        sanitized = sanitize_log_record(record)

        assert "[EMAIL]" in sanitized["chunks"][0]["text"]
        assert "owner@example.com" not in sanitized["chunks"][0]["text"]
        assert "[DOMAIN]" in sanitized["chunks"][1]["text"]
        assert "api.internal.example" not in sanitized["chunks"][1]["text"]
        # Non-text fields stay intact.
        assert sanitized["chunks"][0]["source"] == "kb1.md"
        assert sanitized["chunks"][0]["score"] == 0.91

    def test_sanitize_log_record_redacts_secret_env_vars(self):
        record = {
            "level": "WARN",
            "message": "auth failed",
            "DEEPSEEK_API_KEY": "sk-real-secret-1234",
            "GIGACHAT_AUTH": "Basic eW91LXNob3VsZC1ub3Qtc2VlLXRoaXM=",
            "OPENROUTER_API_KEY": "or-real-1234",
            "user_id": "kept-as-is",
        }
        sanitized = sanitize_log_record(record)

        assert sanitized["DEEPSEEK_API_KEY"] == REDACTED_MARKER
        assert sanitized["GIGACHAT_AUTH"] == REDACTED_MARKER
        assert sanitized["OPENROUTER_API_KEY"] == REDACTED_MARKER
        assert sanitized["user_id"] == "kept-as-is"

    def test_sanitize_log_record_truncates_oversized_payload(self):
        oversized = "X" * (DEFAULT_PAYLOAD_TRUNCATE_BYTES + 4096)
        record = {"level": "INFO", "message": "x", "payload": oversized}
        sanitized = sanitize_log_record(record)

        assert len(sanitized["payload"].encode("utf-8")) <= DEFAULT_PAYLOAD_TRUNCATE_BYTES
        assert "[TRUNCATED:" in sanitized["payload"]

    def test_sanitize_log_record_preserves_classification_and_provider(self):
        record = {
            "level": "INFO",
            "message": "classified email@example.com",
            "provider": "gigachat",
            "classification": "Да",
            "requirement_id": "REQ-001",
        }
        sanitized = sanitize_log_record(record)

        assert sanitized["provider"] == "gigachat"
        assert sanitized["classification"] == "Да"
        assert sanitized["requirement_id"] == "REQ-001"
        assert "email@example.com" not in sanitized["message"]

    def test_sanitize_log_record_is_pure(self):
        """The original record dict MUST NOT be mutated."""
        record = {"level": "INFO", "message": "ping a@b.com"}
        before = dict(record)
        sanitize_log_record(record)
        assert record == before

    def test_sanitize_log_record_rejects_non_dict_input(self):
        with pytest.raises(TypeError):
            sanitize_log_record("plain string")  # type: ignore[arg-type]

    def test_log_sanitization_applies_to_evaluate_rag_report(self, tmp_path):
        """Audit doc §8.3: evaluate_rag reports MUST be sanitised before write.

        Simulates an ``evaluate_rag.py`` artifact written via
        ``sanitize_log_record`` + ``json.dump``; the regex set from §2 of
        the audit MUST find zero matches in the final file.
        """
        import json
        import re

        raw_report = {
            "run_id": "rag-eval-001",
            "timestamp": "2026-05-17T11:00:00",
            "logger": "scripts.evaluate.evaluate_rag",
            "level": "INFO",
            "message": "rag-eval finished",
            "metrics": {"hit_rate_at_3": 0.9, "mrr": 0.83, "context_recall": 0.78},
            "samples": [
                {
                    "question": "Как связаться с поддержкой api.corp.local?",
                    "answer": "Пишите на support@example.com, тел +71234567890",
                    "context": "IP 10.0.0.1 — резервный сервер",
                    "chunks": [
                        {
                            "text": "Контакт администратора admin@internal.example",
                            "source": "kb.md",
                            "score": 0.88,
                        }
                    ],
                }
            ],
        }
        sanitized = sanitize_log_record(raw_report)
        report_path = tmp_path / "rag-eval-001.json"
        report_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        content = report_path.read_text(encoding="utf-8")
        forbidden_patterns = [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            r"\+7[\s\-]?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}",
            r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            r"\b(?:[a-zA-Z0-9-]+\.)?(internal|corp|local)\.[a-z]{2,}\b",
        ]
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, content)
            assert matches == [], (
                f"Sanitised evaluate_rag report contains forbidden pattern "
                f"{pattern!r}: {matches!r}"
            )
        # Sanity-check: the report still carries trace metadata.
        assert sanitized["run_id"] == "rag-eval-001"
        assert sanitized["metrics"]["hit_rate_at_3"] == 0.9
