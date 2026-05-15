"""Smoke tests for the F1 evaluation CLI (issue #47)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate.evaluate_quality import (  # noqa: E402
    CLASSES,
    compute_metrics,
    load_gold_standard,
    load_predictions,
    main,
    render_summary,
    save_report,
)


def _gold(*items):
    return [
        {"id": rid, "expected_status": status, "sources": []}
        for rid, status in items
    ]


def _pred(*items):
    return [{"id": rid, "status": status} for rid, status in items]


def test_perfect_match_yields_macro_f1_one():
    gold = _gold(("1", "Да"), ("2", "Нет"), ("3", "Частично"), ("4", "НД"))
    predictions = _pred(("1", "Да"), ("2", "Нет"), ("3", "Частично"), ("4", "НД"))

    report = compute_metrics(gold, predictions)

    assert report.matched == 4
    assert report.macro_f1 == pytest.approx(1.0)
    assert report.accuracy == pytest.approx(1.0)
    for label in CLASSES:
        metrics = report.per_class[label]
        assert metrics.f1 == pytest.approx(1.0)
        assert metrics.support == 1


def test_complete_mismatch_yields_zero_metrics_without_division_error():
    gold = _gold(("1", "Да"), ("2", "Нет"))
    predictions = _pred(("1", "Нет"), ("2", "Да"))

    report = compute_metrics(gold, predictions)

    assert report.matched == 2
    assert report.macro_f1 == pytest.approx(0.0)
    assert report.accuracy == pytest.approx(0.0)


def test_empty_dataset_does_not_crash():
    report = compute_metrics([], [])
    assert report.matched == 0
    assert report.macro_f1 == 0.0
    assert report.accuracy == 0.0
    for label in CLASSES:
        assert report.per_class[label].f1 == 0.0


def test_partial_match_with_missing_and_extra_ids():
    gold = _gold(("1", "Да"), ("2", "Нет"), ("3", "Частично"))
    predictions = _pred(("1", "Да"), ("2", "Да"), ("99", "НД"))

    report = compute_metrics(gold, predictions)

    assert report.matched == 2
    assert report.missing_in_pred == ["3"]
    assert report.extra_in_pred == ["99"]
    assert report.confusion_matrix["Да"]["Да"] == 1
    assert report.confusion_matrix["Нет"]["Да"] == 1

    # Per-class numbers reflect only the matched pairs.
    da = report.per_class["Да"]
    assert da.tp == 1 and da.fp == 1
    assert da.precision == pytest.approx(0.5)
    assert da.recall == pytest.approx(1.0)
    assert da.f1 == pytest.approx(2 / 3)

    no = report.per_class["Нет"]
    assert no.tp == 0 and no.fn == 1
    assert no.f1 == 0.0


def test_id_normalisation_supports_numeric_and_string_keys():
    gold = [{"id": 1, "expected_status": "Да"}, {"id": "REQ-002", "expected_status": "Нет"}]
    predictions = [
        {"id": "1", "status": "Да"},
        {"id": "REQ-002", "status": "Нет"},
    ]

    report = compute_metrics(gold, predictions)

    assert report.matched == 2
    assert report.macro_f1 > 0


def test_invalid_status_records_are_skipped_and_reported():
    gold = _gold(("1", "Да"), ("2", "Unknown"))
    predictions = _pred(("1", "Да"), ("2", "Нет"))

    report = compute_metrics(gold, predictions)

    assert report.matched == 1
    assert report.invalid_status == [
        {"id": "2", "expected": "Unknown", "predicted": "Нет"}
    ]


def test_load_gold_standard_accepts_both_shapes(tmp_path: Path):
    wrapped = {
        "version": "1.0",
        "items": [
            {"id": 1, "expected_status": "Да", "expected_sources": ["a.pdf"]},
        ],
    }
    flat = [
        {"id": "REQ-001", "expected_status": "Да", "sources": ["a.pdf"]},
    ]
    wrapped_path = tmp_path / "wrapped.json"
    wrapped_path.write_text(json.dumps(wrapped, ensure_ascii=False), encoding="utf-8")
    flat_path = tmp_path / "flat.json"
    flat_path.write_text(json.dumps(flat, ensure_ascii=False), encoding="utf-8")

    wrapped_records = load_gold_standard(wrapped_path)
    flat_records = load_gold_standard(flat_path)

    assert len(wrapped_records) == 1
    assert wrapped_records[0]["id"] == "1"
    assert wrapped_records[0]["expected_status"] == "Да"
    assert wrapped_records[0]["sources"] == ["a.pdf"]

    assert flat_records[0]["id"] == "REQ-001"
    assert flat_records[0]["sources"] == ["a.pdf"]


def test_load_predictions_json(tmp_path: Path):
    pred_path = tmp_path / "pred.json"
    pred_path.write_text(
        json.dumps(
            [
                {"id": 1, "Статус": "Да"},
                {"id": 2, "[Статус]": "Нет"},
                {"id": 3, "status": "Частично"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records = load_predictions(pred_path)
    statuses = {r["id"]: r["status"] for r in records}
    assert statuses == {"1": "Да", "2": "Нет", "3": "Частично"}


def test_load_predictions_excel(tmp_path: Path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")

    pred_path = tmp_path / "result.xlsx"
    pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Требование": ["a", "b", "c"],
            "[Статус]": ["Да", "Нет", "Частично"],
        }
    ).to_excel(pred_path, index=False)

    records = load_predictions(pred_path)
    statuses = {r["id"]: r["status"] for r in records}
    assert statuses == {"1": "Да", "2": "Нет", "3": "Частично"}


def test_render_summary_contains_macro_f1_and_per_class():
    gold = _gold(("1", "Да"), ("2", "Нет"))
    predictions = _pred(("1", "Да"), ("2", "Нет"))
    report = compute_metrics(gold, predictions)

    text = render_summary(report)
    assert "Quality Report" in text
    assert "Macro-F1" in text
    assert "Да:" in text


def test_save_report_writes_valid_json(tmp_path: Path):
    gold = _gold(("1", "Да"), ("2", "Нет"), ("3", "Частично"), ("4", "НД"))
    predictions = _pred(("1", "Да"), ("2", "Нет"), ("3", "Частично"), ("4", "НД"))
    report = compute_metrics(gold, predictions)

    out_path = tmp_path / "report.json"
    save_report(report, out_path)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["macro_f1"] == 1.0
    assert payload["matched"] == 4
    assert "per_class" in payload and "confusion_matrix" in payload


def test_main_cli_smoke(tmp_path: Path, capsys):
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(
        json.dumps(
            {
                "items": [
                    {"id": 1, "expected_status": "Да"},
                    {"id": 2, "expected_status": "Нет"},
                    {"id": 3, "expected_status": "Частично"},
                    {"id": 4, "expected_status": "НД"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pred_path = tmp_path / "pred.json"
    pred_path.write_text(
        json.dumps(
            [
                {"id": 1, "Статус": "Да"},
                {"id": 2, "Статус": "Нет"},
                {"id": 3, "Статус": "Частично"},
                {"id": 4, "Статус": "НД"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "report.json"

    exit_code = main(
        [
            "--gold",
            str(gold_path),
            "--pred",
            str(pred_path),
            "--output",
            str(out_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Macro-F1: 1.000" in captured.out
    assert out_path.exists()
    assert json.loads(out_path.read_text(encoding="utf-8"))["macro_f1"] == 1.0


def test_main_returns_error_when_gold_missing(tmp_path: Path):
    pred_path = tmp_path / "pred.json"
    pred_path.write_text("[]", encoding="utf-8")

    exit_code = main(
        [
            "--gold",
            str(tmp_path / "missing.json"),
            "--pred",
            str(pred_path),
        ]
    )

    assert exit_code == 2
