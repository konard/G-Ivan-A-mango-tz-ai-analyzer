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
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - declared in requirements.txt
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False


# --------------------------------------------------------------------- paths --
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LLM_CONFIG_PATH = PROJECT_ROOT / "configs" / "llm_config.yaml"
EMBEDDING_CONFIG_PATH = PROJECT_ROOT / "configs" / "embedding_config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"
SOURCES_DIR = PROJECT_ROOT / "knowledge_base" / "sources"

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

# BL-08 (issue #94): the RAG system prompt is now a versioned artefact in
# ``prompts/``. The Streamlit module loads it lazily inside ``main()`` so an
# import of this module (e.g. from ``tests/test_citation_links.py``) never
# touches the filesystem. A minimal fallback is kept so the UI still renders
# something sensible when the prompt file is missing — operators should fix
# the install rather than edit the constant.
_SYSTEM_PROMPT_NAME = "system_rag"
_SYSTEM_PROMPT_VERSION = "v1.0"
_SYSTEM_PROMPT_FALLBACK = (
    "You are an assistant for the Clarify Engine knowledge base. "
    "Answer using ONLY the provided context chunks. "
    "Quote source filenames in square brackets when you rely on a chunk. "
    "Respond in Markdown."
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


# ----------------------------------------------------------------- retrieval --
def search_kb(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Run a vector search and return chunk dicts ordered by similarity."""
    retriever = get_retriever()
    try:
        chunks = retriever.search(query, top_k=top_k)
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
    sources_dir: Path = SOURCES_DIR,
) -> str:
    """Return a clickable Markdown citation pinned to a PDF page.

    Format follows the BL-09 spec: ``[source.pdf, стр. N](file:///abs/path#page=N)``.
    When the page number is missing or non-integer, the link still resolves to
    the source file (no ``#page`` anchor).
    """
    if not source:
        return ""
    abs_path = (sources_dir / source).resolve()
    page_int = _coerce_page(page)
    if page_int:
        label = f"{source}, стр. {page_int}"
        target = f"file://{abs_path}#page={page_int}"
    else:
        label = source
        target = f"file://{abs_path}"
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


def linkify_citations(
    answer: str,
    chunks: List[Dict[str, Any]],
    *,
    sources_dir: Path = SOURCES_DIR,
) -> str:
    """Rewrite ``[filename.pdf]`` placeholders in ``answer`` to BL-09 links.

    The replacement uses the highest-ranked chunk's ``page_number`` for each
    source. Citations whose source is not present in ``chunks`` are left
    untouched so the UI never invents page numbers.
    """
    if not answer:
        return answer
    page_by_source = _first_page_per_source(chunks)
    if not page_by_source:
        return answer

    pattern = re.compile(r"\[([^\[\]\(\)\n]+\.[A-Za-z0-9]{1,8})\](?!\()")

    def _replace(match: re.Match) -> str:
        source = match.group(1).strip()
        if source not in page_by_source:
            return match.group(0)
        link = build_citation_link(source, page_by_source[source], sources_dir=sources_dir)
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
        suffix = f" #chunk={chunk_idx}" if chunk_idx is not None else ""
        blocks.append(f"[{idx}] {source}{suffix}\n{text}")
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
        score_label = (
            f"similarity={similarity:.4f}" if isinstance(similarity, float)
            else "similarity=n/a"
        )
        chunk_suffix = f" · chunk={chunk_idx}" if chunk_idx is not None else ""
        page_suffix = f" · стр. {page_number}" if page_number else ""
        with st.expander(
            f"#{i} — {source}{page_suffix}{chunk_suffix}  ({score_label})",
            expanded=(i == 1),
        ):
            if source and source != "unknown":
                st.markdown(build_citation_link(source, page_number))
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
        st.error(str(exc))

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
    query = st.text_area(
        "Your query",
        height=140,
        placeholder="Ask a question about the indexed knowledge base…",
        key="kb_query",
    )
    submitted = st.button("Search KB", type="primary")

    if not submitted:
        st.info(
            "Enter a query and click **Search KB** to retrieve chunks and an "
            "LLM-generated answer."
        )
        return

    if not query.strip():
        st.warning("Please enter a query before searching.")
        return

    answer, chunks, prompt = _retrieve_and_answer(
        query=query,
        top_k=settings["top_k"],
        history=None,
    )
    if answer is None:
        return

    st.subheader("LLM Response")
    rendered_answer = linkify_citations(answer or "", chunks)
    st.markdown(rendered_answer or "_(empty response)_")

    if settings["debug"]:
        with st.expander("Prompt sent to LLM", expanded=False):
            st.code(prompt, language="markdown")

    render_chunks(chunks, settings["debug"])


def _run_consultation_mode(
    *,
    settings: Dict[str, Any],
    max_history_messages: int,
) -> None:
    """Stateful chat path — keeps ≤ ``max_history_messages`` recent turns."""
    st.caption(
        "Режим консультации: ассистент помнит последние "
        f"{max_history_messages} сообщений. Используйте "
        "**🧹 Очистить историю** в сайдбаре, чтобы начать диалог заново."
    )

    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg.get("role", "user")):
            st.markdown(msg.get("content", ""))

    query = st.chat_input("Задайте вопрос по документации…")
    if not query:
        if not st.session_state.get("messages"):
            st.info(
                "Введите вопрос ниже, чтобы начать консультацию по базе знаний."
            )
        return

    with st.chat_message("user"):
        st.markdown(query)

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
    )
    if answer is None:
        return

    rendered_answer = linkify_citations(answer or "", chunks)
    with st.chat_message("assistant"):
        st.markdown(rendered_answer or "_(empty response)_")
        if settings["debug"]:
            with st.expander("Prompt sent to LLM", expanded=False):
                st.code(prompt, language="markdown")
            render_chunks(chunks, settings["debug"])

    # Persist the turn and trim again so the buffer in session_state never
    # grows beyond the configured cap (defence-in-depth — the trim above only
    # protects the prompt; this one protects the UI state).
    messages = list(st.session_state.get("messages", []))
    messages.append({"role": "user", "content": query})
    messages.append({"role": "assistant", "content": rendered_answer or ""})
    st.session_state["messages"] = trim_history(messages, max_history_messages)


def _retrieve_and_answer(
    *,
    query: str,
    top_k: int,
    history: Optional[Sequence[Dict[str, str]]],
) -> tuple[Optional[str], List[Dict[str, Any]], str]:
    """Run retrieval + LLM call and surface errors via Streamlit.

    Returns ``(answer, chunks, prompt)``. ``answer`` is ``None`` when either
    retrieval or the LLM call failed — the caller should simply ``return`` so
    Streamlit can render the partial state already written via ``st.error``.
    """
    from src.llm.client import LLMError

    try:
        with st.spinner("Searching knowledge base…"):
            chunks = search_kb(query, top_k)
    except KBError as exc:
        st.error(str(exc))
        return None, [], ""

    prompt = build_user_prompt(query, chunks, history=history)
    prompt_tokens = estimate_token_count(prompt)
    history_msgs = len(history) if history else 0
    logger.info(
        "ui_prompt_built mode=%s history_messages=%d approx_tokens=%d",
        "consultation" if history is not None else "stateless",
        history_msgs,
        prompt_tokens,
    )

    try:
        with st.spinner("Calling LLM (GigaChat → OpenRouter → Ollama)…"):
            client = get_llm_client()
            answer = client.generate_rag_response(get_rag_system_prompt(), prompt)
    except LLMError as exc:
        st.error(str(exc))
        render_chunks(chunks, False)
        return None, chunks, prompt

    return answer, chunks, prompt


if __name__ == "__main__":
    main()
