"""Query expansion wrapper for consultation-mode RAG retrieval.

The wrapper asks an LLM for semantic rewrites of the original user query,
runs the configured retriever for the original query plus each rewrite, and
fuses the ranked hit lists with Reciprocal Rank Fusion. All LLM and parsing
failures degrade to the original query path so retrieval never depends on
query expansion being available.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.llm.prompt_loader import PromptNotFoundError, load_prompt
from src.rag.retriever import DEFAULT_RRF_K, DEFAULT_TOP_K

logger = logging.getLogger(__name__)

DEFAULT_QUERY_EXPANSION_PROMPT_NAME = "system_rag_query_expansion"
DEFAULT_QUERY_EXPANSION_PROMPT_VERSION = "v1"
DEFAULT_EXPANSION_COUNT = 3
MAX_EXPANSION_COUNT = 4

_SYSTEM_PROMPT_FALLBACK = (
    "You rewrite knowledge-base search queries. Return ONLY a JSON array of "
    "3 short query rewrites that preserve the original intent and vary terms."
)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class QueryExpansionConfig:
    """Runtime settings for query expansion.

    The canonical config shape is::

        rag:
          query_expansion_enabled: false
          expansion_count: 3

    Top-level keys with the same names are accepted for backwards-compatible
    experiments, but new configuration should use the ``rag`` block.
    """

    enabled: bool = False
    expansion_count: int = DEFAULT_EXPANSION_COUNT
    rrf_k: int = DEFAULT_RRF_K
    prompt_name: str = DEFAULT_QUERY_EXPANSION_PROMPT_NAME
    prompt_version: str = DEFAULT_QUERY_EXPANSION_PROMPT_VERSION

    @classmethod
    def from_mapping(
        cls,
        config: Optional[Mapping[str, Any]],
    ) -> "QueryExpansionConfig":
        cfg = config or {}
        rag_cfg = cfg.get("rag") if isinstance(cfg, Mapping) else None
        if not isinstance(rag_cfg, Mapping):
            rag_cfg = {}

        def pick(key: str, default: Any) -> Any:
            if key in rag_cfg:
                return rag_cfg[key]
            return cfg.get(key, default)

        enabled = _as_bool(pick("query_expansion_enabled", False), default=False)
        expansion_count = _as_int(
            pick("expansion_count", DEFAULT_EXPANSION_COUNT),
            DEFAULT_EXPANSION_COUNT,
        )
        expansion_count = max(0, min(MAX_EXPANSION_COUNT, expansion_count))
        rrf_k = _as_int(pick("rrf_k", cfg.get("rrf_k", DEFAULT_RRF_K)), DEFAULT_RRF_K)
        prompt_name = str(
            pick("query_expansion_prompt_name", DEFAULT_QUERY_EXPANSION_PROMPT_NAME)
        )
        prompt_version = str(
            pick(
                "query_expansion_prompt_version",
                DEFAULT_QUERY_EXPANSION_PROMPT_VERSION,
            )
        )
        return cls(
            enabled=enabled,
            expansion_count=expansion_count,
            rrf_k=max(1, rrf_k),
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )


def _normalise_query_key(query: str) -> str:
    return " ".join(query.casefold().split())


def _strip_fenced_json(raw: str) -> str:
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.I)
    return fence.group(1).strip() if fence else text


def _loads_json_payload(raw: str) -> Any:
    if not raw or not raw.strip():
        raise ValueError("Empty query expansion response")
    text = _strip_fenced_json(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    candidates = []
    array_start, array_end = text.find("["), text.rfind("]")
    if array_start != -1 and array_end > array_start:
        candidates.append(text[array_start : array_end + 1])
    object_start, object_end = text.find("{"), text.rfind("}")
    if object_start != -1 and object_end > object_start:
        candidates.append(text[object_start : object_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON array or object in query expansion response")


def parse_expansion_response(
    raw_response: str,
    *,
    original_query: str,
    max_count: int = DEFAULT_EXPANSION_COUNT,
) -> List[str]:
    """Parse and validate an LLM query-expansion response.

    Accepted shapes are a JSON array of strings or an object with one of the
    keys ``queries``, ``expansions`` or ``rewrites``. Dict items with a
    ``query`` value are accepted so providers can return richer structures
    without breaking the parser.
    """
    payload = _loads_json_payload(raw_response)
    if isinstance(payload, dict):
        for key in ("queries", "expansions", "rewrites"):
            value = payload.get(key)
            if isinstance(value, list):
                payload = value
                break
        else:
            raise ValueError("Query expansion JSON object has no query list")
    if not isinstance(payload, list):
        raise ValueError("Query expansion response must be a JSON list")

    max_count = max(0, min(MAX_EXPANSION_COUNT, int(max_count)))
    original_key = _normalise_query_key(original_query)
    seen = {original_key}
    expansions: List[str] = []
    for item in payload:
        if isinstance(item, str):
            candidate = item
        elif isinstance(item, Mapping) and isinstance(item.get("query"), str):
            candidate = str(item["query"])
        else:
            continue
        candidate = " ".join(candidate.strip().split())
        if not candidate:
            continue
        key = _normalise_query_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        expansions.append(candidate)
        if len(expansions) >= max_count:
            break
    return expansions


def _chunk_key(chunk: Mapping[str, Any]) -> str:
    identifier = chunk.get("id")
    if identifier is not None:
        return f"id::{identifier}"

    metadata = (
        chunk.get("metadata") if isinstance(chunk.get("metadata"), Mapping) else {}
    )
    metadata = metadata or {}
    source = chunk.get("source") or metadata.get("source") or ""
    chunk_idx = chunk.get("chunk_idx", metadata.get("chunk_idx"))
    if source and chunk_idx is not None:
        return f"chunk::{source}::{chunk_idx}"

    page = (
        chunk.get("page")
        or metadata.get("page")
        or metadata.get("page_number")
        or ""
    )
    text = chunk.get("text", "")
    return f"content::{source}::{page}::{text}"


def fuse_ranked_results(
    ranked_lists: Sequence[Sequence[Mapping[str, Any]]],
    *,
    rrf_k: int = DEFAULT_RRF_K,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fuse multiple ranked hit lists with RRF and deduplicate chunks."""
    if rrf_k <= 0:
        raise ValueError("RRF k must be positive")

    fused: Dict[str, Dict[str, Any]] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits or [], start=1):
            if not isinstance(hit, Mapping):
                continue
            key = _chunk_key(hit)
            contribution = 1.0 / (rrf_k + rank)
            current = fused.get(key)
            if current is None:
                item = dict(hit)
                item["metadata"] = dict(hit.get("metadata") or {})
                item["score"] = contribution
                fused[key] = item
            else:
                current["score"] = float(current.get("score") or 0.0) + contribution

    ranked = sorted(fused.values(), key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item["score"] = round(float(item.get("score") or 0.0), 6)
    if top_k is not None:
        ranked = ranked[: max(0, int(top_k))]
    return ranked


class QueryExpander:
    """Generate semantic query rewrites with graceful fallback."""

    def __init__(
        self,
        llm_client: Any,
        *,
        config: Optional[Mapping[str, Any]] = None,
        prompts_dir: str | Path = "prompts",
    ) -> None:
        self.llm_client = llm_client
        self.config = QueryExpansionConfig.from_mapping(config)
        self.prompts_dir = Path(prompts_dir)
        self._system_prompt: Optional[str] = None

    def _load_system_prompt(self) -> str:
        if self._system_prompt is not None:
            return self._system_prompt
        try:
            prompt = load_prompt(
                self.config.prompt_name,
                version=self.config.prompt_version,
                prompts_dir=self.prompts_dir,
            )
            self._system_prompt = prompt.content
        except PromptNotFoundError:
            logger.warning(
                "Query expansion prompt %s_%s not found; using minimal fallback.",
                self.config.prompt_name,
                self.config.prompt_version,
            )
            self._system_prompt = _SYSTEM_PROMPT_FALLBACK
        return self._system_prompt

    @staticmethod
    def _build_user_prompt(query: str, count: int) -> str:
        return (
            f"<query>{query.strip()}</query>\n"
            f"Return exactly {count} query rewrites as a JSON array of strings."
        )

    def expand_query(self, query: str) -> List[str]:
        """Return validated rewrites or ``[]`` when expansion cannot run."""
        if (
            not self.config.enabled
            or self.config.expansion_count <= 0
            or not query
            or not query.strip()
        ):
            return []

        started = time.perf_counter()
        try:
            system_prompt = self._load_system_prompt()
            user_prompt = self._build_user_prompt(query, self.config.expansion_count)
            raw_response = self.llm_client.generate_rag_response(
                system_prompt,
                user_prompt,
                mask=True,
            )
            expansions = parse_expansion_response(
                raw_response,
                original_query=query,
                max_count=self.config.expansion_count,
            )
            logger.info(
                "query_expansion generated=%d requested=%d latency_ms=%.3f",
                len(expansions),
                self.config.expansion_count,
                (time.perf_counter() - started) * 1000,
            )
            return expansions
        except Exception as exc:  # noqa: BLE001 - expansion is optional
            logger.warning(
                "query_expansion fallback_to_original error=%s latency_ms=%.3f",
                exc,
                (time.perf_counter() - started) * 1000,
            )
            return []


class QueryExpansionRetriever:
    """Retriever wrapper that expands queries before fusing search hits."""

    def __init__(
        self,
        retriever: Any,
        llm_client: Any,
        *,
        config: Optional[Mapping[str, Any]] = None,
        prompts_dir: str | Path = "prompts",
    ) -> None:
        self.retriever = retriever
        base_config = (
            config if config is not None else getattr(retriever, "config", {})
        )
        self.expander = QueryExpander(
            llm_client,
            config=base_config,
            prompts_dir=prompts_dir,
        )
        self.config = self.expander.config

    def __getattr__(self, name: str) -> Any:
        return getattr(self.retriever, name)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        **search_kwargs: Any,
    ) -> List[Dict[str, Any]]:
        effective_top_k = top_k
        if effective_top_k is None:
            effective_top_k = int(getattr(self.retriever, "top_k", DEFAULT_TOP_K))

        original_results = self.retriever.search(
            query,
            top_k=effective_top_k,
            **search_kwargs,
        )
        expansions = self.expander.expand_query(query)
        if not expansions:
            return list(original_results)

        ranked_lists: List[Sequence[Mapping[str, Any]]] = [original_results]
        for expansion in expansions:
            try:
                ranked_lists.append(
                    self.retriever.search(
                        expansion,
                        top_k=effective_top_k,
                        **search_kwargs,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep original query result
                logger.warning(
                    "query_expansion search_failed expansion=%r error=%s",
                    expansion,
                    exc,
                )

        fused = fuse_ranked_results(
            ranked_lists,
            rrf_k=self.config.rrf_k,
            top_k=effective_top_k,
        )
        logger.info(
            "query_expansion retrieval generated=%d unique_chunks=%d variants=%d",
            len(expansions),
            len(fused),
            1 + len(expansions),
        )
        return fused
