"""Streamlit UI for testing the Clarify Engine knowledge-base RAG pipeline.

Run locally with::

    streamlit run src/ui/app.py

The UI is intentionally minimal and self-contained: it queries the ChromaDB
collection populated by ``knowledge_base/indexing/build_index.py``, embeds the
user query with the model declared in ``configs/embedding_config.yaml``
(default ``BAAI/bge-m3``), and asks the active LLM provider chain
(GigaChat → OpenRouter → Ollama) to answer using the retrieved chunks as
context. Provider metadata is read from ``configs/llm_config.yaml``; secrets
come from ``.env``.

The module purposefully avoids LangChain/LlamaIndex and any framework that
hides retrieval/LLM behaviour — only ``streamlit``, ``chromadb``, ``requests``,
``yaml``, ``dotenv`` and ``sentence-transformers`` (needed to load the
configured embedding model) are used.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from typing import Any, Callable, Dict, List, Optional, Sequence
from uuid import uuid4

import streamlit as st
import yaml

logger = logging.getLogger(__name__)

# Streamlit's set_page_config must be the first Streamlit call, so it happens
# at import time before any other UI helpers are imported.
st.set_page_config(
    page_title="Clarify Engine - KB Test UI",
    page_icon="🔎",
    layout="wide",
)

_load_dotenv_impl: Optional[Callable[..., bool]] = None
try:
    from dotenv import load_dotenv as _imported_load_dotenv
except ImportError:  # pragma: no cover - declared in requirements.txt
    pass
else:
    _load_dotenv_impl = _imported_load_dotenv


def load_dotenv(*args: Any, **kwargs: Any) -> bool:
    if _load_dotenv_impl is None:
        return False
    return bool(_load_dotenv_impl(*args, **kwargs))


# --------------------------------------------------------------------- paths --
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LLM_CONFIG_PATH = PROJECT_ROOT / "configs" / "llm_config.yaml"
EMBEDDING_CONFIG_PATH = PROJECT_ROOT / "configs" / "embedding_config.yaml"
UI_CONFIG_PATH = PROJECT_ROOT / "configs" / "ui_config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"
SOURCES_DIR = PROJECT_ROOT / "knowledge_base" / "sources"
DEFAULT_CITATIONS_BASE_URL = "http://localhost:8000/docs"

DEFAULT_TOP_K = 5
CHUNK_PREVIEW_CHARS = 600

# BL-07 (issue #93) — operation modes. The radio labels are user-facing and
# match the spec verbatim; `STATELESS` and `CONSULTATION` are the internal
# identifiers used everywhere else so we never compare emoji strings.
MODE_STATELESS = "stateless"
MODE_CONSULTATION = "consultation"
MODE_LABELS: Dict[str, str] = {
    MODE_STATELESS: "📊 Анализ ТЗ",
    MODE_CONSULTATION: "💬 Консультация по документации",
}
MODE_ORDER: List[str] = [MODE_STATELESS, MODE_CONSULTATION]
DEFAULT_MAX_HISTORY_MESSAGES = 6
DEFAULT_MULTI_HOP_MAX_HOPS = 2
DEFAULT_MULTI_HOP_MIN_CONFIDENCE_TO_STOP = 0.8
# ~4 characters per token is a reasonable upper-bound proxy for Russian +
# Cyrillic text. We log this as a guard against unbounded prompt growth; the
# real provider tokeniser may differ but the trend (and the relative impact
# of trimming history) is the same.
TOKEN_CHAR_RATIO = 4

PROVIDER_DISPLAY = {
    "gigachat": "GigaChat",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
}

# BL-13 (issue #106) — graceful degradation state. The issue explicitly pins
# ``last_query`` as the retry source, so that key remains un-namespaced.
UI_GENERATION_ERROR_TEXT = "Не удалось получить ответ."
UI_GENERATION_ERROR_REASON = "Все провайдеры недоступны"
RETRY_BUTTON_LABEL = "Повторить"
SESSION_LAST_QUERY_KEY = "last_query"
SESSION_LAST_ERROR_KEY = "last_error"
SESSION_PROCESSING_KEY = "is_processing"
SESSION_PENDING_QUERY_KEY = "pending_query"
SESSION_PENDING_MODE_KEY = "pending_mode"
SESSION_PENDING_RUN_ID_KEY = "pending_run_id"
SESSION_LAST_ANALYSIS_RESULT_KEY = "last_analysis_result"

# BL-08 (issue #94): the RAG system prompt is now a versioned artefact in
# ``prompts/``. The Streamlit module loads it lazily inside ``main()`` so an
# import of this module (e.g. from ``tests/test_citation_links.py``) never
# touches the filesystem. A minimal fallback is kept so the UI still renders
# something sensible when the prompt file is missing — operators should fix
# the install rather than edit the constant.
_SYSTEM_PROMPT_NAME = "system_rag"
_SYSTEM_PROMPT_VERSION = "v1.0"
_REFLECTION_PROMPT_NAME = "system_rag_reflection"
_REFLECTION_PROMPT_VERSION = "v1.0"
_SYSTEM_PROMPT_FALLBACK = (
    "You are an assistant for the Clarify Engine knowledge base. "
    "Answer using ONLY the provided context chunks. "
    "Quote source filenames in square brackets when you rely on a chunk. "
    "Respond in Markdown."
)
_REFLECTION_PROMPT_FALLBACK = (
    "You judge whether retrieved context is sufficient to answer a question. "
    "Do not answer the question. Return only strict JSON with keys "
    "sufficient, follow_up, confidence."
)


# -------------------------------------------------------------------- errors --
class KBError(RuntimeError):
    """User-facing error raised when the knowledge base cannot be queried."""


# ------------------------------------------------------------------- helpers --
def load_llm_config(path: Path = LLM_CONFIG_PATH) -> Dict[str, Any]:
    """Load ``configs/llm_config.yaml``; return ``{}`` on any failure."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        st.warning(f"Failed to parse {path.name}: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def load_ui_config(path: Path = UI_CONFIG_PATH) -> Dict[str, Any]:
    """Load ``configs/ui_config.yaml``; return ``{}`` on any failure."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        st.warning(f"Failed to parse {path.name}: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def get_citations_config(ui_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return citation link settings with backwards-compatible defaults."""
    cfg = ui_config if ui_config is not None else load_ui_config()
    citations = cfg.get("citations") if isinstance(cfg, dict) else None
    if not isinstance(citations, dict):
        citations = {}
    source_dir_raw = citations.get("source_dir", "knowledge_base/sources")
    source_dir = Path(str(source_dir_raw))
    if not source_dir.is_absolute():
        source_dir = PROJECT_ROOT / source_dir
    return {
        "base_url": str(citations.get("base_url") or DEFAULT_CITATIONS_BASE_URL),
        "source_dir": source_dir,
    }


