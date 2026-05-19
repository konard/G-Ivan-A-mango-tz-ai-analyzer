"""BL-30 canonical query cache PoC.

The script replays Golden Set questions as a small historical query stream,
pre-warms an in-memory semantic cache with canonical records, then sweeps one
or more cosine thresholds to estimate cache hit rate, latency savings, token
savings, and intent-accuracy impact.

Default execution is deterministic and stdlib-only so it can run in CI and on
fresh local clones:

    python scripts/poc/semantic_cache_poc.py \
        --golden test_data/rag_golden_set.json \
        --output reports/semantic_cache_poc.json

For a real embedding run, install the project requirements and use:

    python scripts/poc/semantic_cache_poc.py --embedding-backend bge-m3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLDEN_PATH = REPO_ROOT / "test_data" / "rag_golden_set.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "reports" / "semantic_cache_poc.json"
DEFAULT_THRESHOLDS = (0.90, 0.95, 0.97)
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_MIN_RECORDS = 50
DEFAULT_AUGMENT_PER_ITEM = 2
DEFAULT_FULL_PIPELINE_LATENCY_MS = 1200.0
DEFAULT_CACHE_HIT_LATENCY_MS = 35.0
DEFAULT_CONTEXT_TOKEN_OVERHEAD = 1200

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", flags=re.IGNORECASE)
LEADING_NOISE_PATTERNS = (
    r"^\s*подскажите[:,\s-]*",
    r"^\s*скажите[:,\s-]*",
    r"^\s*пожалуйста[:,\s-]*",
    r"^\s*инструкция[:,\s-]*",
    r"^\s*нужна\s+инструкция[:,\s-]*",
    r"^\s*нужны\s+шаги[:,\s-]*",
)
TRAILING_NOISE_PATTERNS = (
    r"[\s.?!,;:-]*нужны\s+краткие\s+шаги[\s.?!,;:-]*$",
    r"[\s.?!,;:-]*нужна\s+краткая\s+инструкция[\s.?!,;:-]*$",
    r"[\s.?!,;:-]*подробная\s+инструкция[\s.?!,;:-]*$",
)


@dataclass(frozen=True)
class GoldenItem:
    """One Golden Set question with enough data to create a cache record."""

    id: str
    question: str
    source_refs: List[str]
    expected_substrings: List[str]
    answer: str
    intent_key: str

    @classmethod
    def from_dict(cls, raw: Dict[str, Any], fallback_id: str) -> "GoldenItem":
        item_id = str(raw.get("id") or fallback_id)
        source_refs = _coerce_string_list(
            raw.get("source_refs") or raw.get("expected_sources") or []
        )
        expected_substrings = _coerce_string_list(raw.get("expected_substrings") or [])
        answer = str(raw.get("answer") or _stub_answer(source_refs, expected_substrings))
        return cls(
            id=item_id,
            question=str(raw.get("question") or raw.get("query") or ""),
            source_refs=source_refs,
            expected_substrings=expected_substrings,
            answer=answer,
            intent_key=str(raw.get("intent_key") or item_id),
        )


@dataclass(frozen=True)
class QueryRecord:
    """One historical query event used by the cache simulation."""

    id: str
    query: str
    answer: str
    source_refs: List[str]
    intent_key: str


@dataclass
class CacheEntry:
    """In-memory approximation of the proposed canonical cache record."""

    id: str
    query_embedding: List[float]
    original_query: str
    answer: str
    source_refs: List[str]
    timestamp: str
    intent_key: str
    cluster_size: int = 1


class HashingEmbedder:
    """Deterministic normalized hashing embedder for offline smoke runs.

    It is not a replacement for ``BAAI/bge-m3``. It exists so the PoC can be
    tested without downloading a large model; the report records the backend
    explicitly to keep metrics honest.
    """

    name = "hashing"

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_many(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        for feature, weight in _features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class BgeM3Embedder:
    """Optional real embedding backend aligned with ``embedding-model.md``."""

    name = "bge-m3"

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError(
                "sentence-transformers is required for --embedding-backend bge-m3"
            ) from exc
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_many(self, texts: Sequence[str]) -> List[List[float]]:  # pragma: no cover
        encoded = self.model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, row)) for row in encoded]


def _coerce_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    return [str(value)]


def _stub_answer(source_refs: Sequence[str], expected_substrings: Sequence[str]) -> str:
    refs = ", ".join(source_refs) if source_refs else "unknown source"
    markers = ", ".join(expected_substrings[:3]) if expected_substrings else "no markers"
    return f"Stub answer grounded in {refs}; expected markers: {markers}."


def load_golden_set(path: Path) -> List[GoldenItem]:
    """Load JSON/JSONL Golden Set items in the BL-05 evaluator shape."""
    if not path.exists():
        raise FileNotFoundError(f"Golden Set not found: {path}")
    if path.suffix.lower() == ".jsonl":
        items: List[GoldenItem] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            items.append(GoldenItem.from_dict(raw, fallback_id=f"JSONL-{line_no:03d}"))
        return _validate_items(items, path)

    raw_data = json.loads(path.read_text(encoding="utf-8"))
    raw_items = raw_data.get("items") if isinstance(raw_data, dict) else raw_data
    items = [
        GoldenItem.from_dict(raw, fallback_id=f"JSON-{index:03d}")
        for index, raw in enumerate(raw_items or [], start=1)
    ]
    return _validate_items(items, path)


def _validate_items(items: List[GoldenItem], path: Path) -> List[GoldenItem]:
    valid = [item for item in items if item.question.strip()]
    if not valid:
        raise ValueError(f"Golden Set {path} yielded zero query items")
    return valid


def prepare_replay_records(
    items: Sequence[GoldenItem],
    min_records: int = DEFAULT_MIN_RECORDS,
    augment_per_item: int = DEFAULT_AUGMENT_PER_ITEM,
) -> List[QueryRecord]:
    """Create a deterministic replay stream from Golden Set questions.

    The shipped BL-05 Golden Set has fewer than 50 questions, while Pilot exit
    criteria refer to a sample of at least 50. This PoC therefore keeps every
    original question as a canonical seed and adds lightweight replay variants
    that preserve the original intent key. Reports label this as an augmented
    Golden Set replay, not production traffic.
    """
    if min_records <= 0:
        raise ValueError("min_records must be positive")
    if augment_per_item < 0:
        raise ValueError("augment_per_item cannot be negative")

    records = [_record_from_item(item, "canonical", item.question) for item in items]
    target_records = max(min_records, len(items) * (1 + augment_per_item))
    if len(records) >= target_records:
        return records

    variant_builders = (
        _without_terminal_punctuation,
        _with_polite_prefix,
        _with_instruction_suffix,
        _with_instruction_prefix,
    )
    round_index = 0
    while len(records) < target_records:
        builder = variant_builders[round_index % len(variant_builders)]
        variant_name = f"variant-{round_index + 1}"
        for item in items:
            if len(records) >= target_records:
                break
            records.append(_record_from_item(item, variant_name, builder(item.question)))
        round_index += 1
    return records


def _record_from_item(item: GoldenItem, suffix: str, query: str) -> QueryRecord:
    return QueryRecord(
        id=f"{item.id}::{suffix}",
        query=query,
        answer=item.answer,
        source_refs=list(item.source_refs),
        intent_key=item.intent_key,
    )


def _without_terminal_punctuation(question: str) -> str:
    return question.strip().rstrip("?!.,;:")


def _with_polite_prefix(question: str) -> str:
    stripped = question.strip()
    if not stripped:
        return question
    return f"Нужна помощь: {stripped[:1].lower()}{stripped[1:]}"


def _with_instruction_suffix(question: str) -> str:
    return f"{question.strip()} Нужны краткие шаги."


def _with_instruction_prefix(question: str) -> str:
    return f"Инструкция: {question.strip()}"


def normalize_query(text: str) -> str:
    normalized = text.lower().replace("ё", "е").strip()
    for pattern in LEADING_NOISE_PATTERNS:
        normalized = re.sub(pattern, "", normalized)
    for pattern in TRAILING_NOISE_PATTERNS:
        normalized = re.sub(pattern, "", normalized)
    return " ".join(TOKEN_RE.findall(normalized))


def _features(text: str) -> Iterable[Tuple[str, float]]:
    normalized = normalize_query(text)
    tokens = normalized.split()
    for token in tokens:
        yield f"tok:{token}", 1.0
    joined = " ".join(tokens)
    for start in range(max(0, len(joined) - 2)):
        trigram = joined[start : start + 3]
        if trigram.strip():
            yield f"tri:{trigram}", 0.35


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def simulate_cache(
    records: Sequence[QueryRecord],
    embeddings: Sequence[Sequence[float]],
    threshold: float,
    seed_size: int,
    *,
    online_fill: bool = True,
    full_pipeline_latency_ms: float = DEFAULT_FULL_PIPELINE_LATENCY_MS,
    cache_hit_latency_ms: float = DEFAULT_CACHE_HIT_LATENCY_MS,
    context_token_overhead: int = DEFAULT_CONTEXT_TOKEN_OVERHEAD,
    timestamp: str = "1970-01-01T00:00:00+00:00",
) -> Dict[str, Any]:
    """Replay records through an in-memory canonical cache."""
    if len(records) != len(embeddings):
        raise ValueError("records and embeddings must have the same length")
    if not records:
        raise ValueError("records cannot be empty")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    if seed_size <= 0 or seed_size >= len(records):
        raise ValueError("seed_size must leave at least one record for evaluation")

    cache_entries = [
        _cache_entry(records[index], list(embeddings[index]), timestamp)
        for index in range(seed_size)
    ]

    cache_hits = 0
    cache_misses = 0
    accurate_hits = 0
    false_positive_hits = 0
    token_savings = 0
    safe_token_savings = 0
    best_scores: List[float] = []

    for index in range(seed_size, len(records)):
        record = records[index]
        embedding = embeddings[index]
        best_entry, best_score = _best_cache_match(cache_entries, embedding)
        best_scores.append(best_score)

        if best_entry and best_score >= threshold:
            cache_hits += 1
            best_entry.cluster_size += 1
            saved_tokens = estimate_llm_tokens(record, context_token_overhead)
            token_savings += saved_tokens
            if best_entry.intent_key == record.intent_key:
                accurate_hits += 1
                safe_token_savings += saved_tokens
            else:
                false_positive_hits += 1
            continue

        cache_misses += 1
        if online_fill:
            cache_entries.append(_cache_entry(record, list(embedding), timestamp))

    evaluated_records = len(records) - seed_size
    hit_rate = _ratio(cache_hits, evaluated_records)
    hit_precision = _ratio(accurate_hits, cache_hits, default=1.0)
    accuracy_impact = _ratio(false_positive_hits, evaluated_records)
    latency_baseline = evaluated_records * full_pipeline_latency_ms
    latency_with_cache = (
        cache_hits * cache_hit_latency_ms + cache_misses * full_pipeline_latency_ms
    )
    latency_savings = max(0.0, latency_baseline - latency_with_cache)

    cluster_sizes = [entry.cluster_size for entry in cache_entries]
    return {
        "threshold": _round(threshold),
        "seed_records": seed_size,
        "evaluated_records": evaluated_records,
        "cache_entries_final": len(cache_entries),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "accurate_hits": accurate_hits,
        "false_positive_hits": false_positive_hits,
        "hit_rate": _round(hit_rate),
        "effective_hit_rate": _round(_ratio(accurate_hits, evaluated_records)),
        "hit_precision": _round(hit_precision),
        "accuracy_impact": _round(accuracy_impact),
        "latency_baseline_ms": _round(latency_baseline),
        "latency_with_cache_ms": _round(latency_with_cache),
        "latency_savings_ms": _round(latency_savings),
        "latency_savings_rate": _round(_ratio(latency_savings, latency_baseline)),
        "token_savings_estimated": token_savings,
        "safe_token_savings_estimated": safe_token_savings,
        "clusters_total": len(cache_entries),
        "clusters_with_hits": sum(1 for size in cluster_sizes if size > 1),
        "largest_cluster_size": max(cluster_sizes) if cluster_sizes else 0,
        "mean_best_similarity": _round(sum(best_scores) / len(best_scores))
        if best_scores
        else 0.0,
    }


def _cache_entry(record: QueryRecord, embedding: List[float], timestamp: str) -> CacheEntry:
    return CacheEntry(
        id=record.id,
        query_embedding=embedding,
        original_query=record.query,
        answer=record.answer,
        source_refs=list(record.source_refs),
        timestamp=timestamp,
        intent_key=record.intent_key,
    )


def _best_cache_match(
    cache_entries: Sequence[CacheEntry],
    embedding: Sequence[float],
) -> Tuple[Optional[CacheEntry], float]:
    best_entry: Optional[CacheEntry] = None
    best_score = -1.0
    for entry in cache_entries:
        score = cosine_similarity(entry.query_embedding, embedding)
        if score > best_score:
            best_entry = entry
            best_score = score
    return best_entry, best_score


def estimate_llm_tokens(record: QueryRecord, context_token_overhead: int) -> int:
    return (
        _estimate_tokens(record.query)
        + _estimate_tokens(record.answer)
        + max(0, context_token_overhead)
    )


def _estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _round(value: float) -> float:
    return round(float(value), 6)


def build_embedder(args: argparse.Namespace) -> Any:
    if args.embedding_backend == "hashing":
        return HashingEmbedder(dimensions=args.hash_dim)
    if args.embedding_backend == "bge-m3":
        return BgeM3Embedder(model_name=args.embedding_model)
    raise ValueError(f"Unknown embedding backend: {args.embedding_backend}")


def select_recommended_result(
    results: Sequence[Dict[str, Any]],
    *,
    target_threshold: float = 0.95,
    min_hit_precision: float,
    max_accuracy_impact: float,
) -> Dict[str, Any]:
    eligible = [
        result
        for result in results
        if result["hit_precision"] >= min_hit_precision
        and result["accuracy_impact"] <= max_accuracy_impact
    ]
    for result in eligible:
        if abs(result["threshold"] - target_threshold) < 1e-9:
            return result
    if eligible:
        return max(eligible, key=lambda result: (result["effective_hit_rate"], result["threshold"]))
    return max(results, key=lambda result: (result["hit_precision"], -result["accuracy_impact"]))


def build_report(
    *,
    args: argparse.Namespace,
    items: Sequence[GoldenItem],
    records: Sequence[QueryRecord],
    seed_size: int,
    results: Sequence[Dict[str, Any]],
    generated_at: str,
) -> Dict[str, Any]:
    recommended = select_recommended_result(
        results,
        min_hit_precision=args.min_hit_precision,
        max_accuracy_impact=args.max_accuracy_impact,
    )
    decision_gate = "candidate"
    if (
        recommended["effective_hit_rate"] < args.target_hit_rate
        or recommended["accuracy_impact"] > args.max_accuracy_impact
        or recommended["hit_precision"] < args.min_hit_precision
    ):
        decision_gate = "reject"

    return {
        "run_id": str(uuid.uuid4()),
        "generated_at": generated_at,
        "golden_path": str(args.golden),
        "golden_items": len(items),
        "total_records": len(records),
        "seed_size": seed_size,
        "evaluated_records": len(records) - seed_size,
        "augmentation": {
            "enabled": len(records) > len(items),
            "min_records": args.min_records,
            "augment_per_item": args.augment_per_item,
            "note": "Deterministic replay variants preserve Golden Set intent keys.",
        },
        "embedding_backend": args.embedding_backend,
        "embedding_model": args.embedding_model
        if args.embedding_backend == "bge-m3"
        else "deterministic-normalized-hashing",
        "cache_record_shape": [
            "query_embedding",
            "original_query",
            "answer",
            "source_refs",
            "timestamp",
        ],
        "thresholds": [result["threshold"] for result in results],
        "recommended_threshold": recommended["threshold"],
        "decision_gate": decision_gate,
        "targets": {
            "hit_rate": args.target_hit_rate,
            "max_accuracy_impact": args.max_accuracy_impact,
            "min_hit_precision": args.min_hit_precision,
        },
        "assumptions": {
            "full_pipeline_latency_ms": args.full_latency_ms,
            "cache_hit_latency_ms": args.cache_latency_ms,
            "context_token_overhead": args.context_token_overhead,
            "online_fill": True,
        },
        "results": list(results),
    }


def write_report(report: Dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BL-30 semantic cache PoC")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--embedding-backend",
        choices=("hashing", "bge-m3"),
        default="hashing",
        help="Use deterministic hashing for CI or BAAI/bge-m3 for local research.",
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--hash-dim", type=int, default=256)
    parser.add_argument("--thresholds", nargs="+", type=float, default=list(DEFAULT_THRESHOLDS))
    parser.add_argument("--seed-size", type=int, default=0)
    parser.add_argument("--min-records", type=int, default=DEFAULT_MIN_RECORDS)
    parser.add_argument("--augment-per-item", type=int, default=DEFAULT_AUGMENT_PER_ITEM)
    parser.add_argument("--full-latency-ms", type=float, default=DEFAULT_FULL_PIPELINE_LATENCY_MS)
    parser.add_argument("--cache-latency-ms", type=float, default=DEFAULT_CACHE_HIT_LATENCY_MS)
    parser.add_argument("--context-token-overhead", type=int, default=DEFAULT_CONTEXT_TOKEN_OVERHEAD)
    parser.add_argument("--target-hit-rate", type=float, default=0.30)
    parser.add_argument("--max-accuracy-impact", type=float, default=0.05)
    parser.add_argument("--min-hit-precision", type=float, default=0.95)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        items = load_golden_set(args.golden)
        records = prepare_replay_records(
            items,
            min_records=args.min_records,
            augment_per_item=args.augment_per_item,
        )
        seed_size = args.seed_size or len(items)
        if seed_size >= len(records):
            raise ValueError(
                f"seed-size={seed_size} leaves no evaluation records; "
                "increase --min-records or reduce --seed-size"
            )
        if seed_size <= 0:
            raise ValueError("seed-size must be positive")

        embedder = build_embedder(args)
        embeddings = embedder.embed_many([record.query for record in records])
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        results = [
            simulate_cache(
                records,
                embeddings,
                threshold=threshold,
                seed_size=seed_size,
                full_pipeline_latency_ms=args.full_latency_ms,
                cache_hit_latency_ms=args.cache_latency_ms,
                context_token_overhead=args.context_token_overhead,
                timestamp=generated_at,
            )
            for threshold in args.thresholds
        ]
        report = build_report(
            args=args,
            items=items,
            records=records,
            seed_size=seed_size,
            results=results,
            generated_at=generated_at,
        )
        write_report(report, args.output)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"semantic-cache-poc: {exc}", file=sys.stderr)
        return 2

    selected = report["recommended_threshold"]
    selected_result = next(result for result in report["results"] if result["threshold"] == selected)
    print(
        "semantic-cache-poc: "
        f"records={report['total_records']} seed={report['seed_size']} "
        f"threshold={selected:.2f} hit_rate={selected_result['hit_rate']:.3f} "
        f"hit_precision={selected_result['hit_precision']:.3f} "
        f"accuracy_impact={selected_result['accuracy_impact']:.3f} "
        f"report={args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
