"""Sidebar widget for picking the operation mode and global UI settings.

BL-41 (issue #168) extracts the sidebar layout from ``src.ui.app`` into a
single component. The function still returns the same ``{mode, debug, top_k,
clear_history}`` dictionary so ``src.ui.app.main`` can keep its orchestration
flow unchanged.
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


def render_sidebar(
    retriever_info: Optional[Dict[str, str]],
    *,
    max_history_messages: int,
    env_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Render the Streamlit sidebar and return user choices.

    ``env_path`` is passed in so the sidebar can warn when ``.env`` is missing
    without re-importing module-level constants from ``src.ui.app``.
    """
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
            LABELS["sidebar_topk_label"],
            min_value=1,
            max_value=10,
            value=DEFAULT_TOP_K,
            help=LABELS["sidebar_topk_help"],
        )

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
