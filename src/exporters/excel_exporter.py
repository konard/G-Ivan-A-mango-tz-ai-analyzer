"""Excel exporter for classification results.

The exporter preserves the original ТЗ structure (all columns from the input
workbook) and appends the columns mandated by issue #39:

    [Статус], [Комментарий], [Цитаты], [Confidence]

It also adds operational columns ([Провайдер], [Требует ревью], [Ошибка],
[Рекомендация]) so that BAs and auditors get the full picture in one file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)

RESULT_COLUMNS: List[str] = [
    "[Статус]",
    "[Комментарий]",
    "[Цитаты]",
    "[Confidence]",
    "[Уверенность]",  # alias retained for backward compatibility with audits
    "[Рекомендация]",
    "[Требует ревью]",
    "[Провайдер]",
    "[Ошибка]",
]


def _format_citations(citations: List[Dict[str, Any]]) -> str:
    if not citations:
        return ""
    parts: List[str] = []
    for citation in citations:
        source = citation.get("source", "?")
        section = citation.get("section", "")
        quote = citation.get("quote", "")
        chunk = f"{source}"
        if section:
            chunk += f" / {section}"
        if quote:
            chunk += f": «{quote}»"
        parts.append(chunk)
    return "\n".join(parts)


def _classification_row(item: Dict[str, Any]) -> Dict[str, Any]:
    classification = item.get("classification") or {}
    confidence = float(classification.get("confidence", 0.0) or 0.0)
    return {
        "[Статус]": classification.get("classification", "НД"),
        "[Комментарий]": classification.get("reasoning", ""),
        "[Цитаты]": _format_citations(classification.get("citations", [])),
        "[Confidence]": confidence,
        "[Уверенность]": confidence,
        "[Рекомендация]": classification.get("recommendations", ""),
        "[Требует ревью]": "Да" if classification.get("requires_ba_review") else "Нет",
        "[Провайдер]": classification.get("provider", ""),
        "[Ошибка]": item.get("error", ""),
    }


def save_results(
    results: Iterable[Dict[str, Any]],
    output_file: Union[str, Path],
    sheet_name: str = "Results",
    source_file: Optional[Union[str, Path]] = None,
    run_id: Optional[str] = None,
) -> Path:
    """Persist classification results to an Excel workbook.

    Args:
        results: Iterable of dicts produced by :func:`src.pipeline.run_analysis`.
            Each dict carries the original ``id``/``text`` plus a
            ``classification`` payload (see ``LLMClient.classify_requirement``).
        output_file: Destination ``.xlsx`` path.
        sheet_name: Worksheet name to write to.
        source_file: Optional input workbook path. When supplied, the exporter
            preserves the source columns and appends the classification
            columns next to them (row order is matched by 1-based ``id``).
        run_id: Optional pipeline run identifier. Stored as a worksheet-level
            metadata column ``[run_id]`` if provided.

    Returns:
        The absolute path of the saved workbook.
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to export results. Install it with `pip install pandas openpyxl`."
        ) from exc

    results_list: List[Dict[str, Any]] = list(results)
    classification_rows = [_classification_row(item) for item in results_list]

    source_df = _load_source_dataframe(source_file)
    if source_df is not None and not source_df.empty:
        # Match each result back to its source row by 1-based id.
        n = len(source_df)
        empty_row = {col: "" for col in RESULT_COLUMNS}
        empty_row["[Confidence]"] = 0.0
        empty_row["[Уверенность]"] = 0.0
        appended_rows: List[Dict[str, Any]] = [dict(empty_row) for _ in range(n)]
        for item, row in zip(results_list, classification_rows):
            idx = int(item.get("id", 0)) - 1
            if 0 <= idx < n:
                appended_rows[idx] = row
        appended_df = pd.DataFrame(appended_rows, columns=RESULT_COLUMNS)
        merged = pd.concat([source_df.reset_index(drop=True), appended_df], axis=1)
    else:
        # No source workbook supplied — fall back to a minimal results-only sheet.
        minimal_rows = []
        for item, row in zip(results_list, classification_rows):
            minimal_rows.append(
                {
                    "ID": item.get("id"),
                    "Требование": item.get("text"),
                    **row,
                }
            )
        merged = pd.DataFrame(minimal_rows)

    if run_id:
        merged["[run_id]"] = run_id

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_excel(output_path, sheet_name=sheet_name, index=False)
    logger.info("Saved %d rows to %s", len(merged), output_path)
    return output_path


def _load_source_dataframe(source_file: Optional[Union[str, Path]]):
    """Best-effort read of the input ``.xlsx`` to preserve its structure."""
    if not source_file:
        return None
    path = Path(source_file)
    if not path.exists():
        return None
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        return None
    try:
        import pandas as pd  # type: ignore
    except ImportError:  # pragma: no cover
        return None
    try:
        return pd.read_excel(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not preserve structure from %s: %s", path, exc)
        return None
