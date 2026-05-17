"""RAG retrieval-quality evaluator (BL-05, issue #87).

Reads a Golden Set (``test_data/rag_golden_set.json``), runs each question
through the project retriever, and reports three metrics:

* **Hit Rate @K** — fraction of questions for which at least one chunk in
  the top-K retrieved set comes from an ``expected_sources`` file.
* **MRR (Mean Reciprocal Rank)** — mean of ``1 / rank_of_first_hit`` across
  questions (zero when no hit was found within K).
* **Context Recall** — fraction of ``expected_substrings`` (case-folded)
  that appear in at least one of the top-K retrieved chunk texts.

The script never calls an LLM — it is a retrieval-only evaluator (the LLM
answer-quality channel is exercised by BL-05.2 in a later sprint). The
report is also passed through ``src.llm.masking.sanitize_log_record``
before it is written to disk so the PII regimes in BL-04 / BL-23 apply
end-to-end.

Usage::

    python scripts/evaluate/evaluate_rag.py \\
        --golden test_data/rag_golden_set.json \\
        --output reports/rag_eval.json \\
        --k 5 [--subset smoke] [--retriever stub]

The ``--retriever stub`` flag is the CI smoke entry point (BL-05.1): it
uses a deterministic substring retriever over the Golden Set so the
smoke job stays well under the 2-minute budget even with no Chroma index
and no embedding model on the runner.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.llm.masking import sanitize_log_record  # noqa: E402

logger = logging.getLogger("evaluate_rag")

DEFAULT_GOLDEN_PATH = REPO_ROOT / "test_data" / "rag_golden_set.json"
DEFAULT_K = 5

RetrieverFn = Callable[[str, int], List[Dict[str, Any]]]


# ---------------------------------------------------------------- data model --
@dataclass
class GoldenItem:
    """One question-grounded entry from the Golden Set."""

    id: str
    question: str
    expected_sources: List[str] = field(default_factory=list)
    expected_substrings: List[str] = field(default_factory=list)
    subset: str = ""

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "GoldenItem":
        return cls(
            id=str(raw.get("id", "")),
            question=str(raw.get("question", "")),
            expected_sources=[str(s) for s in raw.get("expected_sources", []) or []],
            expected_substrings=[str(s) for s in raw.get("expected_substrings", []) or []],
            subset=str(raw.get("subset", "")),
        )


def load_golden_set(path: Path) -> List[GoldenItem]:
    """Read and validate ``test_data/rag_golden_set.json``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    items_raw = data.get("items") or []
    return [GoldenItem.from_dict(item) for item in items_raw]


# ----------------------------------------------------------------- metrics --
def hit_rank(chunks: Sequence[Dict[str, Any]], expected_sources: Iterable[str]) -> int:
    """Return the 1-based rank of the first chunk whose ``source`` matches.

    Returns ``0`` when no chunk matches. Case-insensitive comparison.
    """
    wanted = {str(s).lower() for s in expected_sources}
    if not wanted:
        return 0
    for rank, chunk in enumerate(chunks, start=1):
        source = str(chunk.get("source") or "").lower()
        if source in wanted:
            return rank
    return 0


def context_recall(
    chunks: Sequence[Dict[str, Any]], expected_substrings: Iterable[str]
) -> float:
    """Fraction of expected substrings that appear in the retrieved chunks."""
    needles = [str(s) for s in expected_substrings if str(s).strip()]
    if not needles:
        return 1.0
    haystack = " \n".join((chunk.get("text") or "") for chunk in chunks).lower()
    hits = sum(1 for needle in needles if needle.lower() in haystack)
    return hits / len(needles)


@dataclass
class ItemResult:
    id: str
    question: str
    hit: bool
    rank: int
    reciprocal_rank: float
    context_recall: float
    top_sources: List[str]


def evaluate(
    items: Sequence[GoldenItem],
    retriever_fn: RetrieverFn,
    k: int = DEFAULT_K,
) -> Dict[str, Any]:
    """Run the retriever over ``items`` and aggregate metrics."""
    item_results: List[ItemResult] = []
    hit_count = 0
    rr_sum = 0.0
    cr_sum = 0.0
    for item in items:
        chunks = retriever_fn(item.question, k) or []
        chunks = chunks[:k]
        rank = hit_rank(chunks, item.expected_sources)
        hit = rank > 0
        rr = 1.0 / rank if rank else 0.0
        cr = context_recall(chunks, item.expected_substrings)
        if hit:
            hit_count += 1
        rr_sum += rr
        cr_sum += cr
        item_results.append(
            ItemResult(
                id=item.id,
                question=item.question,
                hit=hit,
                rank=rank,
                reciprocal_rank=rr,
                context_recall=cr,
                top_sources=[str(c.get("source") or "") for c in chunks],
            )
        )

    n = len(item_results) or 1
    return {
        "k": k,
        "total_items": len(item_results),
        "hit_rate": hit_count / n,
        "mrr": rr_sum / n,
        "context_recall": cr_sum / n,
        "items": [vars(result) for result in item_results],
    }


