"""Excel parser for tender requirements (ТЗ).

Reads an .xlsx workbook and extracts a list of atomic requirements from the
"Требование" column (or the first non-empty textual column as a fallback).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.parsers.base_parser import BaseParser

try:
    import pandas as pd
    import yaml
except ImportError as exc:  # pragma: no cover - import guarded for environments without pandas
    pd = None  # type: ignore[assignment]
    yaml = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

logger = logging.getLogger(__name__)

REQUIREMENT_COLUMN_CANDIDATES_DEFAULT = [
    "Требование",
    "требование",
    "Requirement",
    "requirement",
    "Текст требования",
    "Описание",
    "Поля, обязательные для заполнения",
    "Суть",
    "Наименование",
    "Description",
]


class JsonFormatter(logging.Formatter):
    """Форматтер логов в JSON c полем ``run_id`` (если оно есть на записи)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        run_id = getattr(record, "run_id", None)
        if run_id:
            log_entry["run_id"] = run_id
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_json: bool = True,
    run_id: Optional[str] = None,
) -> None:
    """Настроить корневой логгер.

    Используется только когда парсер вызывают самостоятельно (без пайплайна).
    Когда :func:`load_requirements` вызывается из ``src.pipeline.run_analysis``,
    логирование уже сконфигурировано (``configure_json_logging``), поэтому здесь
    важно НЕ сбрасывать обработчики автоматически.
    """
    logger_root = logging.getLogger()
    logger_root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger_root.handlers.clear()

    formatter: logging.Formatter
    if use_json:
        formatter = JsonFormatter()
    else:
        run_id_marker = f"[run_id:{run_id}] " if run_id else ""
        formatter = logging.Formatter(
            f"%(asctime)s - %(name)s - %(levelname)s - {run_id_marker}%(message)s"
        )

    handler: logging.Handler
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, encoding="utf-8")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    logger_root.addHandler(handler)


def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Загрузить конфигурацию из YAML файла.

    Args:
        config_path: Путь к файлу конфигурации. По умолчанию ищет configs/parsing_config.yaml.

    Returns:
        Словарь с конфигурацией.

    Raises:
        FileNotFoundError: Если файл конфигурации не найден.
        ExcelParseError: Если не удалось загрузить зависимости для чтения YAML.
    """
    if yaml is None:  # pragma: no cover - defensive
        raise ExcelParseError(
            "PyYAML is required to load configuration. Install it with `pip install pyyaml`."
        ) from _IMPORT_ERROR

    if config_path is None:
        # Поиск конфига относительно корня проекта
        possible_paths = [
            Path("configs/parsing_config.yaml"),
            Path(__file__).parent.parent / "configs" / "parsing_config.yaml",
        ]
        for p in possible_paths:
            if p.exists():
                config_path = p
                break
        else:
            # Возвращаем конфигурацию по умолчанию, если файл не найден
            logging.warning("Config file not found, using defaults.")
            return {
                "allowed_extensions": [".xlsx", ".xls", ".docx"],
                "column_keywords": REQUIREMENT_COLUMN_CANDIDATES_DEFAULT,
                "text_processing": {
                    "trim": True,
                    "lowercase": False,
                    "remove_empty": True,
                    "min_length": 5,
                },
                "logging": {"level": "INFO", "format": "json", "output": "logs/parser.log"},
                "incoming_dir": "data/incoming",
            }

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


class ExcelParseError(RuntimeError):
    """Raised when the Excel file cannot be parsed into requirements."""

    def __init__(self, message: str, run_id: Optional[str] = None):
        super().__init__(message)
        self.run_id = run_id


def _ensure_pandas() -> None:
    if pd is None:  # pragma: no cover - defensive
        raise ExcelParseError(
            "pandas is required to parse Excel files. Install it with "
            "`pip install pandas openpyxl`."
        ) from _IMPORT_ERROR


def _detect_requirement_column(
    df: "pd.DataFrame",
    keywords: Optional[List[str]] = None,
    *,
    log_extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Return the column name to use as the source of requirement text."""
    if keywords is None:
        keywords = REQUIREMENT_COLUMN_CANDIDATES_DEFAULT

    for candidate in keywords:
        if candidate in df.columns:
            return candidate

    # Fallback: the richest text column. Real tender sheets often put numbering
    # before descriptions, so picking the first textual column loses data.
    best_column: Optional[str] = None
    best_score: tuple[int, float] = (0, 0.0)
    for column in df.columns:
        series = df[column].dropna()
        if series.empty:
            continue
        values = [
            str(value).strip()
            for value in series.tolist()
            if str(value).strip() and str(value).strip().lower() != "nan"
        ]
        valid_values = [
            value for value in values if len(value) >= BaseParser.DEFAULT_MIN_LENGTH
        ]
        if not valid_values:
            continue
        score = (
            len(valid_values),
            sum(len(value) for value in valid_values) / len(valid_values),
        )
        if score > best_score:
            best_score = score
            best_column = str(column)

    if best_column is not None:
        logger.warning(
            "No standard requirement column found; using fallback column '%s'.",
            best_column,
            extra=log_extra or {},
        )
        return best_column

    raise ExcelParseError(
        "No requirement column found. Expected one of: " + ", ".join(keywords)
    )


def _sheet_display_name(workbook: "pd.ExcelFile", sheet_ref: Union[str, int]) -> str:
    if isinstance(sheet_ref, int):
        try:
            return str(workbook.sheet_names[sheet_ref])
        except IndexError:
            return str(sheet_ref)
    return str(sheet_ref)


