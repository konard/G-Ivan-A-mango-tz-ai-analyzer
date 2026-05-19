"""Sidebar widget for picking the operation mode and global UI settings.

BL-41 (issue #168) extracts the sidebar layout from ``src.ui.app`` into a
single component. The function still returns the same ``{mode, debug, top_k,
clear_history}`` dictionary so ``src.ui.app.main`` can keep its orchestration
flow unchanged.

BL-48.6 (issue #184): the «глубина поиска» slider reads its label, tooltip,
range and production warning from ``configs/ui_config.yaml`` so business-facing
copy and limits can be tweaked without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from src.ui.constants import (
    LABELS,
    MODE_CONSULTATION,
    MODE_HELP,
    MODE_LABELS,
    MODE_ORDER,
    MODE_STATELESS,
)

DEFAULT_TOP_K = 5
DEFAULT_TOP_K_MIN = 1
DEFAULT_TOP_K_MAX = 20
DEFAULT_TOP_K_PRODUCTION_MAX = 10


def _clamp_int(value: Any, fallback: int, *, minimum: int = 1) -> int:
    """Return ``value`` coerced to int and clamped to ``>= minimum``."""
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, coerced)


def resolve_retrieval_settings(
    ui_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read the BL-48.6 retrieval slider settings from ``ui_config.yaml``.

    The loader is forgiving on purpose: missing keys, the wrong type, or a
    completely empty config never break the sidebar — defaults are applied
    silently so the UI keeps working even with a half-migrated config file.
    """
    cfg = ui_config or {}
    ui_section = cfg.get("ui") if isinstance(cfg, dict) else None
    retrieval = ui_section.get("retrieval") if isinstance(ui_section, dict) else None
    if not isinstance(retrieval, dict):
        retrieval = {}

    top_k_min = _clamp_int(retrieval.get("top_k_min"), DEFAULT_TOP_K_MIN, minimum=1)
    top_k_max = _clamp_int(
        retrieval.get("top_k_max"), DEFAULT_TOP_K_MAX, minimum=top_k_min
    )
    if top_k_max < top_k_min:
        top_k_max = top_k_min
    top_k_default = _clamp_int(
        retrieval.get("top_k_default"), DEFAULT_TOP_K, minimum=top_k_min
    )
    top_k_default = min(top_k_default, top_k_max)
    top_k_production_max = _clamp_int(
        retrieval.get("top_k_production_max"),
        DEFAULT_TOP_K_PRODUCTION_MAX,
        minimum=top_k_min,
    )
    top_k_production_max = min(top_k_production_max, top_k_max)

    label = str(retrieval.get("top_k_label") or LABELS["sidebar_topk_label"])
    help_text = str(retrieval.get("top_k_help") or LABELS["sidebar_topk_help"])
    tooltip = str(retrieval.get("top_k_tooltip") or "").strip()
    warning_template = str(
        retrieval.get("top_k_warning_template")
        or LABELS["sidebar_topk_warning_template"]
    )

    return {
        "top_k_min": top_k_min,
        "top_k_max": top_k_max,
        "top_k_default": top_k_default,
        "top_k_production_max": top_k_production_max,
        "label": label,
        "help": help_text,
        "tooltip": tooltip,
        "warning_template": warning_template,
    }


def _render_top_k_warning(value: int, settings: Dict[str, Any]) -> None:
    """Show an inline warning when the user crosses the production-safe limit."""
    threshold = int(settings.get("top_k_production_max") or 0)
    if threshold <= 0 or value <= threshold:
        return
    template = str(
        settings.get("warning_template")
        or LABELS["sidebar_topk_warning_template"]
    )
    try:
        message = template.format(limit=threshold, value=value)
    except (KeyError, IndexError):
        message = template
    st.warning(message)


def render_sidebar(
    retriever_info: Optional[Dict[str, str]],
    *,
    max_history_messages: int,
    env_path: Optional[Path] = None,
    retrieval_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Render the Streamlit sidebar and return user choices.

    ``env_path`` is passed in so the sidebar can warn when ``.env`` is missing
    without re-importing module-level constants from ``src.ui.app``.
    ``retrieval_settings`` is the resolved BL-48.6 slider config; when omitted
    the function falls back to safe defaults so old callers keep working.
    """
    slider_cfg = retrieval_settings or resolve_retrieval_settings()
    tooltip = str(slider_cfg.get("tooltip") or "").strip()
    help_text = str(slider_cfg.get("help") or LABELS["sidebar_topk_help"])
    slider_help = f"{help_text}\n\n{tooltip}" if tooltip else help_text

    with st.sidebar:
        st.header(LABELS["sidebar_header"])

        mode_label = st.radio(
            LABELS["sidebar_mode_label"],
            options=[MODE_LABELS[m] for m in MODE_ORDER],
            index=0,
            help=(
                f"📊 **{MODE_LABELS[MODE_STATELESS]}** — "
                f"{MODE_HELP[MODE_STATELESS]}\n\n"
                f"💬 **{MODE_LABELS[MODE_CONSULTATION]}** — "
                f"{MODE_HELP[MODE_CONSULTATION]} "
                f"≤ {max_history_messages} последних сообщений."
            ),
        )
        mode = next(
            (m for m, label in MODE_LABELS.items() if label == mode_label),
            MODE_STATELESS,
        )

        debug_mode = st.toggle(
            LABELS["sidebar_debug_label"],
            value=False,
            help=LABELS["sidebar_debug_help"],
        )

        top_k = st.slider(
            str(slider_cfg.get("label") or LABELS["sidebar_topk_label"]),
            min_value=int(slider_cfg["top_k_min"]),
            max_value=int(slider_cfg["top_k_max"]),
            value=int(slider_cfg["top_k_default"]),
            help=slider_help,
        )
        if tooltip:
            with st.expander(LABELS["sidebar_topk_info_expander"], expanded=False):
                st.markdown(tooltip)
        _render_top_k_warning(int(top_k), slider_cfg)

        clear_history = False
        if mode == MODE_CONSULTATION:
            st.divider()
            history_len = len(st.session_state.get("messages", []))
            st.caption(
                LABELS["sidebar_history_caption"].format(
                    len=history_len, max=max_history_messages
                )
            )
            clear_history = st.button(
                LABELS["sidebar_clear_history_button"],
                help=LABELS["sidebar_clear_history_help"],
            )

        st.divider()
        st.caption(LABELS["sidebar_fallback_caption"])
        if retriever_info:
            st.caption(
                LABELS["sidebar_vector_store_caption"].format(
                    path=retriever_info["persist_directory"]
                )
            )
            st.caption(
                LABELS["sidebar_collection_caption"].format(
                    name=retriever_info["collection_name"]
                )
            )
            st.caption(
                LABELS["sidebar_embedding_caption"].format(
                    name=retriever_info["model_name"]
                )
            )

        if env_path is not None and not env_path.exists():
            st.warning(LABELS["sidebar_no_env_warning"])

    return {
        "mode": mode,
        "debug": debug_mode,
        "top_k": top_k,
        "clear_history": clear_history,
    }
