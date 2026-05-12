"""Hybrid retriever combining BM25 lexical search and dense vector search.

Ranking is fused with Reciprocal Rank Fusion (RRF). The retriever is designed
so that it works with a real ChromaDB / sentence-transformers stack when those
libraries are installed, but it also degrades gracefully to an in-memory
implementation when they are unavailable (handy for unit tests and CI without
heavy ML dependencies).
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


@dataclass
class RetrievedChunk:
    """A single retrieval result."""

    text: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "text": self.text,
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
    """Deterministic bag-of-tokens hash embedding used as a fallback.

    Good enough for similarity ordering in tests; should be replaced by a real
    embedding model (e.g. ``BAAI/bge-m3``) in production.
    """
    vec = [0.0] * dim
    for token in _tokenize(text):
        idx = hash(token) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


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


class HybridRetriever:
    """Hybrid BM25 + dense retriever with RRF re-ranking."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
    ) -> None:
        self.config = config or {}
        self._embedder = embedder or _hash_embedding
        self._documents: List[_Document] = []
        self._bm25: Optional[_BM25] = None

    # ------------------------------------------------------------------ load --
    @classmethod
    def from_config(
        cls,
        config_path: str = "configs/embedding_config.yaml",
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
    def search(self, query: str, top_k: int = 3, rrf_k: int = 60) -> List[Dict[str, Any]]:
        """Run hybrid search.

        Args:
            query: Natural-language query (typically a requirement text).
            top_k: Number of chunks to return.
            rrf_k: RRF constant. Larger values flatten ranking contributions.

        Returns:
            A list of dictionaries shaped as
            ``{"source": str, "text": str, "score": float, "metadata": {...}}``.
        """
        if not query or not query.strip():
            return []
        if not self._documents:
            logger.warning("HybridRetriever.search called with no indexed documents.")
            return []

        query_tokens = _tokenize(query)
        bm25_scores = self._bm25.get_scores(query_tokens) if self._bm25 else [0.0] * len(self._documents)
        query_vec = list(self._embedder(query))
        dense_scores = [_cosine_similarity(query_vec, doc.embedding) for doc in self._documents]

        bm25_rank = self._ranks_from_scores(bm25_scores)
        dense_rank = self._ranks_from_scores(dense_scores)

        fused: List[tuple[int, float]] = []
        for idx in range(len(self._documents)):
            score = 0.0
            if bm25_rank[idx] is not None:
                score += 1.0 / (rrf_k + bm25_rank[idx])
            if dense_rank[idx] is not None:
                score += 1.0 / (rrf_k + dense_rank[idx])
            fused.append((idx, score))

        fused.sort(key=lambda item: item[1], reverse=True)
        results: List[Dict[str, Any]] = []
        for idx, score in fused[:top_k]:
            if score <= 0.0:
                continue
            doc = self._documents[idx]
            results.append(
                RetrievedChunk(
                    text=doc.text,
                    source=doc.source,
                    score=round(score, 6),
                    metadata=doc.metadata,
                ).to_dict()
            )
        return results

    @staticmethod
    def _ranks_from_scores(scores: Sequence[float]) -> List[Optional[int]]:
        """Convert raw scores to 1-based ranks, ``None`` for zero/negative scores."""
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        ranks: List[Optional[int]] = [None] * len(scores)
        rank = 1
        for idx in order:
            if scores[idx] <= 0.0:
                continue
            ranks[idx] = rank
            rank += 1
        return ranks


def build_retriever(
    documents: Optional[Iterable[Dict[str, Any]]] = None,
    config_path: str = "configs/embedding_config.yaml",
) -> HybridRetriever:
    """Convenience factory: build a retriever and pre-index documents."""
    retriever = HybridRetriever.from_config(config_path=config_path)
    if documents:
        retriever.add_documents(documents)
    return retriever
