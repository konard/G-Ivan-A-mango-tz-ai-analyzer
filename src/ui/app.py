"""Streamlit UI for testing the Clarify Engine knowledge-base RAG pipeline.

Run locally with::

    streamlit run src/ui/app.py

The UI is intentionally minimal and self-contained: it queries the ChromaDB
collection populated by ``knowledge_base/indexing/build_index.py``, embeds the
user query with ``BAAI/bge-m3`` and asks the active LLM provider (DeepSeek or
GigaChat) to answer using the retrieved chunks as context. All provider
metadata is read from ``configs/llm_config.yaml``; secrets come from ``.env``.

The module purposefully avoids LangChain/LlamaIndex and any framework that
hides retrieval/LLM behaviour — only ``streamlit``, ``chromadb``, ``requests``,
``yaml``, ``dotenv`` and ``sentence-transformers`` (needed to load BAAI/bge-m3)
are used.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
ENV_PATH = PROJECT_ROOT / ".env"

# Per issue #70 the UI points ChromaDB at ``knowledge_base/vector_store/``.
VECTOR_STORE_PATH = PROJECT_ROOT / "knowledge_base" / "vector_store"
COLLECTION_NAME = "clarify_engine_kb"
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"

DEFAULT_TOP_K = 5
CHUNK_PREVIEW_CHARS = 600
LLM_REQUEST_TIMEOUT = 60

PROVIDER_DISPLAY = {"deepseek": "DeepSeek", "gigachat": "GigaChat"}
SYSTEM_PROMPT = (
    "You are an assistant for the Clarify Engine knowledge base.\n"
    "Answer the user's question using ONLY the provided context chunks. "
    "Quote source filenames in square brackets (e.g. [filename.pdf]) when you "
    "rely on a chunk. If the context is insufficient, say so explicitly.\n"
    "Respond in Markdown."
)


# -------------------------------------------------------------------- errors --
class LLMError(RuntimeError):
    """User-facing error raised when an LLM provider cannot complete a call."""


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


def available_providers(config: Dict[str, Any]) -> List[str]:
    """Return provider names declared in the LLM config (in priority order)."""
    providers = config.get("providers") or {}
    if isinstance(providers, dict) and providers:
        ordered = sorted(
            providers.keys(),
            key=lambda name: providers[name].get("priority", 99),
        )
        return ordered
    fallback = config.get("fallback_providers") or []
    return [str(item) for item in fallback]


def truncate(text: str, limit: int = CHUNK_PREVIEW_CHARS) -> str:
    """Trim ``text`` to ``limit`` characters and append ``...`` when truncated."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


