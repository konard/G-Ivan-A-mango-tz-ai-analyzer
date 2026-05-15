"""CLI for measuring classification quality of the TZ analyzer.

Compares pipeline predictions against an expert gold standard and reports
Macro-F1 plus per-class precision / recall / F1. This script implements
NFR-01 (Macro-F1 >= 0.70) from ``docs/CONCEPT.md`` §5 and the MVP exit
criteria (§8.1.1).

Usage::

    python scripts/evaluate/evaluate_quality.py \\
        --gold test_data/gold_standard.json \\
        --pred output/result_test.xlsx \\
        --output reports/quality_report.json

Predictions may be supplied as:

* Excel produced by ``src.exporters.excel_exporter`` — columns ``ID`` /
  ``[Статус]`` are recognised out of the box;
* JSON list of dicts shaped like ``{"id": ..., "Статус": "Да"}`` (the key
  name may also be ``[Статус]``, ``status`` or ``expected_status``).

No additional dependencies beyond what ships with the MVP are required;
``pandas`` / ``openpyxl`` are imported lazily only when an Excel file is
provided.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

logger = logging.getLogger("evaluate_quality")

CLASSES: Tuple[str, ...] = ("Да", "Нет", "Частично", "НД")

ID_COLUMN_CANDIDATES: Tuple[str, ...] = ("id", "ID", "Id", "№", "Номер")
STATUS_COLUMN_CANDIDATES: Tuple[str, ...] = (
    "[Статус]",
    "Статус",
    "status",
    "Status",
    "classification",
    "expected_status",
)


class _JsonFormatter(logging.Formatter):
    """JSON log formatter aligned with ``src.pipeline._JsonFormatter``."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        run_id = getattr(record, "run_id", None)
        if run_id:
            entry["run_id"] = run_id
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class _RunIdFilter(logging.Filter):
    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "run_id", None):
            record.run_id = self._run_id
        return True


def configure_json_logging(run_id: str, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RunIdFilter(run_id))
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _normalise_id(raw: Any) -> str:
    """Coerce an id value to a comparable string (``REQ-001`` <-> ``1``)."""
    if raw is None:
        return ""
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    return str(raw).strip()


