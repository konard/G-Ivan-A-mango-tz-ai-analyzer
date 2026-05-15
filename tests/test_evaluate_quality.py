"""Unit tests for scripts/evaluate/evaluate_quality.py (issue #45 SHOULD 1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "evaluate"))

evaluate_quality = pytest.importorskip("evaluate_quality")


def test_evaluate_perfect_predictions_yields_f1_one():
    gold = {1: "Да", 2: "Нет", 3: "Частично", 4: "НД"}
    predictions = dict(gold)
    report = evaluate_quality.evaluate(predictions, gold)
    assert report.total == 4
    assert report.correct == 4
    assert report.accuracy == 1.0
    assert pytest.approx(report.macro_f1) == 1.0


def test_evaluate_partial_mismatch_drops_f1():
    gold = {1: "Да", 2: "Нет", 3: "Частично"}
    predictions = {1: "Да", 2: "Да", 3: "НД"}  # 1 correct, 2 wrong
    report = evaluate_quality.evaluate(predictions, gold)

    assert report.total == 3
    assert report.correct == 1
    assert report.accuracy == pytest.approx(1 / 3)
    # "Да" precision = 1/2 = 0.5, recall = 1/1 = 1.0, f1 = 2/3
    da = report.per_class["Да"]
    assert da.true_positive == 1
    assert da.false_positive == 1
    assert da.false_negative == 0
    assert da.f1 == pytest.approx(2 / 3)


def test_evaluate_missing_prediction_counts_as_false_negative():
    gold = {1: "Да", 2: "Нет"}
    predictions = {1: "Да"}  # missing id=2
    report = evaluate_quality.evaluate(predictions, gold)
    assert report.per_class["Нет"].false_negative == 1
    assert report.per_class["Нет"].true_positive == 0
