"""Input file parsers (Excel, DOCX, etc.) for the TZ analyzer."""

from pathlib import Path

from src.parsers.base_parser import BaseParser, ParserError
from src.parsers.docx_parser import DocxParser, load_requirements as load_docx_requirements
from src.parsers.excel_parser import (
    ExcelParser,
    ExcelParseError,
    load_config,
    load_requirements as load_excel_requirements,
    setup_logging,
)

__all__ = [
    "ExcelParser",
    "DocxParser",
    "load_excel_requirements",
    "load_docx_requirements",
    "load_requirements_by_extension",
    "load_requirements",
    "parser_for_extension",
    "load_config",
    "setup_logging",
    "BaseParser",
    "ParserError",
    "ExcelParseError",
]


def parser_for_extension(
    file_path: str | Path,
    *,
    config_path: str | None = None,
    run_id: str | None = None,
) -> BaseParser:
    """Return the parser object matching the input file extension."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in {".xlsx", ".xls"}:
        return ExcelParser(sheet_name=None, config_path=config_path, run_id=run_id)
    if ext == ".docx":
        return DocxParser(config_path=config_path)
    raise NotImplementedError(
        f"Unsupported file extension: {ext or '<none>'}. "
        "Please convert the input file to .docx and retry."
    )


def load_requirements_by_extension(
    file_path: str | Path,
    config_path: str | None = None,
    run_id: str | None = None,
) -> list:
    """Load requirements from a file based on its extension.

    Args:
        file_path: Path to the input file (.xlsx or .docx).
        config_path: Путь к файлу конфигурации (опционально).

    Returns:
        A list of dictionaries shaped as ``{"id": int, "text": str, "locator": dict}``.

    Raises:
        NotImplementedError: If the file extension is not supported.
        FileNotFoundError: If the file does not exist.
    """
    parser = parser_for_extension(file_path, config_path=config_path, run_id=run_id)
    return parser.load_requirements(file_path)


def load_requirements(
    file_path: str | Path,
    config_path: str | None = None,
    run_id: str | None = None,
) -> list:
    """Backward-compatible alias for the extension dispatcher."""
    return load_requirements_by_extension(
        file_path, config_path=config_path, run_id=run_id
    )
