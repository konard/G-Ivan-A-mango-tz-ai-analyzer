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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from src.exporters.schema import (
    NormalizedExportRow,
    RESULT_COLUMNS,
    rows_from_results,
)

logger = logging.getLogger(__name__)


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
    rows = rows_from_results(results, run_id=run_id or "")
    return save_export_rows(
        rows,
        output_file,
        sheet_name=sheet_name,
        source_file=source_file,
        run_id=run_id,
    )


def save_export_rows(
    rows: Sequence[NormalizedExportRow],
    output_file: Union[str, Path],
    sheet_name: str = "Results",
    source_file: Optional[Union[str, Path]] = None,
    run_id: Optional[str] = None,
) -> Path:
    """Persist normalized export rows to an Excel workbook."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to export results. Install it with `pip install pandas openpyxl`."
        ) from exc

    run_id = run_id or _run_id_from_rows(rows)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_workbook = _load_source_workbook(source_file)
    if source_workbook:
        with pd.ExcelWriter(output_path) as writer:
            for current_sheet_name, source_df in source_workbook.items():
                merged = _merge_source_sheet(
                    source_df,
                    current_sheet_name=current_sheet_name,
                    rows=rows,
                    run_id=run_id,
                    single_sheet=len(source_workbook) == 1,
                )
                merged.to_excel(writer, sheet_name=current_sheet_name, index=False)
        logger.info("Saved %d sheets to %s", len(source_workbook), output_path)
        return output_path

    minimal_rows: List[Dict[str, Any]] = []
    for row in rows:
        minimal_rows.append(
            {
                "ID": row.id,
                "Требование": row.source_text,
                **row.mvp_values(),
            }
        )
    merged = pd.DataFrame(minimal_rows)
    merged.to_excel(output_path, sheet_name=sheet_name, index=False)
    logger.info("Saved %d rows to %s", len(merged), output_path)
    return output_path


def _load_source_dataframe(source_file: Optional[Union[str, Path]]):
    """Best-effort read of the input ``.xlsx`` to preserve its structure."""
    workbook = _load_source_workbook(source_file)
    if not workbook:
        return None
    return next(iter(workbook.values()))


def _load_source_workbook(
    source_file: Optional[Union[str, Path]]
) -> Optional[Mapping[str, Any]]:
    """Best-effort read of the input workbook to preserve all sheets."""
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
        workbook = pd.read_excel(path, sheet_name=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not preserve structure from %s: %s", path, exc)
        return None
    if not isinstance(workbook, dict):
        return None
    return workbook


def _merge_source_sheet(
    source_df: Any,
    *,
    current_sheet_name: str,
    rows: Sequence[NormalizedExportRow],
    run_id: str,
    single_sheet: bool,
):
    import pandas as pd  # type: ignore

    n = len(source_df)
    appended_rows: List[Dict[str, Any]] = [_empty_row(run_id) for _ in range(n)]
    for row in rows:
        row_index = _source_row_index_for_sheet(
            row,
            current_sheet_name=current_sheet_name,
            single_sheet=single_sheet,
        )
        if row_index is None:
            continue
        if 0 <= row_index < n:
            appended_rows[row_index] = row.mvp_values()
    appended_df = pd.DataFrame(appended_rows, columns=RESULT_COLUMNS)
    return pd.concat([source_df.reset_index(drop=True), appended_df], axis=1)


def _source_row_index_for_sheet(
    row: NormalizedExportRow,
    *,
    current_sheet_name: str,
    single_sheet: bool,
) -> Optional[int]:
    locator = row.locator or {}
    locator_sheet = locator.get("sheet_name") or locator.get("sheet")
    if locator_sheet:
        if str(locator_sheet) != str(current_sheet_name):
            return None
        try:
            return int(locator.get("row")) - 2
        except (TypeError, ValueError):
            return None
    if single_sheet:
        return row.id - 1
    return None


def _run_id_from_rows(rows: Sequence[NormalizedExportRow]) -> str:
    for row in rows:
        if row.run_id:
            return row.run_id
    return ""
