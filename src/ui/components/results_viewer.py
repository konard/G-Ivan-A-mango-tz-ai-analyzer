"""Rendering helpers for KB chunks and analysis results (BL-41).

These helpers stay free of business logic: they receive normalised chunk
dictionaries from ``src.ui.app`` and emit Streamlit widgets. The functions
that other parts of the codebase still expect on ``src.ui.app`` (``truncate``,
``_coerce_page``, ``_section_signature``, ``_format_dependency_summary``,
``render_chunks``) are re-exported from ``src.ui.app`` so the public surface
stays stable for tests.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from src.ui.constants import LABELS, STATUS_TOOLTIPS

CHUNK_PREVIEW_CHARS = 600


def truncate(text: str, limit: int = CHUNK_PREVIEW_CHARS) -> str:
    """Trim ``text`` to ``limit`` characters and append ``...`` when truncated."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def coerce_page(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def section_signature(metadata: Dict[str, Any]) -> str:
    title = str(metadata.get("section_title") or "").strip()
    number = str(metadata.get("section_number") or "").strip()
    fallback = str(metadata.get("section_fallback") or "").strip()
    if fallback and fallback != "none" and title:
        return f"раздел: {title}"
    if number and title:
        return f"§{number} {title}"
    if number:
        return f"§{number}"
    return title


def _metadata_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raw_items = str(value).split(";")
    seen = set()
    items: List[str] = []
    for raw in raw_items:
        item = re.sub(r"\s+", " ", raw or "").strip(" \t\r\n,;")
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def format_dependency_context(metadata: Dict[str, Any]) -> str:
    related = _metadata_list(metadata.get("related_sections"))
    prerequisites = _metadata_list(metadata.get("prerequisites"))
    see_also = _metadata_list(metadata.get("see_also"))
    lines: List[str] = []
    if prerequisites:
        lines.append("Предварительные условия: " + "; ".join(prerequisites))
    if related:
        lines.append("Связанные разделы: " + "; ".join(related))
    if see_also:
        lines.append("См. также: " + "; ".join(see_also))
    return "\n".join(lines)


def format_dependency_summary(metadata: Dict[str, Any]) -> str:
    related = _metadata_list(metadata.get("related_sections"))
    prerequisites = _metadata_list(metadata.get("prerequisites"))
    see_also = _metadata_list(metadata.get("see_also"))
    if not (related or prerequisites or see_also):
        return ""

    parts: List[str] = []
    if prerequisites:
        parts.append("**Предварительные условия:** " + ", ".join(prerequisites))
    if related:
        parts.append("**Связанные разделы:** " + ", ".join(related))
    if see_also:
        parts.append("**См. также:** " + ", ".join(see_also))
    return "\n\n".join(parts)


def render_status_legend() -> None:
    """Show the Да/Нет/Частично/НД/Ошибка tooltips above the citations.

    UX check from issue #168 §3 requires a tooltip explaining each status to a
    business analyst. When ``st.columns`` is available (real Streamlit) we lay
    the badges out horizontally; otherwise we fall back to a single caption
    line so test stubs without ``columns`` keep working.
    """
    columns_fn = getattr(st, "columns", None)
    if callable(columns_fn):
        try:
            columns = columns_fn(len(STATUS_TOOLTIPS))
        except Exception:  # noqa: BLE001 — fall back to caption on layout error
            columns = None
        if columns:
            rendered = True
            for col, (status, hint) in zip(columns, STATUS_TOOLTIPS.items()):
                col_markdown = getattr(col, "markdown", None)
                if not callable(col_markdown):
                    rendered = False
                    break
                col_markdown(f"**{status}**", help=hint)
            if rendered:
                return
    legend = " · ".join(
        f"**{status}** — {hint}" for status, hint in STATUS_TOOLTIPS.items()
    )
    st.caption(f"{LABELS['chunks_legend_header']} {legend}")


def render_chunks(
    chunks: List[Dict[str, Any]],
    debug: bool,
    *,
    build_citation_link: Optional[Callable[..., str]] = None,
) -> None:
    """Render the retrieved KB chunks as collapsible cards.

    ``build_citation_link`` is supplied by ``src.ui.app`` (it depends on the
    citations base URL config), keeping this module decoupled from BL-09.
    """
    st.subheader(LABELS["chunks_header"])
    if not chunks:
        st.info(LABELS["chunks_empty_info"])
        return
    render_status_legend()
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "unknown")
        similarity = chunk.get("similarity")
        distance = chunk.get("distance")
        chunk_idx = chunk.get("chunk_idx")
        meta = chunk.get("metadata") or {}
        page_number = coerce_page(meta.get("page_number")) or coerce_page(chunk.get("page"))
        signature = section_signature(meta)
        score_label = (
            f"similarity={similarity:.4f}" if isinstance(similarity, float)
            else "similarity=n/a"
        )
        chunk_suffix = f" · chunk={chunk_idx}" if chunk_idx is not None else ""
        page_suffix = f" · стр. {page_number}" if page_number else ""
        section_suffix = f" · {signature}" if signature else ""
        with st.expander(
            f"#{i} — {source}{page_suffix}{section_suffix}{chunk_suffix}  ({score_label})",
            expanded=(i == 1),
        ):
            if build_citation_link and source and source != "unknown":
                st.markdown(
                    build_citation_link(
                        source,
                        page_number,
                        section_signature=signature,
                    )
                )
            dependency_summary = format_dependency_summary(meta)
            if dependency_summary:
                st.markdown(dependency_summary)
            st.markdown(LABELS["chunks_snippet_header"])
            st.write(truncate(chunk.get("text", "")))
            st.caption(
                f"distance: {distance:.4f}" if isinstance(distance, float)
                else "distance: n/a"
            )
            if debug:
                st.markdown(LABELS["chunks_metadata_header"])
                st.json(
                    {
                        "source": source,
                        "chunk_idx": chunk_idx,
                        "distance": distance,
                        "similarity": similarity,
                        "metadata": chunk.get("metadata", {}),
                    }
                )
                st.markdown(LABELS["chunks_full_text_header"])
                st.code(chunk.get("text", "") or "(empty)", language="markdown")
