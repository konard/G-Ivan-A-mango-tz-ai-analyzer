from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from src.exporters import ExportRouter


RUN_ID = "abcdef0123456789abcdef0123456789"


def _sample_results() -> list[dict]:
    return [
        {
            "id": 1,
            "text": "Поддержка SIP | запись\nи *аналитика*",
            "locator": {
                "type": "cell",
                "sheet_name": "ТЗ",
                "row": 2,
                "column": "Требование",
            },
            "classification": {
                "classification": "Да",
                "reasoning": "Есть | подтверждение\nв *документации*.",
                "confidence": 0.913,
            },
        },
        {
            "id": 2,
            "text": "Сломанное требование",
            "locator": {"type": "paragraph", "index": 3},
            "classification": {
                "classification": "Ошибка",
                "reasoning": "Ошибка обработки.",
                "confidence": 0.0,
            },
        },
    ]


def test_router_exports_markdown_with_front_matter_table_and_template_name(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "sample_tz.xlsx"
    source_file.write_bytes(b"placeholder")

    output = ExportRouter().export(
        _sample_results(),
        output_format="md",
        output_dir=tmp_path,
        source_file=source_file,
        run_id=RUN_ID,
    )

    assert output.name == "sample_tz_report_abcdef01.md"
    rendered = output.read_text(encoding="utf-8")
    assert rendered.startswith("---\n")
    front_matter = rendered.split("---", 2)[1]
    metadata = yaml.safe_load(front_matter)
    assert metadata["run_id"] == RUN_ID
    assert metadata["source"] == str(source_file)
    assert metadata["schema_version"] == "1.0"
    assert (
        "| № | Ref | Исходное требование | [Статус] | [Комментарий] | [Confidence] | [RunID] |"
        in rendered
    )
    assert "Поддержка SIP \\| запись<br>и \\*аналитика\\*" in rendered
    assert "Есть \\| подтверждение<br>в \\*документации\\*." in rendered
    assert "| 2 | paragraph=3 | Сломанное требование | Ошибка |" in rendered


def test_router_exports_docx_table_without_modifying_source(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    source_file = tmp_path / "sample_tz.docx"
    source_document = docx.Document()
    source_document.add_paragraph("Поддержка SIP")
    source_document.save(source_file)
    source_hash_before = hashlib.sha256(source_file.read_bytes()).hexdigest()

    output = ExportRouter().export(
        _sample_results(),
        output_format="docx",
        output_dir=tmp_path,
        source_file=source_file,
        run_id=RUN_ID,
    )

    assert output.name == "sample_tz_report_abcdef01.docx"
    assert hashlib.sha256(source_file.read_bytes()).hexdigest() == source_hash_before

    report = docx.Document(str(output))
    assert report.paragraphs[0].text.startswith("Результат анализа ТЗ")
    assert report.tables
    table = report.tables[0]
    assert [cell.text for cell in table.rows[0].cells] == [
        "№",
        "Ref",
        "Исходное требование",
        "[Статус]",
        "[Комментарий]",
        "[Confidence]",
        "[RunID]",
    ]
    assert table.rows[1].cells[1].text == 'sheet="ТЗ", row=2, col="Требование"'
    assert table.rows[1].cells[2].text == "Поддержка SIP | запись\nи *аналитика*"
    assert table.rows[1].cells[6].text == RUN_ID


def test_router_rejects_append_to_original_mode_by_default(tmp_path: Path) -> None:
    source_file = tmp_path / "sample_tz.xlsx"
    source_file.write_bytes(b"placeholder")

    with pytest.raises(ValueError, match="append_to_original"):
        ExportRouter().export(
            _sample_results(),
            output_format="md",
            output_dir=tmp_path,
            source_file=source_file,
            run_id=RUN_ID,
            output_mode="append_to_original",
        )