def _read_sheet_frames(
    path: Path,
    sheet_name: Optional[Union[str, int]],
    *,
    log_extra: Dict[str, Any],
    run_id: Optional[str],
) -> List[Tuple[str, "pd.DataFrame"]]:
    try:
        workbook = pd.ExcelFile(path)
    except Exception as exc:  # pandas wraps many parser errors
        logger.error("Failed to read Excel file %s: %s", path, exc, extra=log_extra)
        raise ExcelParseError(f"Failed to read Excel file {path}: {exc}", run_id) from exc

    sheet_refs: List[Union[str, int]]
    if sheet_name is None:
        sheet_refs = list(workbook.sheet_names)
    else:
        sheet_refs = [sheet_name]

    frames: List[Tuple[str, "pd.DataFrame"]] = []
    try:
        for sheet_ref in sheet_refs:
            try:
                df = pd.read_excel(workbook, sheet_name=sheet_ref)
            except Exception as exc:  # pandas wraps many parser errors
                logger.error(
                    "Failed to read Excel sheet %s in %s: %s",
                    sheet_ref,
                    path,
                    exc,
                    extra=log_extra,
                )
                raise ExcelParseError(
                    f"Failed to read Excel sheet {sheet_ref!r} in {path}: {exc}",
                    run_id,
                ) from exc
            frames.append((_sheet_display_name(workbook, sheet_ref), df))
    finally:
        workbook.close()
    return frames


def load_requirements(
    file_path: Union[str, Path],
    sheet_name: Optional[Union[str, int]] = 0,
    column: Optional[str] = None,
    config_path: Optional[Union[str, Path]] = None,
    run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load tender requirements from an Excel workbook.

    Args:
        file_path: Path to the .xlsx file.
        sheet_name: Sheet name or index. Defaults to the first sheet.
        column: Explicit requirement column name. If omitted, the parser tries
            the standard names listed in :data:`REQUIREMENT_COLUMN_CANDIDATES_DEFAULT`.
        config_path: Путь к файлу конфигурации. Если не указан, используется конфиг по умолчанию.
        run_id: Идентификатор сессии (UUID4) — добавляется во все JSON-логи как
            поле ``run_id`` и пробрасывается в :class:`ExcelParseError`. Когда
            парсер вызывается из ``src.pipeline.run_analysis``, ``run_id``
            берётся из пайплайна, что обеспечивает сквозную трассировку.

    Returns:
        A list of dictionaries shaped as ``{"id": int, "text": str, "locator": dict}``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ExcelParseError: If the file cannot be read or contains no requirements.
    """
    _ensure_pandas()

    config = load_config(config_path)
    log_extra: Dict[str, Any] = {"run_id": run_id} if run_id else {}

    path = Path(file_path)
    if not path.exists():
        logger.error("Excel file not found: %s", path, extra=log_extra)
        raise FileNotFoundError(f"Excel file not found: {path}")
    if path.stat().st_size == 0:
        logger.error("Excel file is empty: %s", path, extra=log_extra)
        raise ExcelParseError(f"Excel file is empty: {path}", run_id)

    keywords = config.get("column_keywords", REQUIREMENT_COLUMN_CANDIDATES_DEFAULT)
    text_config = config.get("text_processing", {})
    do_trim = text_config.get("trim", True)
    do_lowercase = text_config.get("lowercase", False)
    remove_empty = text_config.get("remove_empty", True)
    min_length = text_config.get("min_length", 5)

    sheet_frames = _read_sheet_frames(
        path, sheet_name, log_extra=log_extra, run_id=run_id
    )

    requirements: List[Dict[str, Any]] = []
    for current_sheet_name, df in sheet_frames:
        if df.empty:
            logger.warning(
                "Excel sheet is empty: %s!%s", path, current_sheet_name, extra=log_extra
            )
            continue

        target_column = column or _detect_requirement_column(
            df, keywords, log_extra=log_extra
        )
        if target_column not in df.columns:
            logger.error(
                "Column '%s' is not present in %s!%s. Available columns: %s",
                target_column,
                path,
                current_sheet_name,
                list(df.columns),
                extra=log_extra,
            )
            raise ExcelParseError(
                f"Column '{target_column}' is not present in {path}!{current_sheet_name}. "
                f"Available columns: {list(df.columns)}",
                run_id,
            )

        for row_number, raw_value in enumerate(df[target_column].tolist(), start=2):
            if raw_value is None:
                continue
            text = str(raw_value)
            if do_trim:
                text = text.strip()
            if do_lowercase:
                text = text.lower()
            if remove_empty and (not text or text.lower() == "nan"):
                continue
            if len(text) >= min_length:
                requirements.append(
                    {
                        "id": len(requirements) + 1,
                        "text": text,
                        "locator": {
                            "type": "cell",
                            "sheet_name": current_sheet_name,
                            "row": row_number,
                            "column": str(target_column),
                        },
                    }
                )
                continue
            logger.warning(
                "Requirement in %s!%s row %d is too short (%d chars), skipping: %s",
                path,
                current_sheet_name,
                row_number,
                len(text),
                text[:50],
                extra=log_extra,
            )

    if not requirements:
        logger.error(
            "Excel workbook %s does not contain any valid requirements.",
            path,
            extra=log_extra,
        )
        raise ExcelParseError(
            f"Excel workbook {path} does not contain any non-empty values.",
            run_id,
        )

    logger.info(
        "Loaded %d requirements from %s", len(requirements), path, extra=log_extra
    )
    return requirements


class ExcelParser(BaseParser):
    """Parser object used by the extension dispatcher."""

    def __init__(
        self,
        *,
        sheet_name: Optional[Union[str, int]] = 0,
        column: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None,
        run_id: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.sheet_name = sheet_name
        self.column = column
        self.config_path = config_path
        self.run_id = run_id

    def load_requirements(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        return load_requirements(
            file_path,
            sheet_name=self.sheet_name,
            column=self.column,
            config_path=self.config_path,
            run_id=self.run_id,
        )
