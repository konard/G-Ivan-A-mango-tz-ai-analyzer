"""Excel exporter for classification results.

Per issue #45 MUST 4 (FR-06): the output workbook preserves the original ТЗ
columns and appends **exactly four** result columns, in this order::

    [Статус], [Комментарий], [Confidence], [RunID]

The fourth functional column ``[RunID]`` carries the pipeline ``run_id`` on
every row so the UI can filter / re-run only errored rows without needing the
user to re-upload the source file.

Operational columns ([Цитаты], [Уверенность], [Рекомендация], [Требует ревью],
[Провайдер], [Ошибка]) that were emitted in pre-MVP revisions are intentionally
dropped — the MVP is a read-only review surface (no inline edit, no extended
audit columns).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)

RESULT_COLUMNS: List[str] = [
    "[Статус]",
    "[Комментарий]",
    "[Confidence]",
    "[RunID]",
]


def _classification_row(item: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    classification = item.get("classification") or {}
    confidence = float(classification.get("confidence", 0.0) or 0.0)
    return {
        "[Статус]": classification.get("classification", "НД"),
        "[Комментарий]": classification.get("reasoning", ""),
        "[Confidence]": confidence,
        "[RunID]": run_id,
    }


def _empty_row(run_id: str) -> Dict[str, Any]:
    return {
        "[Статус]": "",
        "[Комментарий]": "",
        "[Confidence]": 0.0,
        "[RunID]": run_id,
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
            preserves the source columns and appends the four MVP columns next
            to them (row order is matched by 1-based ``id``).
        run_id: Pipeline run identifier. Written into ``[RunID]`` on every row
            so the UI's retry-only-errors workflow can filter without re-upload.

    Returns:
        The absolute path of the saved workbook.
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to export results. Install it with `pip install pandas openpyxl`."
        ) from exc

    run_id = run_id or ""
    results_list: List[Dict[str, Any]] = list(results)
    classification_rows = [_classification_row(item, run_id) for item in results_list]

    source_df = _load_source_dataframe(source_file)
    if source_df is not None and not source_df.empty:
        n = len(source_df)
        appended_rows: List[Dict[str, Any]] = [_empty_row(run_id) for _ in range(n)]
        for item, row in zip(results_list, classification_rows):
            idx = int(item.get("id", 0)) - 1
            if 0 <= idx < n:
                appended_rows[idx] = row
        appended_df = pd.DataFrame(appended_rows, columns=RESULT_COLUMNS)
        merged = pd.concat([source_df.reset_index(drop=True), appended_df], axis=1)
    else:
        minimal_rows: List[Dict[str, Any]] = []
        for item, row in zip(results_list, classification_rows):
            minimal_rows.append(
                {
                    "ID": item.get("id"),
                    "Требование": item.get("text"),
                    **row,
                }
            )
        merged = pd.DataFrame(minimal_rows)

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
