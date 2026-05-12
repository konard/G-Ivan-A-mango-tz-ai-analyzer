"""Excel parser for tender requirements (ТЗ).

Reads an .xlsx workbook and extracts a list of atomic requirements from the
"Требование" column (or the first non-empty textual column as a fallback).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - import guarded for environments without pandas
    pd = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

logger = logging.getLogger(__name__)

REQUIREMENT_COLUMN_CANDIDATES = (
    "Требование",
    "требование",
    "Requirement",
    "requirement",
    "Текст требования",
    "Описание",
)


class ExcelParseError(RuntimeError):
    """Raised when the Excel file cannot be parsed into requirements."""


def _ensure_pandas() -> None:
    if pd is None:  # pragma: no cover - defensive
        raise ExcelParseError(
            "pandas is required to parse Excel files. Install it with "
            "`pip install pandas openpyxl`."
        ) from _IMPORT_ERROR


def _detect_requirement_column(df: "pd.DataFrame") -> str:
    """Return the column name to use as the source of requirement text."""
    for candidate in REQUIREMENT_COLUMN_CANDIDATES:
        if candidate in df.columns:
            return candidate

    # Fallback: first column whose values are mostly non-empty strings.
    for column in df.columns:
        series = df[column].dropna()
        if series.empty:
            continue
        if series.map(lambda v: isinstance(v, str) and v.strip()).any():
            logger.warning(
                "No standard requirement column found; using fallback column '%s'.",
                column,
            )
            return column

    raise ExcelParseError(
        "No requirement column found. Expected one of: "
        + ", ".join(REQUIREMENT_COLUMN_CANDIDATES)
    )


def load_requirements(
    file_path: Union[str, Path],
    sheet_name: Optional[Union[str, int]] = 0,
    column: Optional[str] = None,
) -> List[Dict[str, Union[int, str]]]:
    """Load tender requirements from an Excel workbook.

    Args:
        file_path: Path to the .xlsx file.
        sheet_name: Sheet name or index. Defaults to the first sheet.
        column: Explicit requirement column name. If omitted, the parser tries
            the standard names listed in :data:`REQUIREMENT_COLUMN_CANDIDATES`.

    Returns:
        A list of dictionaries shaped as ``{"id": int, "text": str}``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ExcelParseError: If the file cannot be read or contains no requirements.
    """
    _ensure_pandas()

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")
    if path.stat().st_size == 0:
        raise ExcelParseError(f"Excel file is empty: {path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except Exception as exc:  # pandas wraps many parser errors
        raise ExcelParseError(f"Failed to read Excel file {path}: {exc}") from exc

    if df.empty:
        raise ExcelParseError(f"Excel sheet is empty: {path}")

    target_column = column or _detect_requirement_column(df)
    if target_column not in df.columns:
        raise ExcelParseError(
            f"Column '{target_column}' is not present in {path}. "
            f"Available columns: {list(df.columns)}"
        )

    requirements: List[Dict[str, Union[int, str]]] = []
    for idx, raw_value in enumerate(df[target_column].tolist(), start=1):
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if not text or text.lower() == "nan":
            continue
        requirements.append({"id": idx, "text": text})

    if not requirements:
        raise ExcelParseError(
            f"Column '{target_column}' in {path} does not contain any non-empty values."
        )

    logger.info("Loaded %d requirements from %s", len(requirements), path)
    return requirements
