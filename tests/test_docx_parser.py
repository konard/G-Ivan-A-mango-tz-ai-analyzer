import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

docx = pytest.importorskip("docx")

from src.parsers import load_requirements_by_extension  # noqa: E402
from src.parsers.docx_parser import DocxParser  # noqa: E402


def _write_docx(path: Path) -> Path:
    document = docx.Document()
    document.add_paragraph("Обеспечить запись звонков")
    document.add_paragraph("")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "ID"
    cell = table.cell(0, 1)
    cell.text = "Поддержать интеграцию с CRM"
    cell.add_paragraph("Настроить очередь входящих звонков")
    document.save(path)
    return path


def test_docx_parser_extracts_paragraphs_tables_and_locators(tmp_path: Path) -> None:
    file_path = _write_docx(tmp_path / "tz.docx")

    items = DocxParser().load_requirements(file_path)

    assert [item["text"] for item in items] == [
        "Обеспечить запись звонков",
        "Поддержать интеграцию с CRM",
        "Настроить очередь входящих звонков",
    ]
    assert all(item["locator"] for item in items)
    assert items[0]["locator"] == {"type": "paragraph", "index": 1}
    assert items[1]["locator"]["type"] == "table"
    assert items[1]["locator"]["row"] == 1
    assert items[1]["locator"]["col"] == 2
    assert items[2]["locator"]["type"] == "table"
    assert items[2]["locator"]["paragraph"] == 2


def test_docx_parser_sample_file_preserves_table_traceability() -> None:
    items = DocxParser().load_requirements(Path("test_data/sample_tz_1.DOCX"))

    assert items
    assert all(item.get("locator") for item in items)
    table_items = [item for item in items if item["locator"]["type"] == "table"]
    assert table_items
    assert any("Бесперебойную запись пациентов" in item["text"] for item in table_items)


def test_dispatcher_routes_xlsx_docx_and_rejects_unknown(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "tz.xlsx"
    pd = pytest.importorskip("pandas")
    pd.DataFrame({"Требование": ["Поддержка аналитики"]}).to_excel(
        xlsx_path, index=False
    )
    docx_path = _write_docx(tmp_path / "tz.docx")

    assert load_requirements_by_extension(xlsx_path)[0]["text"] == "Поддержка аналитики"
    assert (
        load_requirements_by_extension(docx_path)[0]["text"]
        == "Обеспечить запись звонков"
    )
    with pytest.raises(NotImplementedError, match="convert.*\\.docx"):
        load_requirements_by_extension(tmp_path / "legacy.doc")
