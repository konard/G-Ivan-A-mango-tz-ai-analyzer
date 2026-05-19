"""Rendering helpers for the consultation-mode chat (BL-41).

The chat history rendering is split out from ``src.ui.app`` so the orchestrator
no longer needs to know how individual messages are drawn. Debug expanders for
the last assistant turn (prompt + chunks) are still rendered here because they
are part of the same visual element from the user's point of view.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

import streamlit as st

from src.ui.constants import LABELS


def latest_assistant_message_index(
    messages: Sequence[Dict[str, Any]],
) -> Optional[int]:
    """Return the index of the most recent assistant turn or ``None``."""
    for idx in range(len(messages) - 1, -1, -1):
        if str(messages[idx].get("role", "")).lower() == "assistant":
            return idx
    return None


def render_chat_history(
    messages: Sequence[Dict[str, Any]],
    *,
    debug: bool,
    render_chunks: Callable[[List[Dict[str, Any]], bool], None],
) -> None:
    """Render each saved chat message and the debug overlay for the last turn.

    ``render_chunks`` is injected so this component does not need to know how
    citations are linkified — that work lives next to the citations config in
    ``src.ui.app``.
    """
    latest_idx = latest_assistant_message_index(messages)
    for idx, msg in enumerate(messages):
        with st.chat_message(msg.get("role", "user")):
            st.markdown(msg.get("content", ""))
            if (
                debug
                and idx == latest_idx
                and str(msg.get("role", "")).lower() == "assistant"
            ):
                prompt = str(msg.get("prompt") or "")
                chunks = msg.get("chunks") or []
                if prompt:
                    with st.expander(
                        LABELS["analysis_prompt_expander"], expanded=False
                    ):
                        st.code(prompt, language="markdown")
                if chunks:
                    render_chunks(chunks, debug)
