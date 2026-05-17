"""In-memory export helpers for UI downloads."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

from src.llm.masking import mask_text

DEFAULT_EXPORT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "export_config.yaml"


def load_excel_columns(config_path: Path = DEFAULT_EXPORT_CONFIG_PATH) -> List[str]:
    """Return the strict Excel export column allow-list from YAML config."""
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    export_cfg = data.get("export") if isinstance(data, dict) else None
    columns = export_cfg.get("excel_columns") if isinstance(export_cfg, dict) else None
    if not isinstance(columns, list):
        return []
    return [str(column) for column in columns if str(column).strip()]


def export_to_excel(dataframe: Any, columns: Sequence[str] | None = None) -> BytesIO:
    """Serialize a masked, strictly column-filtered dataframe to ``BytesIO``."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to export Excel files. Install pandas and openpyxl."
        ) from exc

    if not isinstance(dataframe, pd.DataFrame):
        dataframe = pd.DataFrame(dataframe)

    allowed_columns = list(columns) if columns is not None else load_excel_columns()
    filtered = dataframe.reindex(columns=allowed_columns)
    mapper = getattr(filtered, "map", None) or getattr(filtered, "applymap")
    masked = mapper(_mask_cell)

    buffer = BytesIO()
    masked.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


def export_chat_to_markdown(history: Sequence[Dict[str, Any]]) -> BytesIO:
    """Serialize chat history as masked Markdown question/answer blocks."""
    blocks: List[str] = []
    pending_question = ""
    for message in history:
        role = str(message.get("role", "")).lower()
        content = mask_text(str(message.get("content", "")).strip())
        if not content:
            continue
        if role == "user":
            if pending_question:
                blocks.append(f"### Вопрос\n{pending_question}")
            pending_question = content
        elif role == "assistant":
            if pending_question:
                blocks.append(f"### Вопрос\n{pending_question}")
                pending_question = ""
            blocks.append(f"### Ответ\n{content}")

    if pending_question:
        blocks.append(f"### Вопрос\n{pending_question}")

    markdown = "\n\n".join(blocks).strip()
    buffer = BytesIO(markdown.encode("utf-8-sig"))
    buffer.seek(0)
    return buffer


def _mask_cell(value: Any) -> Any:
    if value is None:
        return value
    return mask_text(str(value))