def get_debug_error_details(ui_config: Optional[Dict[str, Any]] = None) -> bool:
    """Return true only when UI config explicitly enables error diagnostics."""
    cfg = ui_config if ui_config is not None else load_ui_config()
    ui_cfg = cfg.get("ui") if isinstance(cfg, dict) else None
    if not isinstance(ui_cfg, dict):
        return False
    return bool(ui_cfg.get("debug_error_details", False))


def truncate(text: str, limit: int = CHUNK_PREVIEW_CHARS) -> str:
    """Trim ``text`` to ``limit`` characters and append ``...`` when truncated."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


# ----------------------------------------------------- cached resource loaders --
@st.cache_resource(show_spinner="Loading retriever (BM25 + bge-m3 + ChromaDB)…")
def get_retriever():
    """Build and cache the production hybrid retriever (BL-01).

    Combines BM25 lexical recall + bge-m3 dense recall with RRF fusion
    (k=60) over the persistent ChromaDB collection.
    """
    from src.rag.retriever import HybridChromaRetriever

    try:
        return HybridChromaRetriever.from_config(
            config_path=str(EMBEDDING_CONFIG_PATH),
            project_root=PROJECT_ROOT,
        )
    except Exception as exc:  # noqa: BLE001
        raise KBError(f"Failed to initialise retriever: {exc}") from exc


@st.cache_resource(show_spinner="Initialising LLM client…")
def get_llm_client():
    """Build and cache an :class:`LLMClient` from the LLM config."""
    from src.llm.client import LLMClient

    return LLMClient.from_config(config_path=str(LLM_CONFIG_PATH))


@st.cache_resource(show_spinner=False)
def get_rag_system_prompt() -> str:
    """Return the RAG system prompt from the versioned prompt library.

    BL-08 (issue #94): no hardcoded prompt in the UI. The loader emits an
    INFO log record carrying ``prompt_name`` / ``prompt_version`` /
    ``prompt_sha256`` so the audit trail in JSON logs stays consistent
    with the classifier path.
    """
    from src.llm.prompt_loader import PromptNotFoundError, load_prompt

    try:
        return load_prompt(
            _SYSTEM_PROMPT_NAME,
            version=_SYSTEM_PROMPT_VERSION,
            prompts_dir=PROJECT_ROOT / "prompts",
        ).content
    except PromptNotFoundError:
        st.warning(
            "System prompt prompts/system_rag_v1.0.md not found — using minimal fallback. "
            "Re-install the repository to restore prompt audit trail."
        )
        return _SYSTEM_PROMPT_FALLBACK


@st.cache_resource(show_spinner=False)
def get_rag_reflection_prompt() -> str:
    """Return the BL-11 reflection prompt from the versioned prompt library."""
    from src.llm.prompt_loader import PromptNotFoundError, load_prompt

    try:
        return load_prompt(
            _REFLECTION_PROMPT_NAME,
            version=_REFLECTION_PROMPT_VERSION,
            prompts_dir=PROJECT_ROOT / "prompts",
        ).content
    except PromptNotFoundError:
        st.warning(
            "System prompt prompts/system_rag_reflection_v1.0.md not found — "
            "using minimal fallback."
        )
        return _REFLECTION_PROMPT_FALLBACK


# ----------------------------------------------------------------- retrieval --
def search_vector_store(
    ui_mode: str = MODE_STATELESS,
    llm_config: Optional[Dict[str, Any]] = None,
    enable_query_expansion: bool = False,
) -> List[Dict[str, Any]]:
    """Run a vector search and return chunk dicts ordered by similarity."""

    # --- Imports ---
    from src.rag.retriever import get_retriever
    
    # --- Base Retriever ---
    base_retriever = get_retriever()
    active_retriever = base_retriever

    # --- Layer 1: Multi-hop Retrieval (Inner Wrapper) ---
    # Срабатывает внутри поиска (Reflection)
    multi_hop = resolve_multi_hop_settings(llm_config, ui_mode)
    if multi_hop["enabled"]:
        from src.rag.retriever import IterativeRetriever

        def _reflection_call(user_prompt: str) -> str:
            client = get_llm_client()
            return client.generate_rag_response(
                get_rag_reflection_prompt(),
                user_prompt,
            )

        active_retriever = IterativeRetriever(
            active_retriever,
            reflection_call=_reflection_call,
            max_hops=int(multi_hop["max_hops"]),
            min_confidence_to_stop=float(multi_hop["min_confidence_to_stop"]),
        )

    # --- Layer 2: Query Expansion (Outer Wrapper) ---
    # Срабатывает до поиска (Expansion)
    if enable_query_expansion:
        from src.rag.query_expansion import QueryExpansionRetriever, QueryExpansionConfig
        from src.rag.retriever import load_embedding_config

        expansion_config = getattr(base_retriever, "config", None)
        if not isinstance(expansion_config, dict):
            expansion_config = load_embedding_config(str(EMBEDDING_CONFIG_PATH))
        
        if QueryExpansionConfig.from_mapping(expansion_config).enabled:
            active_retriever = QueryExpansionRetriever(
                active_retriever,
                get_llm_client(),
                config=expansion_config,
                prompts_dir=PROJECT_ROOT / "prompts",
            )

    # --- Execution ---
    # Active retriever is now either Base, Iterative, or QueryExpansion(Iterative(Base))
    return active_retriever.search()
    try:
        chunks = active_retriever.search(
            query,
            top_k=top_k,
            use_parent_context=use_parent_context,
        )
    except Exception as exc:  # noqa: BLE001
        raise KBError(f"ChromaDB query failed: {exc}") from exc
    if not chunks:
        raise KBError(
            f"Collection '{retriever.collection_name}' at "
            f"'{retriever.persist_directory}' returned no results. Make sure "
            "the index is built: `python knowledge_base/indexing/build_index.py`."
        )
    return chunks


# ------------------------------------------------------------- BL-09 citations --
def build_citation_link(
    source: str,
    page: Any,
    *,
    section_signature: str = "",
    base_url: Optional[str] = None,
) -> str:
    """Return a clickable Markdown citation pinned to a PDF page.

    Format follows the BL-09.1 spec: ``[source.pdf, стр. N](base/source.pdf#page=N)``.
    When the page number is missing or non-integer, the link still resolves to
    the source file (no ``#page`` anchor).
    """
    if not source:
        return ""
    cfg = get_citations_config()
    resolved_base_url = (base_url or str(cfg["base_url"])).rstrip("/")
    page_int = _coerce_page(page)
    section_suffix = f", {section_signature}" if section_signature else ""
    encoded_source = quote(Path(source).name)
    target = f"{resolved_base_url}/{encoded_source}"
    if page_int:
        label = f"{source}, стр. {page_int}{section_suffix}"
        target = f"{target}#page={page_int}"
    else:
        label = f"{source}{section_suffix}"
    return f"[{label}]({target})"


def _coerce_page(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def _first_page_per_source(chunks: List[Dict[str, Any]]) -> Dict[str, int]:
    """Pick the first page seen for each source filename (top-ranked first)."""
    mapping: Dict[str, int] = {}
    for chunk in chunks:
        source = str(chunk.get("source") or "").strip()
        if not source or source in mapping:
            continue
        meta = chunk.get("metadata") or {}
        page = _coerce_page(meta.get("page_number")) or _coerce_page(chunk.get("page"))
        if page:
            mapping[source] = page
    return mapping


def _section_signature(metadata: Dict[str, Any]) -> str:
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


def _first_citation_meta_per_source(chunks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Pick page/section metadata from the highest-ranked chunk per source."""
    mapping: Dict[str, Dict[str, Any]] = {}
    for chunk in chunks:
        source = str(chunk.get("source") or "").strip()
        if not source or source in mapping:
            continue
        meta = chunk.get("metadata") or {}
        page = _coerce_page(meta.get("page_number")) or _coerce_page(chunk.get("page"))
        mapping[source] = {
            "page": page,
            "section_signature": _section_signature(meta),
        }
    return mapping


def linkify_citations(
    answer: str,
    chunks: List[Dict[str, Any]],
    *,
    base_url: Optional[str] = None,
) -> str:
    """Rewrite ``[filename.pdf]`` placeholders in ``answer`` to BL-09 links.

    The replacement uses the highest-ranked chunk's ``page_number`` for each
    source. Citations whose source is not present in ``chunks`` are left
    untouched so the UI never invents page numbers.
    """
    if not answer:
        return answer
    meta_by_source = _first_citation_meta_per_source(chunks)
    if not meta_by_source:
        return answer

    pattern = re.compile(r"\[([^\[\]\(\)\n]+\.[A-Za-z0-9]{1,8})\](?!\()")

    def _replace(match: re.Match) -> str:
        source = match.group(1).strip()
        if source not in meta_by_source:
            return match.group(0)
        meta = meta_by_source[source]
        link = build_citation_link(
            source,
            meta.get("page"),
            section_signature=str(meta.get("section_signature") or ""),
            base_url=base_url,
        )
        return link or match.group(0)

    return pattern.sub(_replace, answer)


# ----------------------------------------------------------- LLM provider calls --
def _format_context(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "(no context)"
    blocks: List[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "unknown")
        text = (chunk.get("text") or "").strip()
        chunk_idx = chunk.get("chunk_idx")
        meta = chunk.get("metadata") or {}
        suffix = f" #chunk={chunk_idx}" if chunk_idx is not None else ""
        page = _coerce_page(meta.get("page_number")) or _coerce_page(chunk.get("page"))
        page_label = f" стр. {page}" if page else ""
        section_label = _section_signature(meta)
        section_suffix = f" {section_label}" if section_label else ""
        blocks.append(f"[{idx}] {source}{page_label}{section_suffix}{suffix}\n{text}")
    return "\n\n".join(blocks)


def build_user_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    history: Optional[Sequence[Dict[str, str]]] = None,
) -> str:
    """Build the user message sent to the LLM.

    When ``history`` is provided (consultation mode, BL-07), prior turns are
    inlined into a ``<history>`` block above the current question. The block
    is omitted entirely for stateless analysis so the prompt shape stays
    identical to the pre-BL-07 behaviour.
    """
    context = _format_context(chunks)
    sections: List[str] = [f"<context>\n{context}\n</context>"]
    if history:
        sections.append(f"<history>\n{format_history(history)}\n</history>")
    sections.append(f"<question>{query.strip()}</question>")
    return "\n\n".join(sections)


# ---------------------------------------------------- BL-07 history helpers --
def get_max_history_messages(llm_config: Optional[Dict[str, Any]] = None) -> int:
    """Return the configured cap on consultation-mode history length.

    Reads ``ui.max_history_messages`` from ``configs/llm_config.yaml`` and
    clamps the result to a non-negative integer; defaults to
    :data:`DEFAULT_MAX_HISTORY_MESSAGES` when the key is missing or malformed.
    """
    cfg = llm_config if llm_config is not None else load_llm_config()
    ui_cfg = cfg.get("ui") if isinstance(cfg, dict) else None
    if not isinstance(ui_cfg, dict):
        return DEFAULT_MAX_HISTORY_MESSAGES
    raw = ui_cfg.get("max_history_messages", DEFAULT_MAX_HISTORY_MESSAGES)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_HISTORY_MESSAGES
    return max(0, value)


def resolve_multi_hop_settings(
    llm_config: Optional[Dict[str, Any]],
    ui_mode: str,
) -> Dict[str, Any]:
    """Resolve BL-11 multi-hop config with the Consultation-mode hard lock."""
    cfg = llm_config or {}
    rag_cfg = cfg.get("rag") if isinstance(cfg, dict) else None
    if not isinstance(rag_cfg, dict):
        rag_cfg = {}

    try:
        max_hops = int(rag_cfg.get("max_hops", DEFAULT_MULTI_HOP_MAX_HOPS))
    except (TypeError, ValueError):
        max_hops = DEFAULT_MULTI_HOP_MAX_HOPS
    max_hops = max(1, max_hops)

    try:
        min_confidence = float(
            rag_cfg.get(
                "min_confidence_to_stop",
                DEFAULT_MULTI_HOP_MIN_CONFIDENCE_TO_STOP,
            )
        )
    except (TypeError, ValueError):
        min_confidence = DEFAULT_MULTI_HOP_MIN_CONFIDENCE_TO_STOP
    min_confidence = min(1.0, max(0.0, min_confidence))

    enabled = bool(rag_cfg.get("multi_hop_enabled", False))
    return {
        "enabled": enabled and ui_mode == MODE_CONSULTATION,
        "max_hops": max_hops,
        "min_confidence_to_stop": min_confidence,
    }


def trim_history(
    messages: Sequence[Dict[str, str]], max_messages: int
) -> List[Dict[str, str]]:
    """Keep at most ``max_messages`` most recent items from ``messages``."""
    if max_messages <= 0:
        return []
    if len(messages) <= max_messages:
        return list(messages)
    return list(messages[-max_messages:])


def format_history(messages: Sequence[Dict[str, str]]) -> str:
    """Render chat history as plain text for inlining into the LLM prompt.

    Each message becomes ``Пользователь:`` / ``Ассистент:`` prefixed lines so
    the LLM can distinguish speakers without us adding extra `role` fields to
    ``LLMClient.generate_rag_response`` (whose signature must stay stable —
    see issue #93 DoD).
    """
    role_labels = {"user": "Пользователь", "assistant": "Ассистент"}
    lines: List[str] = []
    for msg in messages:
        role = role_labels.get(str(msg.get("role", "")).lower(), "Пользователь")
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def estimate_token_count(text: str) -> int:
    """Cheap token estimate (chars / TOKEN_CHAR_RATIO) for prompt-size logging."""
    if not text:
        return 0
    return max(1, len(text) // TOKEN_CHAR_RATIO)


# ---------------------------------------------------------------- rendering --
def render_chunks(chunks: List[Dict[str, Any]], debug: bool) -> None:
    st.subheader("Source Chunks")
    if not chunks:
        st.info("No matching chunks were returned.")
        return
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "unknown")
        similarity = chunk.get("similarity")
        distance = chunk.get("distance")
        chunk_idx = chunk.get("chunk_idx")
        meta = chunk.get("metadata") or {}
        page_number = _coerce_page(meta.get("page_number")) or _coerce_page(chunk.get("page"))
        section_signature = _section_signature(meta)
        score_label = (
            f"similarity={similarity:.4f}" if isinstance(similarity, float)
            else "similarity=n/a"
        )
        chunk_suffix = f" · chunk={chunk_idx}" if chunk_idx is not None else ""
        page_suffix = f" · стр. {page_number}" if page_number else ""
        section_suffix = f" · {section_signature}" if section_signature else ""
        with st.expander(
            f"#{i} — {source}{page_suffix}{section_suffix}{chunk_suffix}  ({score_label})",
            expanded=(i == 1),
        ):
            if source and source != "unknown":
                st.markdown(
                    build_citation_link(
                        source,
                        page_number,
                        section_signature=section_signature,
                    )
                )
            st.markdown("**Snippet**")
            st.write(truncate(chunk.get("text", "")))
            st.caption(
                f"distance: {distance:.4f}" if isinstance(distance, float)
                else "distance: n/a"
            )
            if debug:
                st.markdown("**Metadata**")
                st.json(
                    {
                        "source": source,
                        "chunk_idx": chunk_idx,
                        "distance": distance,
                        "similarity": similarity,
                        "metadata": chunk.get("metadata", {}),
                    }
                )
                st.markdown("**Full chunk text**")
                st.code(chunk.get("text", "") or "(empty)", language="markdown")


def render_sidebar(
    retriever_info: Optional[Dict[str, str]],
    *,
    max_history_messages: int,
) -> Dict[str, Any]:
    with st.sidebar:
        st.header("Settings")

        # BL-07 — mode toggle. Returning the internal identifier (not the
        # emoji label) keeps the rest of the UI free of UX strings.
        mode_label = st.radio(
            "Режим работы",
            options=[MODE_LABELS[m] for m in MODE_ORDER],
            index=0,
            help=(
                "📊 **Анализ ТЗ** — stateless проверка требований без истории "
                "(минимум токенов).\n\n"
                "💬 **Консультация** — диалог с базой знаний, "
                f"≤ {max_history_messages} последних сообщений сохраняется."
            ),
        )
        mode = next(
            (m for m, label in MODE_LABELS.items() if label == mode_label),
            MODE_STATELESS,
        )

        debug_mode = st.toggle(
            "Debug Mode",
            value=False,
            help="Show raw chunk metadata and the prompt sent to the LLM.",
        )

        top_k = st.slider(
            "Top K chunks",
            min_value=1,
            max_value=10,
            value=DEFAULT_TOP_K,
            help="Number of source chunks retrieved from ChromaDB.",
        )

        clear_history = False
        if mode == MODE_CONSULTATION:
            st.divider()
            history_len = len(st.session_state.get("messages", []))
            st.caption(
                f"История: {history_len} / {max_history_messages} сообщений"
            )
            clear_history = st.button(
                "🧹 Очистить историю",
                help="Удаляет все сохранённые сообщения текущей консультации.",
            )

        st.divider()
        st.caption("LLM fallback chain: **GigaChat → OpenRouter → Ollama**")
        if retriever_info:
            st.caption(f"Vector store: `{retriever_info['persist_directory']}`")
            st.caption(f"Collection: `{retriever_info['collection_name']}`")
            st.caption(f"Embedding model: `{retriever_info['model_name']}`")

        if not ENV_PATH.exists():
            st.warning(
                "`.env` not found at repo root — copy `.env.example` to `.env` "
                "and fill in your API keys to enable LLM calls."
            )

    return {
        "mode": mode,
        "debug": debug_mode,
        "top_k": top_k,
        "clear_history": clear_history,
    }


def _reset_history() -> None:
    """Clear the consultation chat buffer in Streamlit session state."""
    st.session_state["messages"] = []


def _ensure_mode_state(active_mode: str) -> None:
    """Initialise ``st.session_state`` and reset history on mode change.

    The DoD for issue #93 requires automatic history reset whenever the user
    switches between Analysis and Consultation, so the consultation buffer
    never leaks token-costly context into stateless analysis runs.
    """
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    previous = st.session_state.get("ui_mode")
    if previous != active_mode:
        st.session_state["ui_mode"] = active_mode
        _reset_history()


def _new_run_id() -> str:
    return str(uuid4())


def _is_mode_processing(mode: str) -> bool:
    return bool(
        st.session_state.get(SESSION_PROCESSING_KEY)
        and st.session_state.get(SESSION_PENDING_MODE_KEY) == mode
    )


def _has_pending_generation(mode: str) -> bool:
    return bool(
        st.session_state.get(SESSION_PENDING_QUERY_KEY)
        and st.session_state.get(SESSION_PENDING_MODE_KEY) == mode
    )


def _last_error_matches(mode: str) -> bool:
    error = st.session_state.get(SESSION_LAST_ERROR_KEY)
    return isinstance(error, dict) and error.get("mode") == mode


def _queue_generation(query: str, mode: str) -> None:
    """Queue a generation request and rerun so controls render disabled."""
    clean_query = query.strip()
    st.session_state[SESSION_LAST_QUERY_KEY] = clean_query
    st.session_state[SESSION_PENDING_QUERY_KEY] = clean_query
    st.session_state[SESSION_PENDING_MODE_KEY] = mode
    st.session_state[SESSION_PENDING_RUN_ID_KEY] = _new_run_id()
    st.session_state[SESSION_PROCESSING_KEY] = True
    st.session_state.pop(SESSION_LAST_ERROR_KEY, None)
    if mode == MODE_STATELESS:
        st.session_state.pop(SESSION_LAST_ANALYSIS_RESULT_KEY, None)
    st.rerun()


def _finish_pending_generation() -> None:
    st.session_state.pop(SESSION_PENDING_QUERY_KEY, None)
    st.session_state.pop(SESSION_PENDING_MODE_KEY, None)
    st.session_state.pop(SESSION_PENDING_RUN_ID_KEY, None)
    st.session_state[SESSION_PROCESSING_KEY] = False


def _render_retry_notice(mode: str) -> bool:
    """Render the current retryable error block for ``mode``.

    Returns ``True`` only when the retry button was clicked. In real Streamlit
    that path immediately calls ``st.rerun()`` via :func:`_queue_generation`.
    """
    error = st.session_state.get(SESSION_LAST_ERROR_KEY)
    if not isinstance(error, dict) or error.get("mode") != mode:
        return False

    st.error(str(error.get("message") or UI_GENERATION_ERROR_TEXT))
    st.caption(f"Причина: {error.get('reason') or UI_GENERATION_ERROR_REASON}")
    st.download_button(
        "📥 Скачать логи",
        data=error.get("report_bytes") or b"",
        file_name=_error_report_filename(),
        mime="text/plain; charset=utf-8",
        key=f"download_error_{mode}",
    )
    if get_debug_error_details():
        with st.expander("ℹ️ Как исправить", expanded=False):
            report = error.get("report") if isinstance(error.get("report"), dict) else {}
            recommendations = report.get("recommendations") or [
                "Проверьте конфигурацию провайдеров и серверные логи по run_id."
            ]
            for item in recommendations:
                st.markdown(f"- {item}")
            st.caption(f"run_id: {error.get('run_id', '')}")
    clicked = st.button(
        RETRY_BUTTON_LABEL,
        key=f"retry_{mode}",
        disabled=_is_mode_processing(mode),
    )
    if not clicked:
        return False

    query = str(st.session_state.get(SESSION_LAST_QUERY_KEY) or "").strip()
    if not query:
        st.warning("Нет сохранённого запроса для повторной попытки.")
        return False
    _queue_generation(query, mode)
    return True


def _error_report_filename() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"clarify_error_{timestamp}.txt"


def _generation_error_types() -> tuple[type[BaseException], ...]:
    from src.llm.client import LLMError, RetriableProviderError

    types: List[type[BaseException]] = [
        KBError,
        LLMError,
        RetriableProviderError,
        TimeoutError,
        ConnectionError,
    ]
    try:
        import requests  # type: ignore

        types.extend(
            [
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ]
        )
    except ImportError:
        pass
    return tuple(types)


def _provider_for_exception(exc: BaseException) -> str:
    provider = getattr(exc, "provider", None)
    if provider:
        return str(provider)
    if isinstance(exc, KBError):
        return "knowledge_base"
    return "rag_fallback_chain"


def _provider_count() -> int:
    cfg = load_llm_config()
    providers = cfg.get("providers") if isinstance(cfg, dict) else None
    if isinstance(providers, dict) and providers:
        return len(providers)
    fallback = cfg.get("fallback_providers") if isinstance(cfg, dict) else None
    if isinstance(fallback, list) and fallback:
        return len(fallback)
    return 1


def _safe_log_ui_error(
    *,
    run_id: str,
    mode: str,
    provider: str,
    exc: BaseException,
) -> None:
    """Log UI failures without allowing logging failures to break the UI."""
    try:
        logger.error(
            "ui_generation_failed",
            extra={
                "run_id": run_id,
                "error_type": type(exc).__name__,
                "provider": provider,
                "ui_mode": mode,
            },
        )
    except Exception:  # noqa: BLE001 - logging must never break Streamlit
        pass


def _safe_log_prompt_built(
    *,
    run_id: str,
    mode: str,
    history_messages: int,
    approx_tokens: int,
) -> None:
    try:
        logger.info(
            "ui_prompt_built mode=%s history_messages=%d approx_tokens=%d",
            mode,
            history_messages,
            approx_tokens,
            extra={"run_id": run_id, "ui_mode": mode},
        )
    except Exception:  # noqa: BLE001 - logging must never break Streamlit
        pass


def _store_generation_error(
    *,
    query: str,
    mode: str,
    run_id: str,
    exc: BaseException,
    provider: Optional[str] = None,
) -> None:
    from src.utils.error_handler import ErrorHandler

    provider_name = provider or _provider_for_exception(exc)
    llm_config = load_llm_config()
    provider_count = _provider_count()
    handler = ErrorHandler()
    error_context = handler.collect_error_context(
        provider_name,
        exc if isinstance(exc, Exception) else Exception(str(exc)),
        {
            "run_id": run_id,
            "provider_count": provider_count,
            "error_type": type(exc).__name__,
        },
    )
    report = handler.generate_error_report(
        [error_context],
        query,
        {
            **llm_config,
            "run_id": run_id,
            "provider": provider_name,
            "provider_count": provider_count,
        },
    )
    st.session_state[SESSION_LAST_QUERY_KEY] = query.strip()
    st.session_state[SESSION_LAST_ERROR_KEY] = {
        "mode": mode,
        "message": UI_GENERATION_ERROR_TEXT,
        "reason": report.get("reason")
        or f"{UI_GENERATION_ERROR_REASON} (1 из {provider_count})",
        "run_id": run_id,
        "error_type": type(exc).__name__,
        "provider": provider_name,
        "report": report,
        "report_bytes": handler.export_to_txt(report),
    }
    _safe_log_ui_error(
        run_id=run_id,
        mode=mode,
        provider=provider_name,
        exc=exc,
    )
    st.error(UI_GENERATION_ERROR_TEXT)


# ---------------------------------------------------------------------- main --
def main() -> None:
    load_dotenv(ENV_PATH, override=False)

    st.title("Clarify Engine - KB Test UI")
    st.caption(
        "Query the indexed knowledge base and let an LLM answer with citations."
    )

    llm_config = load_llm_config()
    max_history_messages = get_max_history_messages(llm_config)

    retriever_info: Optional[Dict[str, str]] = None
    try:
        retriever = get_retriever()
        retriever_info = {
            "persist_directory": str(retriever.persist_directory),
            "collection_name": retriever.collection_name,
            "model_name": retriever.model_name,
        }
    except KBError as exc:
        run_id = _new_run_id()
        st.error("Не удалось подготовить поиск по базе знаний.")
        _safe_log_ui_error(
            run_id=run_id,
            mode="initialization",
            provider="knowledge_base",
            exc=exc,
        )

    settings = render_sidebar(
        retriever_info, max_history_messages=max_history_messages
    )
    _ensure_mode_state(settings["mode"])
    if settings.get("clear_history"):
        _reset_history()
        st.success("История консультации очищена.")

    if settings["mode"] == MODE_CONSULTATION:
        _run_consultation_mode(
            settings=settings,
            max_history_messages=max_history_messages,
        )
    else:
        _run_analysis_mode(settings=settings)


def _run_analysis_mode(*, settings: Dict[str, Any]) -> None:
    """Stateless TZ-analysis path — no history, identical to pre-BL-07 UX."""
    processing = _is_mode_processing(MODE_STATELESS)
    _render_analysis_export_button()
    query = st.text_area(
        "Your query",
        height=140,
        placeholder="Ask a question about the indexed knowledge base…",
        key="kb_query",
        disabled=processing,
    )
    submitted = st.button("Search KB", type="primary", disabled=processing)
    _render_retry_notice(MODE_STATELESS)

    if submitted:
        if not query.strip():
            st.warning("Please enter a query before searching.")
            return
        _queue_generation(query, MODE_STATELESS)
        return

    if _has_pending_generation(MODE_STATELESS):
        _process_pending_analysis(settings)
        return

    if _render_analysis_result(settings["debug"]):
        return

    if not _last_error_matches(MODE_STATELESS):
        st.info(
            "Enter a query and click **Search KB** to retrieve chunks and an "
            "LLM-generated answer."
        )


def _process_pending_analysis(settings: Dict[str, Any]) -> None:
    query = str(st.session_state.get(SESSION_PENDING_QUERY_KEY) or "").strip()
    run_id = str(st.session_state.get(SESSION_PENDING_RUN_ID_KEY) or _new_run_id())
    if not query:
        _finish_pending_generation()
        st.warning("Please enter a query before searching.")
        st.rerun()
        return

    answer, chunks, prompt = _retrieve_and_answer(
        query=query,
        top_k=settings["top_k"],
        history=None,
        mode=MODE_STATELESS,
        run_id=run_id,
    )
    if answer is not None:
        rendered_answer = linkify_citations(answer or "", chunks)
        st.session_state[SESSION_LAST_ANALYSIS_RESULT_KEY] = {
            "query": query,
            "answer": rendered_answer,
            "chunks": chunks,
            "prompt": prompt,
        }
        st.session_state["analysis_export_rows"] = [
            _build_analysis_export_row(query, rendered_answer, chunks)
        ]
        st.session_state.pop(SESSION_LAST_ERROR_KEY, None)

    _finish_pending_generation()
    st.rerun()


def _render_analysis_result(debug: bool) -> bool:
    result = st.session_state.get(SESSION_LAST_ANALYSIS_RESULT_KEY)
    if not isinstance(result, dict):
        return False

    chunks = result.get("chunks") or []
    prompt = str(result.get("prompt") or "")
    rendered_answer = str(result.get("answer") or "")

    st.subheader("LLM Response")
    st.markdown(rendered_answer or "_(empty response)_")
    _render_analysis_export_button()

    if debug and prompt:
        with st.expander("Prompt sent to LLM", expanded=False):
            st.code(prompt, language="markdown")

    render_chunks(chunks, debug)
    return True


def _run_consultation_mode(
    *,
    settings: Dict[str, Any],
    max_history_messages: int,
) -> None:
    """Stateful chat path — keeps ≤ ``max_history_messages`` recent turns."""
    processing = _is_mode_processing(MODE_CONSULTATION)
    st.caption(
        "Режим консультации: ассистент помнит последние "
        f"{max_history_messages} сообщений. Используйте "
        "**🧹 Очистить историю** в сайдбаре, чтобы начать диалог заново."
    )
    _render_chat_export_button()

    messages = list(st.session_state.get("messages", []))
    latest_assistant_idx = _latest_assistant_message_index(messages)
    for idx, msg in enumerate(messages):
        with st.chat_message(msg.get("role", "user")):
            st.markdown(msg.get("content", ""))
            if (
                settings["debug"]
                and idx == latest_assistant_idx
                and str(msg.get("role", "")).lower() == "assistant"
            ):
                prompt = str(msg.get("prompt") or "")
                chunks = msg.get("chunks") or []
                if prompt:
                    with st.expander("Prompt sent to LLM", expanded=False):
                        st.code(prompt, language="markdown")
                if chunks:
                    render_chunks(chunks, settings["debug"])

    _render_retry_notice(MODE_CONSULTATION)

    query = st.chat_input(
        "Задайте вопрос по документации…",
        disabled=processing,
    )
    if query and not processing:
        _queue_generation(query, MODE_CONSULTATION)
        return

    if _has_pending_generation(MODE_CONSULTATION):
        pending_query = str(
            st.session_state.get(SESSION_PENDING_QUERY_KEY) or ""
        ).strip()
        if pending_query:
            with st.chat_message("user"):
                st.markdown(pending_query)
        _process_pending_consultation(
            settings=settings,
            max_history_messages=max_history_messages,
        )
        return

    if (
        not query
        and not st.session_state.get("messages")
        and not _last_error_matches(MODE_CONSULTATION)
    ):
        st.info("Введите вопрос ниже, чтобы начать консультацию по базе знаний.")


def _latest_assistant_message_index(messages: Sequence[Dict[str, Any]]) -> Optional[int]:
    for idx in range(len(messages) - 1, -1, -1):
        if str(messages[idx].get("role", "")).lower() == "assistant":
            return idx
    return None


def _process_pending_consultation(
    *,
    settings: Dict[str, Any],
    max_history_messages: int,
) -> None:
    query = str(st.session_state.get(SESSION_PENDING_QUERY_KEY) or "").strip()
    run_id = str(st.session_state.get(SESSION_PENDING_RUN_ID_KEY) or _new_run_id())
    if not query:
        _finish_pending_generation()
        st.warning("Нет сохранённого запроса для повторной попытки.")
        st.rerun()
        return

    # BL-07: trim BEFORE the call so we never forward more than the configured
    # number of past turns. The fresh user message is appended *after* the
    # answer is generated, otherwise it would count against the limit twice.
    history = trim_history(
        st.session_state.get("messages", []), max_history_messages
    )
    answer, chunks, prompt = _retrieve_and_answer(
        query=query,
        top_k=settings["top_k"],
        history=history,
        mode=MODE_CONSULTATION,
        run_id=run_id,
    )
    if answer is not None:
        rendered_answer = linkify_citations(answer or "", chunks)
        # Persist the turn and trim again so the buffer in session_state never
        # grows beyond the configured cap (defence-in-depth — the trim above
        # only protects the prompt; this one protects the UI state).
        messages = list(st.session_state.get("messages", []))
        messages.append({"role": "user", "content": query})
        messages.append(
            {
                "role": "assistant",
                "content": rendered_answer or "",
                "prompt": prompt,
                "chunks": chunks,
            }
        )
        st.session_state["messages"] = trim_history(messages, max_history_messages)
        st.session_state.pop(SESSION_LAST_ERROR_KEY, None)

    _finish_pending_generation()
    st.rerun()


def _build_analysis_export_row(
    query: str,
    answer: str,
    chunks: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    citations = []
    for chunk in chunks:
        source = str(chunk.get("source") or "").strip()
        if source and source not in citations:
            citations.append(source)
    return {
        "requirement_id": "ui-query-1",
        "requirement_text": query,
        "classification": "",
        "reasoning": answer,
        "citations": "; ".join(citations),
    }


def _render_analysis_export_button() -> None:
    rows = st.session_state.get("analysis_export_rows", [])
    disabled = not bool(rows)
    if rows:
        from src.utils.export import export_to_excel

        data = export_to_excel(rows)
    else:
        data = BytesIO()
    st.download_button(
        "📥 Скачать отчет (.xlsx)",
        data=data,
        file_name="clarify-analysis-report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=disabled,
    )


def _render_chat_export_button() -> None:
    history = st.session_state.get("messages", [])
    disabled = not bool(history)
    if history:
        from src.utils.export import export_chat_to_markdown

        data = export_chat_to_markdown(history)
    else:
        data = BytesIO()
    st.download_button(
        "📥 Сохранить диалог (.md)",
        data=data,
        file_name="clarify-consultation-dialog.md",
        mime="text/markdown; charset=utf-8",
        disabled=disabled,
    )


def _retrieve_and_answer(
    *,
    query: str,
    top_k: int,
    history: Optional[Sequence[Dict[str, str]]],
    mode: str,
    run_id: str,
) -> tuple[Optional[str], List[Dict[str, Any]], str]:
    """Run retrieval + LLM call and surface errors via Streamlit.

    Returns ``(answer, chunks, prompt)``. ``answer`` is ``None`` when either
    retrieval or the LLM call failed — the caller should simply ``return`` so
    Streamlit can render the partial state already written via ``st.error``.
    """
    st.session_state[SESSION_LAST_QUERY_KEY] = query.strip()
    llm_config = load_llm_config()

    try:
        with st.spinner("Searching knowledge base…"):
            chunks = search_kb(
                query,
                top_k,
                use_parent_context=(mode == MODE_CONSULTATION),
                ui_mode=mode,
                llm_config=llm_config,
                enable_query_expansion=(mode == MODE_CONSULTATION),
            )
    except _generation_error_types() as exc:
        _store_generation_error(
            query=query,
            mode=mode,
            run_id=run_id,
            exc=exc,
            provider="knowledge_base",
        )
        return None, [], ""
    except Exception as exc:  # noqa: BLE001 - keep UI stable on retriever bugs
        _store_generation_error(
            query=query,
            mode=mode,
            run_id=run_id,
            exc=exc,
            provider="knowledge_base",
        )
        return None, [], ""
    prompt = build_user_prompt(query, chunks, history=history)
    prompt_tokens = estimate_token_count(prompt)
    history_msgs = len(history) if history else 0
    _safe_log_prompt_built(
        run_id=run_id,
        mode=mode,
        history_messages=history_msgs,
        approx_tokens=prompt_tokens,
    )

    try:
        with st.spinner("Calling LLM (GigaChat → OpenRouter → Ollama)…"):
            client = get_llm_client()
            answer = client.generate_rag_response(get_rag_system_prompt(), prompt)
    except _generation_error_types() as exc:
        _store_generation_error(
            query=query,
            mode=mode,
            run_id=run_id,
            exc=exc,
        )
        render_chunks(chunks, False)
        return None, chunks, prompt
    except Exception as exc:  # noqa: BLE001 - no raw tracebacks in Streamlit
        _store_generation_error(
            query=query,
            mode=mode,
            run_id=run_id,
            exc=exc,
        )
        render_chunks(chunks, False)
        return None, chunks, prompt

    return answer, chunks, prompt


if __name__ == "__main__":
    main()
