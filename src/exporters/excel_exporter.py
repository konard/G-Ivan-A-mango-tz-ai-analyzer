"""Excel exporter for classification results."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

logger = logging.getLogger(__name__)


def _format_citations(citations: List[Dict[str, Any]]) -> str:
    if not citations:
        return ""
    parts: List[str] = []
    for citation in citations:
        source = citation.get("source", "?")
        section = citation.get("section", "")
        quote = citation.get("quote", "")
        chunk = f"{source}"
        if section:
            chunk += f" / {section}"
        if quote:
            chunk += f": «{quote}»"
        parts.append(chunk)
    return "\n".join(parts)


def save_results(
    results: Iterable[Dict[str, Any]],
    output_file: Union[str, Path],
    sheet_name: str = "Results",
) -> Path:
    """Persist classification results to an Excel workbook.

    Each result dict is expected to contain the original requirement fields plus
    a ``classification`` payload as produced by ``LLMClient.classify_requirement``.

    Adds the columns ``[Статус]``, ``[Уверенность]``, ``[Комментарий]``,
    ``[Цитаты]`` and ``[Провайдер]``.
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required to export results. Install it with `pip install pandas openpyxl`."
        ) from exc

    rows: List[Dict[str, Any]] = []
    for item in results:
        classification = item.get("classification") or {}
        rows.append(
            {
                "ID": item.get("id"),
                "Требование": item.get("text"),
                "[Статус]": classification.get("classification", "НД"),
                "[Уверенность]": classification.get("confidence", 0.0),
                "[Комментарий]": classification.get("reasoning", ""),
                "[Рекомендация]": classification.get("recommendations", ""),
                "[Цитаты]": _format_citations(classification.get("citations", [])),
                "[Требует ревью]": "Да" if classification.get("requires_ba_review") else "Нет",
                "[Провайдер]": classification.get("provider", ""),
                "[Ошибка]": item.get("error", ""),
            }
        )

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(output_path, sheet_name=sheet_name, index=False)
    logger.info("Saved %d rows to %s", len(rows), output_path)
    return output_path
