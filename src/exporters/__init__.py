"""Result export router and public export contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Protocol, Sequence

import yaml

from src.exporters.contract import ExportDocument, ExportMetadata, ExportRow
from src.exporters.docx_exporter import DocxExporter
from src.exporters.md_exporter import MarkdownExporter
from src.exporters.schema import (
    NormalizedExportRow,
    RESULT_COLUMNS,
    ensure_export_rows,
    format_locator,
    rows_from_results,
)

DEFAULT_EXPORT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "export_config.yaml"
)


class IExporter(Protocol):
    output_format: str

    def export(
        self,
        rows: Sequence[NormalizedExportRow],
        output_file: str | Path,
        *,
        source_file: str | Path | None = None,
        run_id: str = "",
    ) -> Path:
        ...


class ExcelExporter:
    """Adapter that keeps the legacy Excel implementation behind the router."""

    output_format = "xlsx"

    def export(
        self,
        rows: Sequence[NormalizedExportRow],
        output_file: str | Path,
        *,
        source_file: str | Path | None = None,
        run_id: str = "",
    ) -> Path:
        from src.exporters.excel_exporter import save_export_rows

        return save_export_rows(
            rows,
            output_file,
            source_file=source_file,
            run_id=run_id,
        )


class ExportRouter:
    """Facade selecting an exporter by output format."""

    def __init__(
        self,
        *,
        config_path: str | Path = DEFAULT_EXPORT_CONFIG_PATH,
        exporters: Mapping[str, IExporter] | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = load_export_config(self.config_path)
        export_cfg = self.config.get("export", {})
        if not isinstance(export_cfg, dict):
            export_cfg = {}

        self.default_format = str(export_cfg.get("default_format", "xlsx")).lower()
        self.append_mode = bool(export_cfg.get("append_mode", False))
        self.report_basename_template = str(
            export_cfg.get(
                "report_basename_template",
                "{basename}_report_{run_id_8}.{ext}",
            )
        )
        self._exporters: Dict[str, IExporter] = {}
        self.register_exporter("xlsx", ExcelExporter())
        self.register_exporter("docx", DocxExporter())
        self.register_exporter("md", MarkdownExporter())
        for output_format, exporter in (exporters or {}).items():
            self.register_exporter(output_format, exporter)

    def register_exporter(self, output_format: str, exporter: IExporter) -> None:
        normalized = _normalize_format(output_format)
        if not normalized:
            raise ValueError("output format must not be empty")
        self._exporters[normalized] = exporter

    @property
    def supported_formats(self) -> tuple[str, ...]:
        return tuple(sorted(self._exporters))

    def export(
        self,
        results: Iterable[Mapping[str, Any] | NormalizedExportRow],
        output_file: str | Path | None = None,
        *,
        output_format: str | None = None,
        output_dir: str | Path | None = None,
        source_file: str | Path | None = None,
        run_id: str | None = None,
        output_mode: str = "create_new",
    ) -> Path:
        if output_mode != "create_new":
            if output_mode == "append_to_original":
                raise ValueError(
                    "append_to_original is disabled for production export; "
                    "use create_new reports instead."
                )
            raise ValueError(f"Unsupported output_mode: {output_mode}")

        rows = rows_from_results(results, run_id=run_id or "")
        effective_run_id = run_id or _run_id_from_rows(rows)
        normalized_format = self._resolve_output_format(output_format, output_file)
        exporter = self._exporters.get(normalized_format)
        if exporter is None:
            supported = ", ".join(self.supported_formats)
            raise ValueError(
                f"Unsupported output_format {normalized_format!r}. "
                f"Supported formats: {supported}"
            )

        output_path = self._resolve_output_path(
            output_file=output_file,
            output_dir=output_dir,
            source_file=source_file,
            output_format=normalized_format,
            run_id=effective_run_id,
        )
        return exporter.export(
            rows,
            output_path,
            source_file=source_file,
            run_id=effective_run_id,
        )

    def _resolve_output_format(
        self,
        output_format: str | None,
        output_file: str | Path | None,
    ) -> str:
        if output_format:
            return _normalize_format(output_format)
        if output_file:
            suffix = Path(output_file).suffix
            if suffix:
                return _normalize_format(suffix)
        return _normalize_format(self.default_format)

    def _resolve_output_path(
        self,
        *,
        output_file: str | Path | None,
        output_dir: str | Path | None,
        source_file: str | Path | None,
        output_format: str,
        run_id: str,
    ) -> Path:
        if output_file is not None:
            explicit_path = Path(output_file)
            if explicit_path.suffix and not explicit_path.is_dir():
                return explicit_path
            output_dir = explicit_path

        base_dir = Path(output_dir) if output_dir is not None else None
        if base_dir is None:
            base_dir = Path(source_file).parent if source_file else Path.cwd()

        basename = Path(source_file).stem if source_file else "report"
        filename = self.report_basename_template.format(
            basename=basename,
            run_id_8=(run_id or "")[:8],
            ext=output_format,
        )
        return base_dir / filename


def load_export_config(
    config_path: str | Path = DEFAULT_EXPORT_CONFIG_PATH,
) -> Dict[str, Any]:
    path = Path(config_path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {"export": {}}
    return data if isinstance(data, dict) else {"export": {}}


def _normalize_format(output_format: str | Path) -> str:
    normalized = str(output_format).strip().lower().lstrip(".")
    if normalized == "markdown":
        return "md"
    if normalized == "xls":
        return "xlsx"
    return normalized


def _run_id_from_rows(rows: Sequence[NormalizedExportRow]) -> str:
    for row in rows:
        if row.run_id:
            return row.run_id
    return ""


from src.exporters.excel_exporter import save_results  # noqa: E402

__all__ = [
    "ExportDocument",
    "ExportMetadata",
    "ExportRow",
    "ExportRouter",
    "ExcelExporter",
    "DocxExporter",
    "MarkdownExporter",
    "IExporter",
    "RESULT_COLUMNS",
    "ensure_export_rows",
    "format_locator",
    "load_export_config",
    "rows_from_results",
    "save_results",
]
