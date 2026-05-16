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

from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import yaml

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

DEFAULT_TOP_K = 5
CHUNK_PREVIEW_CHARS = 600

PROVIDER_DISPLAY = {
    "gigachat": "GigaChat",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
}

SYSTEM_PROMPT = (
    "You are an assistant for the Clarify Engine knowledge base.\n"
    "Answer the user's question using ONLY the provided context chunks. "
    "Quote source filenames in square brackets (e.g. [filename.pdf]) when you "
    "rely on a chunk. If the context is insufficient, say so explicitly.\n"
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
@st.cache_resource(show_spinner="Loading retriever (embedding model + ChromaDB)…")
def get_retriever():
    """Build and cache a :class:`ChromaRetriever` from the embedding config."""
    from src.rag.retriever import ChromaRetriever

    try:
        return ChromaRetriever.from_config(
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


def build_user_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    """Build the user message sent to the LLM."""
    context = _format_context(chunks)
    return (
        f"<context>\n{context}\n</context>\n\n"
        f"<question>{query.strip()}</question>"
    )


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
        score_label = (
            f"similarity={similarity:.4f}" if isinstance(similarity, float)
            else "similarity=n/a"
        )
        chunk_suffix = f" · chunk={chunk_idx}" if chunk_idx is not None else ""
        with st.expander(
            f"#{i} — {source}{chunk_suffix}  ({score_label})", expanded=(i == 1)
        ):
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


def render_sidebar(retriever_info: Optional[Dict[str, str]]) -> Dict[str, Any]:
    with st.sidebar:
        st.header("Settings")
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

    return {"debug": debug_mode, "top_k": top_k}


# ---------------------------------------------------------------------- main --
def main() -> None:
    load_dotenv(ENV_PATH, override=False)

    st.title("Clarify Engine - KB Test UI")
    st.caption(
        "Query the indexed knowledge base and let an LLM answer with citations."
    )

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

    settings = render_sidebar(retriever_info)

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

    # 1. Retrieval ------------------------------------------------------------
    try:
        with st.spinner("Searching knowledge base…"):
            chunks = search_kb(query, settings["top_k"])
    except KBError as exc:
        st.error(str(exc))
        return

    # 2. LLM answer -----------------------------------------------------------
    from src.llm.client import LLMError

    prompt = build_user_prompt(query, chunks)
    try:
        with st.spinner("Calling LLM (GigaChat → OpenRouter → Ollama)…"):
            client = get_llm_client()
            answer = client.generate_rag_response(SYSTEM_PROMPT, prompt)
    except LLMError as exc:
        st.error(str(exc))
        render_chunks(chunks, settings["debug"])
        return

    st.subheader("LLM Response")
    st.markdown(answer or "_(empty response)_")

    if settings["debug"]:
        with st.expander("Prompt sent to LLM", expanded=False):
            st.code(prompt, language="markdown")

    render_chunks(chunks, settings["debug"])


if __name__ == "__main__":
    main()
