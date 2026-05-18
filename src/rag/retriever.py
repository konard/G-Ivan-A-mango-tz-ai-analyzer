"""Hybrid retriever combining BM25 lexical search and dense vector search.

Ranking is fused with Reciprocal Rank Fusion (RRF). The default embedder is a
real ``sentence-transformers`` ``BAAI/bge-m3`` model — there is **no** silent
fallback to a toy hash embedder. When the model cannot be loaded and no
explicit embedder is injected, the retriever raises ``RuntimeError`` (strict
embedder mode introduced in issue #45). Tests and offline scripts may opt out
by passing an embedder callable directly to :class:`HybridRetriever` or
:func:`build_retriever`.

Unified chunk format returned by :meth:`HybridRetriever.search` and by
:func:`reciprocal_rank_fusion`::

    {
        "text": str,    # chunk text
        "source": str,  # file name or document id
        "page": str,    # section / page label (empty string if unknown)
        "score": float, # fused RRF score
    }
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

from src.llm.validator import extract_json, validate_reflection_payload

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)

DEFAULT_EMBEDDING_CONFIG_PATH = "configs/embedding_config.yaml"
DEFAULT_TOP_K = 3
DEFAULT_RRF_K = 60
DEFAULT_PARENT_CONTEXT_MAX_CHARS = 6000

# Fallback used when ``vector_store.persist_directory`` is missing or unreadable
# in ``configs/embedding_config.yaml``. The indexer
# (``knowledge_base/indexing/build_index.py``) also writes here by default, so
# retriever and indexer stay in sync without extra configuration.
DEFAULT_VECTOR_STORE_DIR = "./chroma_data"
DEFAULT_COLLECTION_NAME = "clarify_engine_kb"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


def load_embedding_config(
    config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
) -> Dict[str, Any]:
    """Read ``configs/embedding_config.yaml`` and return its parsed content.

    Returns an empty dict on any failure so callers can rely on documented
    defaults via :func:`resolve_vector_store_path` and friends.
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning("Embedding config %s not found; using defaults.", path)
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def resolve_vector_store_path(
    config: Optional[Dict[str, Any]] = None,
    *,
    project_root: Optional[Path] = None,
) -> Path:
    """Resolve the ChromaDB persistence directory.

    Order of precedence:

    1. ``vector_store.persist_directory`` from ``configs/embedding_config.yaml``
       (relative paths are anchored at ``project_root`` when supplied).
    2. ``./chroma_data`` under ``project_root`` (or the current working
       directory if ``project_root`` is ``None``).

    The function never raises: an unreadable or missing config silently falls
    back to ``DEFAULT_VECTOR_STORE_DIR`` so the retriever and the UI behave
    identically when the configuration is partial.
    """
    cfg = config or {}
    vs_cfg = cfg.get("vector_store") if isinstance(cfg, dict) else None
    raw_path: Optional[str] = None
    if isinstance(vs_cfg, dict):
        value = vs_cfg.get("persist_directory")
        if isinstance(value, str) and value.strip():
            raw_path = value.strip()

    candidate = Path(raw_path) if raw_path else Path(DEFAULT_VECTOR_STORE_DIR)
    if not candidate.is_absolute() and project_root is not None:
        candidate = (project_root / candidate).resolve()
    return candidate


def resolve_collection_name(config: Optional[Dict[str, Any]] = None) -> str:
    """Resolve the ChromaDB collection name with a documented fallback."""
    cfg = config or {}
    vs_cfg = cfg.get("vector_store") if isinstance(cfg, dict) else None
    if isinstance(vs_cfg, dict):
        value = vs_cfg.get("collection_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return DEFAULT_COLLECTION_NAME


def resolve_embedding_model_name(config: Optional[Dict[str, Any]] = None) -> str:
    """Resolve the sentence-transformers model name (default: ``BAAI/bge-m3``)."""
    cfg = config or {}
    value = cfg.get("model_name") if isinstance(cfg, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_EMBEDDING_MODEL


@dataclass
class RetrievedChunk:
    """A single retrieval result with the project-wide unified format."""

    text: str
    source: str
    score: float
    page: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "page": self.page,
            "score": self.score,
            "metadata": self.metadata,
        }


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in _WORD_RE.findall(text or "")]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _hash_embedding(text: str, dim: int = 256) -> List[float]:
    """Deterministic bag-of-tokens hash embedding.

    This is **never** used as a silent fallback by the retriever (strict
    embedder mode, see :func:`_load_dense_embedder`). It is kept only for
    test fixtures that pass it explicitly via ``embedder=_hash_embedding`` and
    for benchmarking utilities that need a tokenizer-free baseline.
    """
    vec = [0.0] * dim
    for token in _tokenize(text):
        idx = hash(token) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


