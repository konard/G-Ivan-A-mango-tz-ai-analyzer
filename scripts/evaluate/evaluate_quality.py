#!/usr/bin/env python3
"""Classification quality evaluator (issue #45 SHOULD 1).

Compares pipeline output against ``test_data/gold_standard.json`` and reports
precision / recall / F1 per class (`Да`, `Нет`, `Частично`, `НД`) plus a
macro-average. Designed for ad-hoc CI / local use — no external services.

Usage:

    # Run the pipeline and evaluate the produced workbook:
    python scripts/evaluate/evaluate_quality.py \\
        --pipeline-output output/result.xlsx \\
        --gold test_data/gold_standard.json

    # Or evaluate a workbook that already has [Статус]:
    python scripts/evaluate/evaluate_quality.py \\
        --pipeline-output output/result.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_GOLD_PATH = PROJECT_ROOT / "test_data" / "gold_standard.json"
SUPPORTED_LABELS: Tuple[str, ...] = ("Да", "Нет", "Частично", "НД")


@dataclass
class ClassMetrics:
    label: str
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return self.true_positive / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return self.true_positive / denom if denom else 0.0

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


@dataclass
class EvaluationReport:
    per_class: Dict[str, ClassMetrics]
    total: int = 0
    correct: int = 0
    pairs: List[Tuple[int, str, str]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def macro_f1(self) -> float:
        if not self.per_class:
            return 0.0
        return sum(m.f1 for m in self.per_class.values()) / len(self.per_class)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "correct": self.correct,
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "per_class": {
                label: {
                    "precision": round(m.precision, 4),
                    "recall": round(m.recall, 4),
                    "f1": round(m.f1, 4),
                    "tp": m.true_positive,
                    "fp": m.false_positive,
                    "fn": m.false_negative,
                }
                for label, m in self.per_class.items()
            },
        }


def load_gold(path: Path) -> Dict[int, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    return {int(item["id"]): str(item["expected_status"]) for item in items}


def load_predictions(workbook: Path) -> Dict[int, str]:
    """Read the pipeline result workbook and return ``{id: predicted_status}``.

    The result workbook from :mod:`src.exporters.excel_exporter` keeps the
    source columns intact and appends ``[Статус]``. Row id is taken from the
    ``ID`` / ``id`` column when present, otherwise from the 1-based row index.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to evaluate quality. Install requirements.txt."
        ) from exc

    df = pd.read_excel(workbook)
    if "[Статус]" not in df.columns:
        raise ValueError(
            f"{workbook} does not contain the [Статус] column; "
            "is this a pipeline result workbook?"
        )
    id_col = next((c for c in df.columns if str(c).lower() in {"id", "№"}), None)
    predictions: Dict[int, str] = {}
    for idx, row in df.iterrows():
        if id_col is not None and not _is_blank(row[id_col]):
            try:
                req_id = int(row[id_col])
            except (TypeError, ValueError):
                req_id = idx + 1
        else:
            req_id = idx + 1
        predictions[req_id] = str(row["[Статус]"])
    return predictions


def _is_blank(value) -> bool:
    if value is None:
        return True
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:  # noqa: BLE001
        pass
    return str(value).strip() == ""


def evaluate(
    predictions: Dict[int, str],
    gold: Dict[int, str],
    labels: Iterable[str] = SUPPORTED_LABELS,
) -> EvaluationReport:
    metrics = {label: ClassMetrics(label=label) for label in labels}
    report = EvaluationReport(per_class=metrics)

    for req_id, expected in gold.items():
        predicted = predictions.get(req_id)
        if predicted is None:
            # Missing prediction → false negative for the expected class.
            if expected in metrics:
                metrics[expected].false_negative += 1
            report.total += 1
            report.pairs.append((req_id, expected, ""))
            continue

        report.total += 1
        report.pairs.append((req_id, expected, predicted))
        if predicted == expected:
            report.correct += 1
            if predicted in metrics:
                metrics[predicted].true_positive += 1
        else:
            if expected in metrics:
                metrics[expected].false_negative += 1
            if predicted in metrics:
                metrics[predicted].false_positive += 1
    return report


def _format_text(report: EvaluationReport) -> str:
    lines = [
        f"Evaluated {report.total} items; correct={report.correct}; "
        f"accuracy={report.accuracy:.2%}; macro F1={report.macro_f1:.3f}",
        "",
        f"{'class':<10} {'precision':>10} {'recall':>10} {'f1':>10} "
        f"{'tp':>4} {'fp':>4} {'fn':>4}",
    ]
    for label, m in report.per_class.items():
        lines.append(
            f"{label:<10} {m.precision:>10.3f} {m.recall:>10.3f} {m.f1:>10.3f} "
            f"{m.true_positive:>4} {m.false_positive:>4} {m.false_negative:>4}"
        )
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pipeline-output",
        required=True,
        type=Path,
        help="Path to the .xlsx result emitted by src.pipeline.run_analysis",
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=DEFAULT_GOLD_PATH,
        help="Path to gold_standard.json (default: test_data/gold_standard.json)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args(argv)

    gold = load_gold(args.gold)
    predictions = load_predictions(args.pipeline_output)
    report = evaluate(predictions, gold)

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
