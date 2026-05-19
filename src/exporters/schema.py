"""Shared export schema and formatting helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESULT_COLUMNS: List[str] = [
    "[Статус]",
    "[Комментарий]",
    "[Confidence]",
    "[RunID]",
]

REPORT_TABLE_COLUMNS: List[str] = [
    "№",
    "Ref",
    "Исходное требование",
    *RESULT_COLUMNS,
]

STATUS_VALUES = {"Да", "Нет", "Частично", "НД", "Ошибка"}


class NormalizedExportRow(BaseModel):
    """Internal MVP export row used by concrete writer adapters.

    The public aliases intentionally match the MVP export markup columns.
    ``locator`` remains structured so adapters can use it for routing, while
    ``ref`` is the human-readable representation written to docx/md reports.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: int = Field(ge=1)
    ref: str = ""
    source_text: str = Field(alias="Исходное требование")
    locator: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(alias="[Статус]")
    comment: str = Field(alias="[Комментарий]")
    confidence: float = Field(alias="[Confidence]", ge=0.0, le=1.0)
    run_id: str = Field(alias="[RunID]")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = str(value or "НД").strip() or "НД"
        if normalized not in STATUS_VALUES:
            raise ValueError(
                "status must be one of: " + ", ".join(sorted(STATUS_VALUES))
            )
        return normalized

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: Any) -> float:
        try:
            return round(float(value or 0.0), 2)
        except (TypeError, ValueError):
            return 0.0

    @field_validator("ref", mode="before")
    @classmethod
    def _normalize_ref(cls, value: Any) -> str:
        return str(value or "")

    def mvp_values(self) -> Dict[str, Any]:
        return {
            "[Статус]": self.status,
            "[Комментарий]": self.comment,
            "[Confidence]": self.confidence,
            "[RunID]": self.run_id,
        }


def rows_from_results(
    results: Iterable[Mapping[str, Any] | NormalizedExportRow],
    *,
    run_id: str = "",
) -> List[NormalizedExportRow]:
    """Convert pipeline result dictionaries into validated export rows."""
    rows: List[NormalizedExportRow] = []
    for index, item in enumerate(results, start=1):
        if isinstance(item, NormalizedExportRow):
            row = item if item.run_id or not run_id else item.model_copy(
                update={"run_id": run_id}
            )
            if not row.ref:
                row = row.model_copy(update={"ref": format_locator(row.locator)})
            rows.append(row)
            continue

        if _looks_like_export_row(item):
            payload = dict(item)
            if run_id and not payload.get("[RunID]") and not payload.get("run_id"):
                payload["[RunID]"] = run_id
            payload.setdefault("ref", format_locator(payload.get("locator") or {}))
            rows.append(NormalizedExportRow.model_validate(payload))
            continue

        classification = item.get("classification") or {}
        error = item.get("error")
        status = classification.get("classification")
        comment = classification.get("reasoning")
        if error and not status:
            status = "Ошибка"
            comment = f"Ошибка обработки: {error}"

        locator = dict(item.get("locator") or {})
        row = NormalizedExportRow(
            id=int(item.get("id") or index),
            ref=format_locator(locator),
            source_text=str(item.get("text") or item.get("Требование") or ""),
            locator=locator,
            status=str(status or "НД"),
            comment=str(comment or ""),
            confidence=classification.get("confidence", 0.0),
            run_id=str(run_id or item.get("run_id") or ""),
        )
        rows.append(row)
    return rows


def ensure_export_rows(
    rows: Sequence[Mapping[str, Any] | NormalizedExportRow],
    *,
    run_id: str = "",
) -> List[NormalizedExportRow]:
    return rows_from_results(rows, run_id=run_id)


def format_locator(locator: Mapping[str, Any] | None) -> str:
    """Render parser locator metadata as a stable ``Ref`` string."""
    if not locator:
        return ""

    locator_type = str(locator.get("type") or "").strip().lower()
    if locator_type == "cell":
        parts: List[str] = []
        sheet = locator.get("sheet_name") or locator.get("sheet")
        if sheet:
            parts.append(f'sheet="{_quote(sheet)}"')
        if locator.get("row") is not None:
            parts.append(f"row={locator.get('row')}")
        column = locator.get("column") or locator.get("col")
        if column:
            parts.append(f'col="{_quote(column)}"')
        return ", ".join(parts)

    if locator_type == "paragraph":
        index = locator.get("index", locator.get("para_index"))
        parts = [f"paragraph={index}"] if index is not None else ["paragraph"]
        if locator.get("fragment") is not None:
            parts.append(f"fragment={locator.get('fragment')}")
        if locator.get("list_path"):
            parts.append(f'list_path="{_quote(_join_list_path(locator["list_path"]))}"')
        return ", ".join(parts)

    if locator_type == "table":
        ordered_keys = ("table", "row", "col", "paragraph", "fragment")
        parts = [
            f"{key}={locator[key]}"
            for key in ordered_keys
            if locator.get(key) is not None
        ]
        if locator.get("list_path"):
            parts.append(f'list_path="{_quote(_join_list_path(locator["list_path"]))}"')
        return ", ".join(parts)

    return ", ".join(
        f'{key}="{_quote(value)}"' if isinstance(value, str) else f"{key}={value}"
        for key, value in sorted(locator.items())
    )


def _looks_like_export_row(item: Mapping[str, Any]) -> bool:
    keys = set(item)
    return bool(
        {"id", "[Статус]", "[Комментарий]", "[Confidence]", "[RunID]"} <= keys
        or {"id", "status", "comment", "confidence", "run_id"} <= keys
    )


def _join_list_path(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "/".join(str(part) for part in value)
    return str(value)


def _quote(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