_STRICT_EMBEDDER_ERROR = "Embedding model unavailable. Strict mode enabled."


def _load_dense_embedder(
    config: Optional[Dict[str, Any]] = None,
) -> Callable[[str], Sequence[float]]:
    """Load the real sentence-transformers embedder defined by ``config``.

    Raises:
        RuntimeError: When the embedding model cannot be loaded. The error
            message is fixed to ``"Embedding model unavailable. Strict mode
            enabled."`` per the issue #45 contract.
    """
    cfg = config or {}
    model_name = str(cfg.get("model_name", "BAAI/bge-m3"))
    normalize = bool(cfg.get("normalize_embeddings", True))

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:
        raise RuntimeError(_STRICT_EMBEDDER_ERROR) from exc

    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_STRICT_EMBEDDER_ERROR) from exc

    def _embed(text: str) -> List[float]:
        vector = model.encode(
            text,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [float(x) for x in vector.tolist()]

    return _embed


def _page_from_metadata(metadata: Mapping[str, Any]) -> str:
    """Pick a reasonable ``page`` label from metadata.

    Looks at common keys: ``page``, ``section``, ``chapter``. Returns ``""``
    when nothing is available so the field is always present in results.
    """
    if not metadata:
        return ""
    for key in ("page", "section", "chapter"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def _result_key(item: Mapping[str, Any]) -> str:
    """Build a stable identifier for an RRF input item.

    Prefers an explicit ``id`` field, falls back to ``(source, page, text)``.
    """
    if not isinstance(item, Mapping):
        return repr(item)
    identifier = item.get("id")
    if identifier is not None:
        return f"id::{identifier}"
    source = item.get("source", "")
    page = item.get("page") or _page_from_metadata(item.get("metadata") or {})
    text = item.get("text", "")
    return f"sp::{source}::{page}::{text}"


def reciprocal_rank_fusion(
    bm25_results: Sequence[Mapping[str, Any]],
    dense_results: Sequence[Mapping[str, Any]],
    k: int = DEFAULT_RRF_K,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fuse two ranked result lists with Reciprocal Rank Fusion.

    The RRF score for each item is::

        score = Σ_over_lists  1 / (k + rank)

    where ``rank`` is 1-based. Items are deduplicated by ``id`` if present,
    otherwise by the tuple ``(source, page, text)``.

    Args:
        bm25_results: Ranked list of BM25 chunks (best first). Each chunk must
            be a mapping that at least contains ``text`` and ``source``.
        dense_results: Ranked list of dense (vector) chunks, same shape.
        k: RRF constant. Larger values flatten contributions of top ranks.
        top_k: Optional cap on the number of fused results. ``None`` keeps all.

    Returns:
        A ranked list of unified chunk dicts::

            {"text": str, "source": str, "page": str, "score": float,
             "metadata": dict}

        ``metadata`` is included as a courtesy for downstream consumers but
        the four primary keys above are guaranteed by the issue contract.
    """
    if k <= 0:
        raise ValueError("RRF k must be positive")

    fused: Dict[str, Dict[str, Any]] = {}

    def _absorb(items: Iterable[Mapping[str, Any]]) -> None:
        for rank, item in enumerate(items or [], start=1):
            if not isinstance(item, Mapping):
                continue
            key = _result_key(item)
            contribution = 1.0 / (k + rank)
            existing = fused.get(key)
            if existing is None:
                metadata = dict(item.get("metadata") or {})
                page = item.get("page") or _page_from_metadata(metadata)
                fused[key] = {
                    "text": str(item.get("text", "")),
                    "source": str(item.get("source", "unknown")),
                    "page": str(page or ""),
                    "score": contribution,
                    "metadata": metadata,
                }
            else:
                existing["score"] += contribution

    _absorb(bm25_results)
    _absorb(dense_results)

    ranked = sorted(fused.values(), key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item["score"] = round(item["score"], 6)
    if top_k is not None:
        ranked = ranked[: max(0, int(top_k))]
    return ranked


class _BM25:
    """Compact BM25 ranker used when ``rank_bm25`` is not installed."""

    def __init__(self, corpus: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.corpus = list(corpus)
        self.k1 = k1
        self.b = b
        self.doc_lengths = [len(doc) for doc in self.corpus]
        self.avgdl = sum(self.doc_lengths) / max(1, len(self.corpus))
        self.doc_freqs: List[Dict[str, int]] = []
        self.df: Dict[str, int] = {}
        for doc in self.corpus:
            freqs: Dict[str, int] = {}
            for token in doc:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)
            for token in freqs:
                self.df[token] = self.df.get(token, 0) + 1
        self.idf = {
            token: math.log(1 + (len(self.corpus) - freq + 0.5) / (freq + 0.5))
            for token, freq in self.df.items()
        }

    def get_scores(self, query_tokens: Sequence[str]) -> List[float]:
        scores = [0.0] * len(self.corpus)
        for q in query_tokens:
            idf = self.idf.get(q)
            if not idf:
                continue
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(q, 0)
                if tf == 0:
                    continue
                dl = self.doc_lengths[i] or 1
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        return scores


@dataclass
class _Document:
    text: str
    source: str
    metadata: Dict[str, Any]
    tokens: List[str]
    embedding: List[float]

    @property
    def page(self) -> str:
        return _page_from_metadata(self.metadata)


class HybridRetriever:
    """Hybrid BM25 + dense retriever with RRF re-ranking."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
    ) -> None:
        self.config = config or {}
        self.use_parent_context = bool(self.config.get("use_parent_context", False))
        self.parent_context_max_chars = int(
            self.config.get("parent_context_max_chars", DEFAULT_PARENT_CONTEXT_MAX_CHARS)
            or DEFAULT_PARENT_CONTEXT_MAX_CHARS
        )
        # Strict embedder mode (issue #45): when no embedder is injected by the
        # caller we *must* load the configured sentence-transformers model.
        # Failure to load raises ``RuntimeError`` — silently falling back to a
        # toy hash embedder would mask data quality regressions.
        self._embedder = embedder if embedder is not None else _load_dense_embedder(self.config)
        self._documents: List[_Document] = []
        self._bm25: Optional[_BM25] = None

    @property
    def top_k(self) -> int:
        return int(self.config.get("top_k", DEFAULT_TOP_K) or DEFAULT_TOP_K)

    @property
    def rrf_k(self) -> int:
        return int(self.config.get("rrf_k", DEFAULT_RRF_K) or DEFAULT_RRF_K)

    # ------------------------------------------------------------------ load --
    @classmethod
    def from_config(
        cls,
        config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
    ) -> "HybridRetriever":
        config: Dict[str, Any] = {}
        path = Path(config_path)
        if path.exists():
            try:
                config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                logger.warning("Failed to parse %s: %s", path, exc)
        else:
            logger.warning("Embedding config %s not found; using defaults.", path)
        return cls(config=config, embedder=embedder)

    # -------------------------------------------------------------- indexing --
    def add_documents(self, documents: Iterable[Dict[str, Any]]) -> None:
        """Index documents.

        Each document is a dict ``{"text": str, "source": str, "metadata": {...}}``.
        """
        for doc in documents:
            text = doc.get("text", "")
            if not text:
                continue
            source = doc.get("source", "unknown")
            metadata = doc.get("metadata", {}) or {}
            self._documents.append(
                _Document(
                    text=text,
                    source=source,
                    metadata=metadata,
                    tokens=_tokenize(text),
                    embedding=list(self._embedder(text)),
                )
            )
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        if not self._documents:
            self._bm25 = None
            return
        self._bm25 = _BM25([doc.tokens for doc in self._documents])

    # --------------------------------------------------------------- search --
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        rrf_k: Optional[int] = None,
        use_parent_context: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Run hybrid search.

        Defaults for ``top_k`` and ``rrf_k`` are read from
        ``configs/embedding_config.yaml`` (keys ``top_k``, ``rrf_k``). Callers
        may override either value, but the configuration is the single source
        of truth.

        Returns a list of unified chunk dicts shaped as
        ``{"text", "source", "page", "score", "metadata"}``.
        """
        if not query or not query.strip():
            return []
        if not self._documents:
            logger.warning("HybridRetriever.search called with no indexed documents.")
            return []

        effective_top_k = int(top_k) if top_k is not None else self.top_k
        effective_rrf_k = int(rrf_k) if rrf_k is not None else self.rrf_k

        query_tokens = _tokenize(query)
        bm25_scores = (
            self._bm25.get_scores(query_tokens) if self._bm25 else [0.0] * len(self._documents)
        )
        query_vec = list(self._embedder(query))
        dense_scores = [_cosine_similarity(query_vec, doc.embedding) for doc in self._documents]

        bm25_results = self._ranked_results(bm25_scores)
        dense_results = self._ranked_results(dense_scores)

        fused = reciprocal_rank_fusion(
            bm25_results=bm25_results,
            dense_results=dense_results,
            k=effective_rrf_k,
            top_k=effective_top_k,
        )
        parent_context_enabled = (
            bool(use_parent_context)
            if use_parent_context is not None
            else self.use_parent_context
        )
        if parent_context_enabled:
            return expand_parent_context(fused, max_chars=self.parent_context_max_chars)
        return fused

    def _ranked_results(self, scores: Sequence[float]) -> List[Dict[str, Any]]:
        """Order documents by raw score (desc) and emit chunk dicts."""
        order = [i for i in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True) if scores[i] > 0.0]
        results: List[Dict[str, Any]] = []
        for idx in order:
            doc = self._documents[idx]
            results.append(
                {
                    "id": f"{doc.source}#{idx}",
                    "text": doc.text,
                    "source": doc.source,
                    "page": doc.page,
                    "score": float(scores[idx]),
                    "metadata": doc.metadata,
                }
            )
        return results


def build_retriever(
    documents: Optional[Iterable[Dict[str, Any]]] = None,
    config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
    embedder: Optional[Callable[[str], Sequence[float]]] = None,
) -> HybridRetriever:
    """Convenience factory: build a retriever and pre-index documents.

    ``embedder`` exists for tests and offline scripts only. Production callers
    should rely on the default sentence-transformers loader (strict mode).
    """
    retriever = HybridRetriever.from_config(config_path=config_path, embedder=embedder)
    if documents:
        retriever.add_documents(documents)
    return retriever


class ParentAwareRetriever:
    """Wrapper that turns child chunk hits into parent section contexts.

    The wrapped retriever is always asked for child chunks. Parent expansion is
    applied once after any outer retrieval strategy (multi-hop or query
    expansion) has produced its final ranked list, which prevents duplicate
    parent sections when several child hits belong to the same section.
    """

    def __init__(
        self,
        retriever: Any,
        *,
        max_chars: int = DEFAULT_PARENT_CONTEXT_MAX_CHARS,
    ) -> None:
        self.retriever = retriever
        self.parent_context_max_chars = int(
            max_chars or DEFAULT_PARENT_CONTEXT_MAX_CHARS
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.retriever, name)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        **search_kwargs: Any,
    ) -> List[Dict[str, Any]]:
        kwargs = dict(search_kwargs)
        kwargs["use_parent_context"] = False
        if top_k is not None:
            kwargs["top_k"] = top_k
        try:
            child_hits = self.retriever.search(query, **kwargs)
        except TypeError as exc:
            if "use_parent_context" not in str(exc):
                raise
            kwargs.pop("use_parent_context", None)
            child_hits = self.retriever.search(query, **kwargs)

        parents = expand_parent_context(
            list(child_hits or []),
            max_chars=self.parent_context_max_chars,
        )
        if top_k is None:
            return parents
        return parents[: max(0, int(top_k))]


def _parent_id(metadata: Mapping[str, Any], source: str) -> str:
    explicit = metadata.get("parent_id") or metadata.get("section_id")
    if explicit:
        return str(explicit)
    section_number = str(metadata.get("section_number") or "").strip()
    section_title = str(metadata.get("section_title") or "").strip()
    if section_number or section_title:
        return f"{source}::{section_number}::{section_title}"
    return f"{source}::document"


def _bounded_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def expand_parent_context(
    chunks: Sequence[Mapping[str, Any]],
    *,
    max_chars: int = DEFAULT_PARENT_CONTEXT_MAX_CHARS,
) -> List[Dict[str, Any]]:
    """Collapse child chunk hits into parent section contexts.

    Child hits keep the original ranking signal, while returned ``text`` uses
    ``metadata.parent_text`` when available. The result count may shrink because
    multiple child chunks from one section map to a single parent.
    """
    grouped: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for chunk in chunks:
        meta = dict(chunk.get("metadata") or {})
        source = str(chunk.get("source") or meta.get("source") or "unknown")
        parent_id = _parent_id(meta, source)
        parent_text = str(meta.get("parent_text") or chunk.get("text") or "")
        parent_text = _bounded_text(parent_text.strip(), max_chars)
        existing = grouped.get(parent_id)
        child_ref = {
            "source": source,
            "chunk_idx": chunk.get("chunk_idx", meta.get("chunk_idx")),
            "score": chunk.get("score"),
        }
        if existing is None:
            parent_meta = dict(meta)
            parent_meta["parent_id"] = parent_id
            parent_meta["parent_context"] = True
            grouped[parent_id] = {
                "text": parent_text,
                "source": source,
                "chunk_idx": chunk.get("chunk_idx", meta.get("chunk_idx")),
                "distance": chunk.get("distance"),
                "similarity": chunk.get("similarity"),
                "score": float(chunk.get("score") or 0.0),
                "metadata": parent_meta,
                "page": chunk.get("page") or _page_from_metadata(meta),
                "child_chunks": [child_ref],
            }
            order.append(parent_id)
        else:
            existing["score"] = max(
                float(existing.get("score") or 0.0),
                float(chunk.get("score") or 0.0),
            )
            existing.setdefault("child_chunks", []).append(child_ref)
    return [grouped[parent_id] for parent_id in order]


# ------------------------------------------------------------- Iterative RAG --
ReflectionCall = Callable[[str], Any]


def _chunk_dedupe_key(chunk: Mapping[str, Any]) -> Tuple[str, str]:
    """Return the BL-11 cross-hop dedupe key for a retrieved chunk."""
    meta = chunk.get("metadata") or {}
    source = str(chunk.get("source") or meta.get("source") or "unknown")
    chunk_idx = chunk.get("chunk_idx", meta.get("chunk_idx"))
    if chunk_idx is not None:
        return source, str(chunk_idx)

    # The production index is required to carry chunk_idx, but tests and
    # degraded data may not. Keep such chunks distinct unless their visible
    # identity is also identical.
    page = str(chunk.get("page") or _page_from_metadata(meta))
    text = str(chunk.get("text") or "")
    return source, f"{page}::{text}"


def _append_deduplicated(
    existing: Sequence[Mapping[str, Any]],
    new_chunks: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Append new chunks, preserving first-seen order by ``(source, chunk_idx)``."""
    merged: List[Dict[str, Any]] = [dict(chunk) for chunk in existing]
    seen = {_chunk_dedupe_key(chunk) for chunk in merged}
    for chunk in new_chunks:
        if not isinstance(chunk, Mapping):
            continue
        key = _chunk_dedupe_key(chunk)
        if key in seen:
            continue
        merged.append(dict(chunk))
        seen.add(key)
    return merged


def _normalise_max_hops(value: Any) -> int:
    try:
        hops = int(value)
    except (TypeError, ValueError):
        return 2
    return max(1, hops)


def _normalise_confidence_threshold(value: Any) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return 0.8
    return min(1.0, max(0.0, threshold))


def build_reflection_user_prompt(
    question: str,
    chunks: Sequence[Mapping[str, Any]],
    *,
    current_query: Optional[str] = None,
) -> str:
    """Build the reflection judge user message for the current hop."""
    context_blocks: List[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata") or {}
        source = str(chunk.get("source") or meta.get("source") or "unknown")
        chunk_idx = chunk.get("chunk_idx", meta.get("chunk_idx"))
        page = chunk.get("page") or _page_from_metadata(meta)
        chunk_suffix = f" chunk_idx={chunk_idx}" if chunk_idx is not None else ""
        page_suffix = f" page={page}" if page else ""
        text = str(chunk.get("text") or "").strip()
        context_blocks.append(
            f"[{idx}] source={source}{chunk_suffix}{page_suffix}\n{text}"
        )
    context = "\n\n".join(context_blocks) if context_blocks else "(no context)"
    query_block = (
        f"\n<current_query>{current_query.strip()}</current_query>"
        if current_query and current_query.strip() != question.strip()
        else ""
    )
    return (
        f"<question>{question.strip()}</question>"
        f"{query_block}\n\n"
        f"<context>\n{context}\n</context>"
    )


class IterativeRetriever:
    """Multi-hop wrapper over an existing retriever.

    The wrapper performs one normal search, asks a reflection LLM whether the
    accumulated context is sufficient, and optionally follows up with one or
    more reformulated searches. Reflection failures are deliberately swallowed:
    callers receive the last accumulated context so the UI can continue to the
    final answer generation path.
    """

    def __init__(
        self,
        retriever: Any,
        *,
        reflection_call: ReflectionCall,
        max_hops: int = 2,
        min_confidence_to_stop: float = 0.8,
    ) -> None:
        self.retriever = retriever
        self.reflection_call = reflection_call
        self.max_hops = _normalise_max_hops(max_hops)
        self.min_confidence_to_stop = _normalise_confidence_threshold(
            min_confidence_to_stop
        )

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_parent_context: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        original_query = query.strip()
        current_query = original_query
        seen_queries = {current_query}
        accumulated: List[Dict[str, Any]] = []

        for hop_idx in range(self.max_hops):
            hop_chunks = self._search_once(
                current_query,
                top_k=top_k,
                use_parent_context=use_parent_context,
            )
            accumulated = _append_deduplicated(accumulated, hop_chunks)

            prompt = build_reflection_user_prompt(
                original_query,
                accumulated,
                current_query=current_query,
            )
            try:
                reflection = self._reflect(prompt)
            except Exception as exc:  # noqa: BLE001 - graceful degradation
                logger.warning(
                    "IterativeRetriever: reflection failed at hop %d/%d; "
                    "using accumulated context: %s",
                    hop_idx + 1,
                    self.max_hops,
                    exc,
                )
                break

            sufficient = bool(reflection["sufficient"])
            confidence = float(reflection["confidence"])
            follow_up = str(reflection.get("follow_up") or "").strip()
            logger.info(
                "IterativeRetriever.search: hop=%d/%d sufficient=%s "
                "confidence=%.3f accumulated=%d follow_up=%s",
                hop_idx + 1,
                self.max_hops,
                sufficient,
                confidence,
                len(accumulated),
                bool(follow_up),
            )

            if sufficient and confidence >= self.min_confidence_to_stop:
                break
            if hop_idx + 1 >= self.max_hops:
                break
            if not follow_up or follow_up in seen_queries:
                break

            seen_queries.add(follow_up)
            current_query = follow_up

        return accumulated

    def _search_once(
        self,
        query: str,
        *,
        top_k: Optional[int],
        use_parent_context: Optional[bool],
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if top_k is not None:
            kwargs["top_k"] = top_k
        if use_parent_context is not None:
            kwargs["use_parent_context"] = use_parent_context
        results = self.retriever.search(query, **kwargs)
        return list(results or [])

    def _reflect(self, prompt: str) -> Dict[str, Any]:
        raw = self.reflection_call(prompt)
        if isinstance(raw, Mapping):
            payload = dict(raw)
        else:
            payload = extract_json(str(raw))
        return validate_reflection_payload(payload)


# ---------------------------------------------------------- ChromaDB retriever --
class ChromaRetriever:
    """Thin wrapper over a persistent ChromaDB collection.

    The retriever encodes queries with the same ``sentence-transformers`` model
    that produced the stored embeddings (default: ``BAAI/bge-m3``, 1024 dim).
    Query embeddings are passed to ChromaDB via ``query_embeddings`` rather
    than ``query_texts`` to bypass ChromaDB's built-in 384-dim default model,
    which would otherwise raise ``InvalidArgumentError`` on a 1024-dim
    collection (issue #73).
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        project_root: Optional[Path] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
        client_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.config = config or {}
        self.persist_directory: Path = resolve_vector_store_path(
            self.config, project_root=project_root
        )
        self.collection_name: str = resolve_collection_name(self.config)
        self.model_name: str = resolve_embedding_model_name(self.config)
        self._normalize = bool(self.config.get("normalize_embeddings", True))
        self._embedder = embedder
        self._client_factory = client_factory
        self._client: Any = None
        self._collection: Any = None

    @classmethod
    def from_config(
        cls,
        config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
        *,
        project_root: Optional[Path] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
        client_factory: Optional[Callable[[str], Any]] = None,
    ) -> "ChromaRetriever":
        return cls(
            config=load_embedding_config(config_path),
            project_root=project_root,
            embedder=embedder,
            client_factory=client_factory,
        )

    # ----------------------------------------------------------- internals --
    def _load_embedder(self) -> Callable[[str], Sequence[float]]:
        if self._embedder is not None:
            return self._embedder
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise RuntimeError(_STRICT_EMBEDDER_ERROR) from exc
        try:
            model = SentenceTransformer(self.model_name)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(_STRICT_EMBEDDER_ERROR) from exc

        normalize = self._normalize

        def _embed(text: str) -> List[float]:
            vector = model.encode(
                text,
                normalize_embeddings=normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return [float(x) for x in vector.tolist()]

        self._embedder = _embed
        return _embed

    def _ensure_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        if self._client_factory is not None:
            self._client = self._client_factory(str(self.persist_directory))
        else:
            try:
                import chromadb  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "chromadb is not installed. Run `pip install -r requirements.txt`."
                ) from exc
            self._client = chromadb.PersistentClient(path=str(self.persist_directory))
        self._collection = self._client.get_or_create_collection(name=self.collection_name)
        return self._collection

    # -------------------------------------------------------------- search --
    def embed_query(self, query: str) -> List[float]:
        """Encode ``query`` with the configured sentence-transformers model."""
        embedder = self._load_embedder()
        vector = embedder(query)
        return [float(v) for v in vector]

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
        """Run a vector search against the configured ChromaDB collection.

        Returns chunk dicts shaped as::

            {"text", "source", "chunk_idx", "distance", "similarity", "metadata"}

        Higher ``similarity`` is better — ChromaDB's L2 distance is mapped to
        a monotonic similarity score (``1 / (1 + distance)``).
        """
        if not query or not query.strip():
            return []
        collection = self._ensure_collection()
        embedding = self.embed_query(query)
        raw = collection.query(
            query_embeddings=[embedding],
            n_results=max(1, int(top_k)),
            include=["documents", "metadatas", "distances"],
        )
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        chunks: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            meta = dict(meta or {})
            distance = float(dist) if dist is not None else None
            similarity = 1.0 / (1.0 + distance) if distance is not None else None
            chunks.append(
                {
                    "text": doc or "",
                    "source": str(meta.get("source", "unknown")),
                    "chunk_idx": meta.get("chunk_idx"),
                    "distance": distance,
                    "similarity": similarity,
                    "metadata": meta,
                }
            )
        return chunks


# --------------------------------------------------------- Hybrid Chroma retriever
class HybridChromaRetriever:
    """Hybrid BM25 + dense retriever backed by a persistent ChromaDB collection.

    Bridges :class:`HybridRetriever` (BM25 + RRF) with :class:`ChromaRetriever`
    (production-grade dense vector store) so the Streamlit UI runs the full
    BL-01 path — BM25 lexical recall + bge-m3 dense recall + RRF fusion (k=60).

    On the first search, the entire ChromaDB corpus is loaded into memory and a
    BM25 index is built. Dense ranking re-uses the persisted embeddings via
    ``ChromaRetriever.search`` (no re-encoding of indexed documents). Result
    shape matches :class:`ChromaRetriever.search` so existing UI code keeps
    working: ``{text, source, chunk_idx, distance, similarity, metadata,
    score}`` where ``score`` is the fused RRF score.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        project_root: Optional[Path] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
        client_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.config = config or {}
        self.use_parent_context = bool(self.config.get("use_parent_context", False))
        self.parent_context_max_chars = int(
            self.config.get("parent_context_max_chars", DEFAULT_PARENT_CONTEXT_MAX_CHARS)
            or DEFAULT_PARENT_CONTEXT_MAX_CHARS
        )
        self._dense = ChromaRetriever(
            config=self.config,
            project_root=project_root,
            embedder=embedder,
            client_factory=client_factory,
        )
        self._bm25: Optional[_BM25] = None
        self._corpus_meta: List[Dict[str, Any]] = []
        self._corpus_loaded = False

    @classmethod
    def from_config(
        cls,
        config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
        *,
        project_root: Optional[Path] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
        client_factory: Optional[Callable[[str], Any]] = None,
    ) -> "HybridChromaRetriever":
        return cls(
            config=load_embedding_config(config_path),
            project_root=project_root,
            embedder=embedder,
            client_factory=client_factory,
        )

    # Public attributes proxied so the UI sidebar keeps working unchanged.
    @property
    def persist_directory(self) -> Path:
        return self._dense.persist_directory

    @property
    def collection_name(self) -> str:
        return self._dense.collection_name

    @property
    def model_name(self) -> str:
        return self._dense.model_name

    @property
    def top_k(self) -> int:
        return int(self.config.get("top_k", DEFAULT_TOP_K) or DEFAULT_TOP_K)

    @property
    def rrf_k(self) -> int:
        return int(self.config.get("rrf_k", DEFAULT_RRF_K) or DEFAULT_RRF_K)

    # ---------------------------------------------------------- BM25 corpus --
    def _load_corpus(self) -> None:
        """Pull all documents from the Chroma collection and build BM25 once."""
        if self._corpus_loaded:
            return
        collection = self._dense._ensure_collection()
        try:
            raw = collection.get(include=["documents", "metadatas"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("HybridChromaRetriever: collection.get failed: %s", exc)
            self._corpus_loaded = True
            return

        ids = raw.get("ids") or []
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []
        tokenized: List[List[str]] = []
        for chunk_id, doc, meta in zip(ids, documents, metadatas):
            meta = dict(meta or {})
            text = doc or ""
            tokenized.append(_tokenize(text))
            self._corpus_meta.append(
                {
                    "id": str(chunk_id),
                    "text": text,
                    "source": str(meta.get("source", "unknown")),
                    "chunk_idx": meta.get("chunk_idx"),
                    "metadata": meta,
                }
            )
        self._bm25 = _BM25(tokenized) if tokenized else None
        self._corpus_loaded = True
        logger.info(
            "HybridChromaRetriever: BM25 built over %d chunks (collection=%s)",
            len(tokenized),
            self.collection_name,
        )

    def _bm25_results(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self._bm25 is None or not self._corpus_meta:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        ranked: List[Dict[str, Any]] = []
        for idx in order:
            if scores[idx] <= 0.0:
                continue
            meta = self._corpus_meta[idx]
            ranked.append(
                {
                    "id": meta["id"],
                    "text": meta["text"],
                    "source": meta["source"],
                    "chunk_idx": meta["chunk_idx"],
                    "metadata": meta["metadata"],
                    "score": float(scores[idx]),
                    "page": _page_from_metadata(meta["metadata"]),
                }
            )
            if len(ranked) >= top_k:
                break
        return ranked

    # -------------------------------------------------------------- search --
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_parent_context: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Run hybrid BM25 + dense retrieval with RRF fusion.

        ``top_k`` controls the number of fused results. Each branch is sampled
        with ``2 × top_k`` candidates so RRF has enough material to reorder.
        """
        if not query or not query.strip():
            return []
        effective_top_k = int(top_k) if top_k is not None else self.top_k
        candidate_k = max(effective_top_k * 2, effective_top_k)

        self._load_corpus()

        dense_chunks = self._dense.search(query, top_k=candidate_k)
        bm25_chunks = self._bm25_results(query, top_k=candidate_k)

        for chunk in dense_chunks:
            sim = chunk.get("similarity")
            chunk["score"] = float(sim) if isinstance(sim, (int, float)) else 0.0
            meta = chunk.get("metadata") or {}
            chunk_idx = chunk.get("chunk_idx")
            source = chunk.get("source", "unknown")
            if "id" not in chunk:
                chunk["id"] = f"{source}__{chunk_idx}" if chunk_idx is not None else source
            chunk["page"] = chunk.get("page") or _page_from_metadata(meta)

        fused = reciprocal_rank_fusion(
            bm25_results=bm25_chunks,
            dense_results=dense_chunks,
            k=self.rrf_k,
            top_k=effective_top_k,
        )

        logger.info(
            "HybridChromaRetriever.search: bm25_hits=%d dense_hits=%d fused=%d "
            "rrf_k=%d top_k=%d collection=%s",
            len(bm25_chunks),
            len(dense_chunks),
            len(fused),
            self.rrf_k,
            effective_top_k,
            self.collection_name,
        )

        dense_by_key = {(c.get("source"), c.get("chunk_idx")): c for c in dense_chunks}
        results: List[Dict[str, Any]] = []
        for item in fused:
            meta = item.get("metadata") or {}
            source = item.get("source", "unknown")
            chunk_idx = meta.get("chunk_idx")
            dense_match = dense_by_key.get((source, chunk_idx))
            results.append(
                {
                    "text": item.get("text", ""),
                    "source": source,
                    "chunk_idx": chunk_idx,
                    "distance": dense_match.get("distance") if dense_match else None,
                    "similarity": dense_match.get("similarity") if dense_match else None,
                    "score": item["score"],
                    "metadata": meta,
                    "page": item.get("page", ""),
                }
            )
        parent_context_enabled = (
            bool(use_parent_context)
            if use_parent_context is not None
            else self.use_parent_context
        )
        if parent_context_enabled:
            return expand_parent_context(results, max_chars=self.parent_context_max_chars)
        return results

    def embed_query(self, query: str) -> List[float]:
        """Encode ``query`` via the underlying ChromaRetriever embedder."""
        return self._dense.embed_query(query)
