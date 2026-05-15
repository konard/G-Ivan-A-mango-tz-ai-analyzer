"""Tests for the Excel exporter (issue #45 MUST 4 — FR-06).

The exporter MUST emit exactly four result columns, in order:
``[Статус], [Комментарий], [Confidence], [RunID]`` — no extended audit
columns, and ``[RunID]`` MUST be populated on every row so the UI retry
workflow can filter by run without re-upload.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from src.exporters.excel_exporter import RESULT_COLUMNS, save_results  # noqa: E402


def _sample_results():
    return [
        {
            "id": 1,
            "text": "Поддержка SIP",
            "classification": {
                "classification": "Да",
                "reasoning": "Подтверждено документацией.",
                "citations": [{"source": "sip.md", "section": "1", "quote": "yes"}],
                "confidence": 0.91,
                "requires_ba_review": False,
                "recommendations": "n/a",
                "provider": "qwen",
            },
        },
        {
            "id": 2,
            "text": "Сломанное требование",
            "error": "RuntimeError: simulated provider outage",
            "classification": {
                "classification": "Ошибка",
                "reasoning": "Ошибка обработки.",
                "citations": [],
                "confidence": 0.0,
                "requires_ba_review": True,
                "recommendations": "",
                "provider": "",
            },
        },
    ]


def test_result_columns_are_exactly_four_mvp_columns():
    assert RESULT_COLUMNS == ["[Статус]", "[Комментарий]", "[Confidence]", "[RunID]"]


def test_save_results_emits_only_mvp_columns(tmp_path: Path) -> None:
    output_file = tmp_path / "result.xlsx"
    save_results(_sample_results(), output_file, run_id="run-xyz")

    df = pd.read_excel(output_file)
    for col in RESULT_COLUMNS:
        assert col in df.columns, f"missing required column {col}"

    forbidden = [
        "[Цитаты]",
        "[Уверенность]",
        "[Рекомендация]",
        "[Требует ревью]",
        "[Провайдер]",
        "[Ошибка]",
        "[run_id]",  # legacy lower-case duplicate
    ]
    for col in forbidden:
        assert col not in df.columns, f"forbidden column {col!r} leaked into output"

    assert (df["[RunID]"] == "run-xyz").all()
    assert df["[Статус]"].tolist() == ["Да", "Ошибка"]
    assert df["[Confidence]"].iloc[0] == pytest.approx(0.91)
    assert df["[Confidence]"].iloc[1] == pytest.approx(0.0)


def test_save_results_with_source_preserves_input_columns(tmp_path: Path) -> None:
    source_file = tmp_path / "tz.xlsx"
    pd.DataFrame(
        {
            "ID": [1, 2],
            "Требование": ["A", "B"],
            "Раздел": ["Общее", "AI"],
        }
    ).to_excel(source_file, index=False)

    output_file = tmp_path / "out.xlsx"
    save_results(
        _sample_results(),
        output_file,
        source_file=source_file,
        run_id="run-abc",
    )

    df = pd.read_excel(output_file)
    assert list(df.columns)[:3] == ["ID", "Требование", "Раздел"]
    assert list(df.columns)[-4:] == RESULT_COLUMNS
    assert (df["[RunID]"] == "run-abc").all()
