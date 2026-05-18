"""Tests for masked UI error diagnostics."""

from __future__ import annotations

from src.utils.error_handler import ErrorHandler


def test_error_handler_masks_report_before_export() -> None:
    handler = ErrorHandler()
    report = handler.generate_error_report(
        [
            handler.collect_error_context(
                "openrouter",
                RuntimeError("500 for admin@example.com from 192.168.1.1"),
                {"run_id": "run-1", "provider_count": 3},
            )
        ],
        "Позвонить +71234567890 и написать admin@example.com",
        {"run_id": "run-1", "provider_count": 3},
    )

    text = handler.export_to_txt(report).decode("utf-8")

    assert "admin@example.com" not in text
    assert "192.168.1.1" not in text
    assert "+71234567890" not in text
    assert "[EMAIL]" in text
    assert "[IP]" in text
    assert "[PHONE]" in text
