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
        {
            "id": 1,
            "text": "Поддержка SIP-телефонии",
            "locator": {
                "type": "cell",
                "sheet_name": "Sheet1",
                "row": 2,
                "column": "Требование",
            },
        },
        {
            "id": 2,
            "text": "Интеграция с CRM",
            "locator": {
                "type": "cell",
                "sheet_name": "Sheet1",
                "row": 3,
                "column": "Требование",
            },
        },
    ]


def test_load_requirements_fallback_column(tmp_path: Path) -> None:
    file_path = _write_xlsx(
        tmp_path / "tz.xlsx",
        pd.DataFrame({"Описание задачи": ["Запись звонков", "Аналитика"]}),
    )
    items = load_requirements(file_path)
    assert [it["text"] for it in items] == ["Запись звонков", "Аналитика"]
    assert all(it["locator"]["column"] == "Описание задачи" for it in items)


def test_load_requirements_fallback_prefers_rich_text_over_numbering(
    tmp_path: Path,
) -> None:
    file_path = _write_xlsx(
        tmp_path / "tz.xlsx",
        pd.DataFrame(
            {
                "Unnamed: 0": ["1.1", "1.2", "1.3"],
                "Нестандартный столбец": [
                    "Программируемый робот",
                    "Генерируемые сообщения",
                    "Поддержка интеграций",
                ],
            }
        ),
    )

    items = load_requirements(file_path)

    assert [it["text"] for it in items] == [
        "Программируемый робот",
        "Генерируемые сообщения",
        "Поддержка интеграций",
    ]
    assert all(it["locator"]["column"] == "Нестандартный столбец" for it in items)


def test_load_requirements_reads_all_sheets_with_locators(tmp_path: Path) -> None:
    file_path = tmp_path / "multi-sheet.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame({"Требование": ["Поддержка SIP"]}).to_excel(
            writer, sheet_name="Основной", index=False
        )
        pd.DataFrame({"Requirement": ["CRM integration"]}).to_excel(
            writer, sheet_name="Second", index=False
        )

    items = load_requirements(file_path, sheet_name=None)

    assert [it["text"] for it in items] == ["Поддержка SIP", "CRM integration"]
    assert [it["locator"]["sheet_name"] for it in items] == ["Основной", "Second"]
    assert all(it["locator"]["row"] == 2 for it in items)


def test_sample_tz_2_reads_all_fixture_sheets_with_locators() -> None:
    items = load_requirements(Path("test_data/sample_tz-2.xlsx"), sheet_name=None)

    sheet_names = {item["locator"]["sheet_name"] for item in items}
    assert {"Чек-лист", "АБТ запись", "АБТ телемед", "РГС"} <= sheet_names
    assert len(items) > 100
    assert all(item["locator"]["type"] == "cell" for item in items)


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
