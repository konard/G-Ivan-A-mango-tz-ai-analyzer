"""Tests for BL-15 context-dependent in-memory exports."""

from __future__ import annotations

from io import BytesIO

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from src.utils.export import (  # noqa: E402
    export_chat_to_markdown,
    export_to_excel,
    load_excel_columns,
)


def test_load_excel_columns_reads_strict_allow_list() -> None:
    assert load_excel_columns() == [
        "requirement_id",
        "requirement_text",
        "classification",
        "reasoning",
        "citations",
    ]


def test_export_to_excel_filters_service_columns_and_masks_pii() -> None:
    data = pd.DataFrame(
        [
            {
                "requirement_id": "REQ-1",
                "requirement_text": "Contact admin@example.com for access",
                "classification": "Да",
                "reasoning": "Call +7 999 123 45 67",
                "citations": "doc.pdf",
                "raw": "raw prompt",
                "provider": "openrouter",
            }
        ]
    )

    exported = export_to_excel(data)

    assert isinstance(exported, BytesIO)
    df = pd.read_excel(exported)
    assert list(df.columns) == load_excel_columns()
    assert "raw" not in df.columns
    assert "provider" not in df.columns
    assert df.loc[0, "requirement_text"] == "Contact [EMAIL] for access"
    assert df.loc[0, "reasoning"] == "Call [PHONE]"


def test_export_chat_to_markdown_formats_dialog_and_masks_pii() -> None:
    exported = export_chat_to_markdown(
        [
            {"role": "user", "content": "Как настроить admin@example.com?"},
            {"role": "assistant", "content": "Используйте +7 999 123 45 67."},
        ]
    )

    markdown = exported.getvalue().decode("utf-8-sig")
    assert markdown == (
        "### Вопрос\nКак настроить [EMAIL]?\n\n"
        "### Ответ\nИспользуйте [PHONE]."
    )
