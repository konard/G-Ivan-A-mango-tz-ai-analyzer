import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from src.parsers.excel_parser import (  # noqa: E402
    ExcelParseError,
    load_requirements,
)


def _write_xlsx(path: Path, df: "pd.DataFrame") -> Path:
    df.to_excel(path, index=False)
    return path


def test_load_requirements_standard_column(tmp_path: Path) -> None:
    file_path = _write_xlsx(
        tmp_path / "tz.xlsx",
        pd.DataFrame(
            {
                "ID": [1, 2, 3],
                "Требование": [
                    "Поддержка SIP-телефонии",
                    "Интеграция с CRM",
                    "  ",
                ],
            }
        ),
    )
    items = load_requirements(file_path)
    assert items == [
        {"id": 1, "text": "Поддержка SIP-телефонии"},
        {"id": 2, "text": "Интеграция с CRM"},
    ]


def test_load_requirements_fallback_column(tmp_path: Path) -> None:
    file_path = _write_xlsx(
        tmp_path / "tz.xlsx",
        pd.DataFrame({"Описание задачи": ["Запись звонков", "Аналитика"]}),
    )
    items = load_requirements(file_path)
    assert [it["text"] for it in items] == ["Запись звонков", "Аналитика"]


def test_load_requirements_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_requirements(tmp_path / "missing.xlsx")


def test_load_requirements_empty_column(tmp_path: Path) -> None:
    file_path = _write_xlsx(
        tmp_path / "tz.xlsx",
        pd.DataFrame({"Требование": [None, "", "   "]}),
    )
    with pytest.raises(ExcelParseError):
        load_requirements(file_path)