# ----------------------------------------------------- cached resource loaders --
@st.cache_resource(show_spinner=f"Loading embedding model {EMBEDDING_MODEL_NAME}…")
def get_embedder(model_name: str = EMBEDDING_MODEL_NAME):
    """Load the sentence-transformers embedder (cached across reruns)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise KBError(
            "sentence-transformers is not installed. Run "
            "`pip install -r requirements.txt`."
        ) from exc
    try:
        return SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001
        raise KBError(f"Failed to load embedding model '{model_name}': {exc}") from exc


@st.cache_resource(show_spinner="Connecting to ChromaDB…")
def get_collection(persist_dir: str, collection_name: str):
    """Return a ChromaDB collection handle (cached across reruns)."""
    try:
        import chromadb
    except ImportError as exc:
        raise KBError(
            "chromadb is not installed. Run `pip install -r requirements.txt`."
        ) from exc
    try:
        client = chromadb.PersistentClient(path=persist_dir)
        return client.get_or_create_collection(name=collection_name)
    except Exception as exc:  # noqa: BLE001
        raise KBError(
            f"Failed to open ChromaDB at '{persist_dir}': {exc}"
        ) from exc


# ----------------------------------------------------------------- retrieval --
def embed_query(query: str) -> List[float]:
    """Embed ``query`` with the cached sentence-transformers model."""
    model = get_embedder()
    vector = model.encode(query, show_progress_bar=False)
    return [float(v) for v in vector.tolist()]


def search_kb(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Run a vector search and return chunk dicts ordered by similarity."""
    collection = get_collection(str(VECTOR_STORE_PATH), COLLECTION_NAME)
    try:
        total = collection.count()
    except Exception as exc:  # noqa: BLE001
        raise KBError(f"Failed to read collection '{COLLECTION_NAME}': {exc}") from exc
    if total == 0:
        raise KBError(
            f"Collection '{COLLECTION_NAME}' at '{VECTOR_STORE_PATH}' is empty. "
            "Run `python knowledge_base/indexing/build_index.py` first."
        )

    embedding = embed_query(query)
    try:
        raw = collection.query(
            query_embeddings=[embedding],
            n_results=max(1, int(top_k)),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:  # noqa: BLE001
        raise KBError(f"ChromaDB query failed: {exc}") from exc

    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    chunks: List[Dict[str, Any]] = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        meta = dict(meta or {})
        # Chromadb returns L2 distances by default; map them to a monotonic
        # (0, 1] similarity so the UI can show a number where higher is better.
        similarity: Optional[float]
        if dist is None:
            similarity = None
        else:
            similarity = 1.0 / (1.0 + float(dist))
        chunks.append(
            {
                "text": doc or "",
                "source": str(meta.get("source", "unknown")),
                "chunk_idx": meta.get("chunk_idx"),
                "distance": float(dist) if dist is not None else None,
                "similarity": similarity,
                "metadata": meta,
            }
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
        blocks.append(f"[{idx}] {source}\n{text}")
    return "\n\n".join(blocks)


def build_user_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    """Build the user message sent to the LLM."""
    context = _format_context(chunks)
    return (
        f"<context>\n{context}\n</context>\n\n"
        f"<question>{query.strip()}</question>"
    )


def _call_deepseek(prompt: str, system: str, cfg: Dict[str, Any]) -> str:
    import requests

    key_env = cfg.get("api_key_env", "DEEPSEEK_API_KEY")
    api_key = os.environ.get(key_env)
    if not api_key:
        raise LLMError(
            f"Missing DeepSeek API key. Set `{key_env}` in your `.env` file."
        )
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg.get("model", "deepseek-chat"),
                "temperature": float(cfg.get("temperature", 0.1)),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=LLM_REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise LLMError(f"DeepSeek request failed: {exc}") from exc

    if response.status_code == 401:
        raise LLMError("DeepSeek rejected the API key (HTTP 401).")
    if response.status_code >= 400:
        raise LLMError(
            f"DeepSeek returned HTTP {response.status_code}: {response.text[:300]}"
        )
    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected DeepSeek response shape: {exc}") from exc


def _call_gigachat(prompt: str, system: str, cfg: Dict[str, Any]) -> str:
    import requests

    creds_env = cfg.get("credentials_env", "GIGACHAT_AUTH")
    credentials = os.environ.get(creds_env) or os.environ.get("GIGACHAT_API_KEY")
    if not credentials:
        raise LLMError(
            f"Missing GigaChat credentials. Set `{creds_env}` "
            "(Base64 of client_id:client_secret) in your `.env` file."
        )
    try:
        token_resp = requests.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {credentials}",
                "RqUID": "00000000-0000-0000-0000-000000000000",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": "GIGACHAT_API_PERS"},
            timeout=LLM_REQUEST_TIMEOUT,
            verify=False,
        )
    except requests.exceptions.RequestException as exc:
        raise LLMError(f"GigaChat auth request failed: {exc}") from exc
    if token_resp.status_code >= 400:
        raise LLMError(
            f"GigaChat auth returned HTTP {token_resp.status_code}: "
            f"{token_resp.text[:300]}"
        )
    try:
        access_token = token_resp.json()["access_token"]
    except (ValueError, KeyError) as exc:
        raise LLMError(f"GigaChat auth response missing access_token: {exc}") from exc

    try:
        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg.get("model", "GigaChat-Pro"),
                "temperature": float(cfg.get("temperature", 0.1)),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=LLM_REQUEST_TIMEOUT,
            verify=False,
        )
    except requests.exceptions.RequestException as exc:
        raise LLMError(f"GigaChat request failed: {exc}") from exc
    if response.status_code >= 400:
        raise LLMError(
            f"GigaChat returned HTTP {response.status_code}: {response.text[:300]}"
        )
    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected GigaChat response shape: {exc}") from exc