# --------------------------------------------------------------- retrievers --
def build_retriever(name: str, golden_path: Path) -> RetrieverFn:
    """Create a retriever callable selected by ``--retriever``.

    * ``"hybrid"`` (default) — the production HybridChromaRetriever wired into
      the UI by BL-01. Requires a populated ``./chroma_data``.
    * ``"stub"`` — deterministic substring retriever over the Golden Set,
      used by the CI smoke job (BL-05.1) so the workflow runs without ML
      dependencies or a Chroma index.
    """
    if name == "hybrid":
        from src.rag.retriever import HybridChromaRetriever

        retriever = HybridChromaRetriever.from_config(
            config_path=str(REPO_ROOT / "configs" / "embedding_config.yaml"),
            project_root=REPO_ROOT,
        )

        def _run(query: str, k: int) -> List[Dict[str, Any]]:
            return retriever.search(query, top_k=k)

        return _run

    if name == "stub":
        return _build_stub_retriever(golden_path)

    raise ValueError(f"Unknown retriever '{name}'. Use 'hybrid' or 'stub'.")


def _build_stub_retriever(golden_path: Path) -> RetrieverFn:
    """Deterministic offline retriever for the CI smoke job."""
    items = load_golden_set(golden_path)
    corpus: List[Dict[str, Any]] = []
    for item in items:
        for source in item.expected_sources:
            text = " ".join([item.question] + item.expected_substrings)
            corpus.append({"text": text, "source": source})

    def _run(query: str, k: int) -> List[Dict[str, Any]]:
        q_tokens = {t for t in query.lower().split() if t}
        scored: List[tuple] = []
        for chunk in corpus:
            text_tokens = set(chunk["text"].lower().split())
            score = len(q_tokens & text_tokens)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {"text": chunk["text"], "source": chunk["source"], "score": float(score)}
            for score, chunk in scored[:k]
        ]

    return _run


# ------------------------------------------------------------------ logging --
class _JsonFormatter(logging.Formatter):
    """JSON formatter aligned with src.pipeline._JsonFormatter (BL-23)."""

    def format(self, record: logging.LogRecord) -> str:
        entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        run_id = getattr(record, "run_id", None)
        if run_id:
            entry["run_id"] = run_id
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(sanitize_log_record(entry), ensure_ascii=False)


def configure_logging(run_id: str) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_JsonFormatter())

    class _RunIdFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
            if not getattr(record, "run_id", None):
                record.run_id = run_id
            return True

    handler.addFilter(_RunIdFilter())
    root.addHandler(handler)


# --------------------------------------------------------------------- main --
def filter_items(items: Sequence[GoldenItem], subset: Optional[str]) -> List[GoldenItem]:
    if not subset:
        return list(items)
    return [item for item in items if item.subset == subset]


def write_report(report: Dict[str, Any], path: Path) -> None:
    """Write the sanitized report to ``path`` (creating parents as needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_log_record(report)
    path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality (BL-05)")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "reports" / "rag_eval.json")
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--retriever", choices=("hybrid", "stub"), default="hybrid")
    parser.add_argument(
        "--subset",
        type=str,
        default="",
        help="Optional Golden-Set subset filter (e.g. 'smoke' for the BL-05.1 CI job).",
    )
    parser.add_argument("--min-hit-rate", type=float, default=0.0)
    parser.add_argument("--min-mrr", type=float, default=0.0)
    parser.add_argument("--min-context-recall", type=float, default=0.0)
    args = parser.parse_args(argv)

    run_id = str(uuid.uuid4())
    configure_logging(run_id)
    logger.info("RAG evaluation started (run_id=%s, k=%s)", run_id, args.k)

    items = filter_items(load_golden_set(args.golden), args.subset or None)
    if not items:
        logger.error("Golden Set %s yielded zero items (subset=%r).", args.golden, args.subset)
        return 2

    retriever_fn = build_retriever(args.retriever, args.golden)
    report = evaluate(items, retriever_fn, k=args.k)
    report["run_id"] = run_id
    report["retriever"] = args.retriever
    report["subset"] = args.subset or "all"

    write_report(report, args.output)
    logger.info(
        "RAG eval done: hit_rate=%.3f mrr=%.3f context_recall=%.3f (items=%d)",
        report["hit_rate"],
        report["mrr"],
        report["context_recall"],
        report["total_items"],
    )

    if report["hit_rate"] < args.min_hit_rate:
        logger.error(
            "Hit Rate %.3f below threshold %.3f", report["hit_rate"], args.min_hit_rate
        )
        return 1
    if report["mrr"] < args.min_mrr:
        logger.error("MRR %.3f below threshold %.3f", report["mrr"], args.min_mrr)
        return 1
    if report["context_recall"] < args.min_context_recall:
        logger.error(
            "Context Recall %.3f below threshold %.3f",
            report["context_recall"],
            args.min_context_recall,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
