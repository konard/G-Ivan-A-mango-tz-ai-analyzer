"""Markdown exporter for MVP analysis reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from src.exporters.schema import NormalizedExportRow, REPORT_TABLE_COLUMNS


class MarkdownExporter:
    """Write a new Markdown report with YAML front matter and a 7-column table."""

    output_format = "md"

    def export(
        self,
        rows: Sequence[NormalizedExportRow],
        output_file: str | Path,
        *,
        source_file: str | Path | None = None,
        run_id: str = "",
    ) -> Path:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "run_id": run_id,
            "date": _utc_timestamp(),
            "source": str(source_file) if source_file else "",
            "schema_version": "1.0",
        }
        front_matter = yaml.safe_dump(
            metadata,
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        source_name = Path(source_file).name if source_file else output_path.stem

        lines = [
            "---",
            front_matter,
            "---",
            "",
            f"# Результат анализа ТЗ — {source_name}",
            "",
            _table_header(),
            _table_separator(),
        ]
        lines.extend(_table_row(row) for row in rows)
        lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return output_path


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _table_header() -> str:
    return "| " + " | ".join(REPORT_TABLE_COLUMNS) + " |"


def _table_separator() -> str:
    return "|---:|---|---|---|---|---:|---|"


def _table_row(row: NormalizedExportRow) -> str:
    values = [
        row.id,
        row.ref,
        row.source_text,
        row.status,
        row.comment,
        f"{row.confidence:.2f}",
        row.run_id,
    ]
    return "| " + " | ".join(_escape_table_cell(value) for value in values) + " |"


def _escape_table_cell(value: object) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    text = text.replace("*", "\\*")
    return text.strip()
