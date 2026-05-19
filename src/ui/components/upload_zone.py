"""File uploader widget for the TZ analyzer (BL-41).

Wraps ``st.file_uploader`` so the Russian copy lives in one place and the
``src.app`` analysis tab can swap in custom labels without re-introducing
inline strings.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import streamlit as st


DEFAULT_UPLOAD_TYPES: tuple[str, ...] = ("xlsx", "docx")


def render_upload_zone(
    label: str = "📎 Файл тендерного ТЗ",
    *,
    types: Iterable[str] = DEFAULT_UPLOAD_TYPES,
    help_text: str = "Поддерживаются Excel (.xlsx) и Word (.docx) файлы.",
    key: Optional[str] = None,
) -> Any:
    """Render the file uploader widget and return the Streamlit upload handle.

    Returns whatever ``st.file_uploader`` returns (``UploadedFile`` or ``None``)
    so callers can check truthiness before reading bytes.
    """
    return st.file_uploader(
        label,
        type=list(types),
        help=help_text,
        key=key,
    )