def _normalise_status(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _pick_column(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    cols = list(columns)
    for name in candidates:
        if name in cols:
            return name
    lowered = {c.lower(): c for c in cols}
    for name in candidates:
        match = lowered.get(name.lower())
        if match is not None:
            return match
    return None


def load_gold_standard(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load a gold-standard dataset.

    Supports both the shape documented in the issue (``[{"id": ..., "expected_status": ...}]``)
    and the wrapped variant currently shipped in the repo
    (``{"version": "...", "items": [...]}``).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Gold standard not found: {file_path}")
    payload = json.loads(file_path.read_text(encoding="utf-8"))

    items: List[Mapping[str, Any]]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    else:
        raise ValueError(
            f"Unsupported gold-standard structure in {file_path}. "
            "Expected a list or an object with an 'items' array."
        )

    records: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        records.append(
            {
                "id": _normalise_id(item.get("id")),
                "expected_status": _normalise_status(item.get("expected_status")),
                "sources": list(item.get("sources") or item.get("expected_sources") or []),
            }
        )
    return records


def _load_predictions_json(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("predictions", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
        else:
            raise ValueError(
                f"Unsupported predictions JSON structure in {path}. "
                "Expected a list or an object with 'predictions'/'items'/'results'."
            )
    else:
        raise ValueError(f"Unsupported predictions JSON structure in {path}.")

    records: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        status = (
            row.get("[Статус]")
            or row.get("Статус")
            or row.get("status")
            or row.get("classification")
            or row.get("expected_status")
        )
        records.append(
            {
                "id": _normalise_id(row.get("id") or row.get("ID")),
                "status": _normalise_status(status),
            }
        )
    return records


def _load_predictions_excel(path: Path) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only when pandas missing
        raise RuntimeError(
            "pandas is required to read Excel predictions. "
            "Install it with `pip install pandas openpyxl`."
        ) from exc

    df = pd.read_excel(path)
    if df.empty:
        return []

    id_col = _pick_column(df.columns, ID_COLUMN_CANDIDATES)
    status_col = _pick_column(df.columns, STATUS_COLUMN_CANDIDATES)
    if status_col is None:
        raise ValueError(
            f"No status column found in {path}. Expected one of: "
            + ", ".join(STATUS_COLUMN_CANDIDATES)
        )

    records: List[Dict[str, Any]] = []
    for offset, row in enumerate(df.to_dict(orient="records"), start=1):
        raw_id = row.get(id_col) if id_col else offset
        records.append(
            {
                "id": _normalise_id(raw_id),
                "status": _normalise_status(row.get(status_col)),
            }
        )
    return records


def load_predictions(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load predictions from JSON or Excel based on file extension."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return _load_predictions_json(file_path)
    if suffix in {".xlsx", ".xls"}:
        return _load_predictions_excel(file_path)
    raise ValueError(
        f"Unsupported predictions format '{suffix}'. Use .json, .xlsx or .xls."
    )


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


@dataclass
class ClassMetrics:
    label: str
    support: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "support": self.support,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class EvaluationReport:
    matched: int = 0
    gold_total: int = 0
    pred_total: int = 0
    macro_f1: float = 0.0
    accuracy: float = 0.0
    per_class: Dict[str, ClassMetrics] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    missing_in_pred: List[str] = field(default_factory=list)
    extra_in_pred: List[str] = field(default_factory=list)
    invalid_status: List[Dict[str, str]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    classes: Tuple[str, ...] = CLASSES

    def as_dict(self) -> Dict[str, Any]:
        return {
            "matched": self.matched,
            "gold_total": self.gold_total,
            "pred_total": self.pred_total,
            "macro_f1": round(self.macro_f1, 4),
            "accuracy": round(self.accuracy, 4),
            "classes": list(self.classes),
            "per_class": {label: m.as_dict() for label, m in self.per_class.items()},
            "confusion_matrix": self.confusion_matrix,
            "missing_in_pred": list(self.missing_in_pred),
            "extra_in_pred": list(self.extra_in_pred),
            "invalid_status": list(self.invalid_status),
            "items": list(self.items),
        }


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def compute_metrics(
    gold: Iterable[Mapping[str, Any]],
    predictions: Iterable[Mapping[str, Any]],
    classes: Iterable[str] = CLASSES,
) -> EvaluationReport:
    """Compare gold-standard and prediction records, return an EvaluationReport.

    Records are joined by their normalised ``id``. Mismatched IDs are logged
    and reported but do not abort the computation.
    """
    classes_tuple = tuple(classes)
    gold_list = [dict(item) for item in gold]
    pred_list = [dict(item) for item in predictions]

    gold_by_id: Dict[str, Dict[str, Any]] = {}
    for record in gold_list:
        rid = _normalise_id(record.get("id"))
        if not rid:
            continue
        gold_by_id[rid] = record

    pred_by_id: Dict[str, Dict[str, Any]] = {}
    for record in pred_list:
        rid = _normalise_id(record.get("id"))
        if not rid:
            continue
        pred_by_id[rid] = record

    report = EvaluationReport(
        gold_total=len(gold_by_id),
        pred_total=len(pred_by_id),
        classes=classes_tuple,
    )
    report.confusion_matrix = {
        actual: {predicted: 0 for predicted in classes_tuple} for actual in classes_tuple
    }
    report.per_class = {label: ClassMetrics(label=label) for label in classes_tuple}

    missing_in_pred = sorted(set(gold_by_id) - set(pred_by_id))
    extra_in_pred = sorted(set(pred_by_id) - set(gold_by_id))
    report.missing_in_pred = missing_in_pred
    report.extra_in_pred = extra_in_pred

    for rid in missing_in_pred:
        logger.warning("Prediction missing for gold id=%s", rid)
    for rid in extra_in_pred:
        logger.warning("Prediction for unknown gold id=%s ignored", rid)

    correct = 0
    for rid, gold_row in gold_by_id.items():
        pred_row = pred_by_id.get(rid)
        if pred_row is None:
            continue
        actual = _normalise_status(gold_row.get("expected_status"))
        predicted = _normalise_status(pred_row.get("status"))
        item_entry: Dict[str, Any] = {
            "id": rid,
            "expected": actual,
            "predicted": predicted,
            "correct": False,
        }
        if actual not in classes_tuple or predicted not in classes_tuple:
            logger.warning(
                "Skipping id=%s due to unknown status (expected=%r predicted=%r)",
                rid,
                actual,
                predicted,
            )
            report.invalid_status.append(
                {"id": rid, "expected": actual, "predicted": predicted}
            )
            report.items.append(item_entry)
            continue

        report.matched += 1
        report.confusion_matrix[actual][predicted] += 1
        report.per_class[actual].support += 1
        if actual == predicted:
            report.per_class[actual].tp += 1
            correct += 1
            item_entry["correct"] = True
        else:
            report.per_class[actual].fn += 1
            report.per_class[predicted].fp += 1
        report.items.append(item_entry)

    f1_sum = 0.0
    for metrics in report.per_class.values():
        metrics.precision = _safe_divide(metrics.tp, metrics.tp + metrics.fp)
        metrics.recall = _safe_divide(metrics.tp, metrics.tp + metrics.fn)
        metrics.f1 = _safe_divide(
            2 * metrics.precision * metrics.recall,
            metrics.precision + metrics.recall,
        )
        f1_sum += metrics.f1

    report.macro_f1 = _safe_divide(f1_sum, len(classes_tuple))
    report.accuracy = _safe_divide(correct, report.matched)
    return report


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_summary(report: EvaluationReport) -> str:
    """Return a human-readable summary suitable for printing to stdout."""
    lines: List[str] = []
    lines.append("📊 Quality Report")
    lines.append("------------------")
    lines.append(f"Matched records: {report.matched} / {report.gold_total}")
    lines.append(f"Macro-F1: {report.macro_f1:.3f}")
    lines.append(f"Accuracy: {report.accuracy:.3f}")
    lines.append("Per-class F1:")
    for label in report.classes:
        metrics = report.per_class.get(label)
        if metrics is None:
            continue
        lines.append(
            f"  {label}: F1={metrics.f1:.2f} "
            f"(P={metrics.precision:.2f}, R={metrics.recall:.2f}, "
            f"support={metrics.support})"
        )
    if report.missing_in_pred:
        preview = ", ".join(report.missing_in_pred[:10])
        if len(report.missing_in_pred) > 10:
            preview += f", … (+{len(report.missing_in_pred) - 10})"
        lines.append(f"⚠️ Mismatched IDs (missing in pred): {preview}")
    if report.extra_in_pred:
        preview = ", ".join(report.extra_in_pred[:10])
        if len(report.extra_in_pred) > 10:
            preview += f", … (+{len(report.extra_in_pred) - 10})"
        lines.append(f"⚠️ Unknown IDs in predictions: {preview}")
    if report.invalid_status:
        lines.append(
            f"⚠️ Records with unknown status labels: {len(report.invalid_status)}"
        )
    return "\n".join(lines)


def save_report(report: EvaluationReport, output_path: Union[str, Path]) -> Path:
    """Persist the full evaluation report as JSON or CSV (by file suffix)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        _save_report_csv(report, path)
    else:
        path.write_text(
            json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return path


def _save_report_csv(report: EvaluationReport, path: Path) -> None:
    import csv

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["label", "support", "tp", "fp", "fn", "precision", "recall", "f1"])
        for label in report.classes:
            metrics = report.per_class.get(label)
            if metrics is None:
                continue
            writer.writerow(
                [
                    metrics.label,
                    metrics.support,
                    metrics.tp,
                    metrics.fp,
                    metrics.fn,
                    f"{metrics.precision:.4f}",
                    f"{metrics.recall:.4f}",
                    f"{metrics.f1:.4f}",
                ]
            )
        writer.writerow([])
        writer.writerow(["macro_f1", f"{report.macro_f1:.4f}"])
        writer.writerow(["accuracy", f"{report.accuracy:.4f}"])
        writer.writerow(["matched", report.matched])
        writer.writerow(["gold_total", report.gold_total])
        writer.writerow(["pred_total", report.pred_total])


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare pipeline predictions with the gold standard and report "
            "Macro-F1 plus per-class metrics (NFR-01)."
        )
    )
    parser.add_argument(
        "--gold",
        required=True,
        help="Path to the gold-standard JSON (e.g. test_data/gold_standard.json).",
    )
    parser.add_argument(
        "--pred",
        required=True,
        help="Path to predictions exported by the pipeline (.xlsx or .json).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the detailed report (.json or .csv).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v INFO, -vv DEBUG).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    run_id = str(uuid.uuid4())
    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    configure_json_logging(run_id=run_id, level=level)
    logger.info("Quality evaluation started: gold=%s pred=%s", args.gold, args.pred)

    try:
        gold = load_gold_standard(args.gold)
        predictions = load_predictions(args.pred)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    except (ValueError, RuntimeError) as exc:
        logger.error("Failed to load inputs: %s", exc)
        return 2

    report = compute_metrics(gold, predictions)

    print(render_summary(report))

    if args.output:
        path = save_report(report, args.output)
        logger.info("Report written to %s", path)

    logger.info(
        "Quality evaluation finished: macro_f1=%.4f matched=%d gold=%d pred=%d",
        report.macro_f1,
        report.matched,
        report.gold_total,
        report.pred_total,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
