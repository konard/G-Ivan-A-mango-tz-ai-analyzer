"""Reusable Streamlit UI components for Clarify Engine (BL-41, issue #168).

The KB Test UI (``src/ui/app.py``) is decomposed into single-responsibility
modules so the orchestration layer can stay short and the rendering helpers
can be exercised independently. Tests still patch the public symbols on
``src.ui.app``; the components themselves only know about Streamlit and the
data structures the orchestrator passes in.
"""

from __future__ import annotations

from src.ui.components.chat_interface import (
    render_chat_history,
)
from src.ui.components.mode_selector import render_sidebar
from src.ui.components.results_viewer import (
    coerce_page,
    format_dependency_summary,
    render_chunks,
    render_status_legend,
    section_signature,
    truncate,
)
from src.ui.components.upload_zone import render_upload_zone

__all__ = [
    "coerce_page",
    "format_dependency_summary",
    "render_chat_history",
    "render_chunks",
    "render_sidebar",
    "render_status_legend",
    "render_upload_zone",
    "section_signature",
    "truncate",
]