ProviderCaller = Callable[[str, str, Dict[str, Any]], str]

PROVIDER_CALLERS: Dict[str, ProviderCaller] = {
    "deepseek": _call_deepseek,
    "gigachat": _call_gigachat,
}


def call_llm(provider_name: str, prompt: str, llm_config: Dict[str, Any]) -> str:
    """Dispatch ``prompt`` to the selected provider and return its raw text."""
    providers = llm_config.get("providers") or {}
    provider_cfg = providers.get(provider_name) or {}
    caller = PROVIDER_CALLERS.get(provider_name)
    if caller is None:
        raise LLMError(f"Provider '{provider_name}' is not supported by this UI.")
    return caller(prompt, SYSTEM_PROMPT, provider_cfg)


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
        score_label = (
            f"similarity={similarity:.4f}" if isinstance(similarity, float)
            else "similarity=n/a"
        )
        with st.expander(f"#{i} — {source}  ({score_label})", expanded=(i == 1)):
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
                        "chunk_idx": chunk.get("chunk_idx"),
                        "distance": distance,
                        "similarity": similarity,
                        "metadata": chunk.get("metadata", {}),
                    }
                )
                st.markdown("**Full chunk text**")
                st.code(chunk.get("text", "") or "(empty)", language="markdown")


def render_sidebar(provider_names: List[str], default_provider: str) -> Dict[str, Any]:
    with st.sidebar:
        st.header("Settings")
        debug_mode = st.toggle(
            "Debug Mode",
            value=False,
            help="Show raw chunk metadata and the prompt sent to the LLM.",
        )

        if provider_names:
            try:
                default_index = provider_names.index(default_provider)
            except ValueError:
                default_index = 0
            provider = st.selectbox(
                "LLM Provider",
                provider_names,
                index=default_index,
                format_func=lambda name: PROVIDER_DISPLAY.get(name, name),
            )
        else:
            provider = ""
            st.error(
                "No LLM providers are configured in `configs/llm_config.yaml`."
            )

        top_k = st.slider(
            "Top K chunks",
            min_value=1,
            max_value=10,
            value=DEFAULT_TOP_K,
            help="Number of source chunks retrieved from ChromaDB.",
        )

        st.divider()
        st.caption(f"Vector store: `{VECTOR_STORE_PATH.relative_to(PROJECT_ROOT)}`")
        st.caption(f"Collection: `{COLLECTION_NAME}`")
        st.caption(f"Embedding model: `{EMBEDDING_MODEL_NAME}`")

        if not ENV_PATH.exists():
            st.warning(
                "`.env` not found at repo root — copy `.env.example` to `.env` "
                "and fill in your API keys to enable LLM calls."
            )

    return {"debug": debug_mode, "provider": provider, "top_k": top_k}


# ---------------------------------------------------------------------- main --
def main() -> None:
    load_dotenv(ENV_PATH, override=False)

    llm_config = load_llm_config()
    provider_names = available_providers(llm_config)
    default_provider = str(
        llm_config.get("active_provider")
        or (provider_names[0] if provider_names else "")
    )

    st.title("Clarify Engine - KB Test UI")
    st.caption(
        "Query the indexed knowledge base and let an LLM answer with citations."
    )

    settings = render_sidebar(provider_names, default_provider)

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
    provider_name = settings["provider"]
    if not provider_name:
        st.error("Cannot call LLM: no provider is configured.")
        render_chunks(chunks, settings["debug"])
        return

    prompt = build_user_prompt(query, chunks)
    try:
        with st.spinner(f"Calling {PROVIDER_DISPLAY.get(provider_name, provider_name)}…"):
            answer = call_llm(provider_name, prompt, llm_config)
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
