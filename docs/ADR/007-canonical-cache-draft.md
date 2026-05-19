# ADR-007: Canonical Query Cache & Clustering

## Status

Draft. Verdict: **Pivot**.

Numbering note: this filename follows issue #151 exactly. The repository
already contains `docs/ADR/007-error-handling.md`, so this draft should be
renumbered before it is promoted beyond Draft.

## Context

BL-30 validates the hypothesis that repeated or near-repeated RAG questions can
skip `retrieval -> context concat -> LLM generation` when the incoming query is
semantically close to a previously verified canonical `query -> answer` pair.

The target architecture in the backlog assumes:

- query embeddings aligned with the approved `BAAI/bge-m3` standard;
- strict cosine threshold around `0.95`;
- cache entries that preserve answer text, citations/source refs, and freshness
  metadata;
- invalidation when KB source hashes or versions change.

This ADR is intentionally a draft because issue #151 covers only the isolated
PoC. Production cache integration remains out of scope.

## PoC Scope

Implemented artifact:

```bash
python scripts/poc/semantic_cache_poc.py \
  --golden test_data/rag_golden_set.json \
  --output reports/semantic_cache_poc_bge_m3.json \
  --thresholds 0.90 0.95 0.97 \
  --embedding-backend bge-m3 \
  --min-records 50
```

The script is standalone and does not modify `src/`, `configs/`, or `ui/`.
Default mode uses deterministic normalized hashing so CI and fresh local clones
do not need to download a model. The measured research run below used
`--embedding-backend bge-m3` with `BAAI/bge-m3` via `sentence-transformers`.

The shipped BL-05 Golden Set contains 32 items. To satisfy the Pilot sample-size
constraint of at least 50 records, the PoC keeps the 32 original questions as
seed cache entries and generates deterministic replay variants with the same
intent key, for 96 total replay records.

## Metrics

Run date: 2026-05-19 UTC.

Embedding backend: `BAAI/bge-m3`.

Assumptions:

- seed records: 32 canonical Golden Set questions;
- evaluated records: 64 replay variants;
- full pipeline latency estimate: 1200 ms;
- cache-hit latency estimate: 35 ms;
- context token overhead estimate: 1200 tokens;
- online fill enabled on cache misses.

| Threshold | Hit Rate | Hit Precision | Accuracy Impact | Latency Savings | Token Savings |
|-----------|----------|---------------|-----------------|-----------------|---------------|
| 0.90 | 100.000% | 100% | 0% | 97.0833% | 79,210 |
| 0.95 | 100.000% | 100% | 0% | 97.0833% | 79,210 |
| 0.97 | 95.3125% | 100% | 0% | 92.5326% | 75,490 |

At the baseline threshold `0.95`, all 32 canonical clusters received at least
one hit, with largest observed cluster size `3`. No false-positive cache hits
were observed in this replay.

## Decision

Pivot, not production acceptance.

The `0.95` threshold is a viable candidate because it clears the BL-30 target
of `>= 30%` hit rate and keeps measured accuracy impact at `0%` in the PoC.
However, the result is not strong enough to accept a production cache because:

- the replay stream is derived from Golden Set variants, not real historical
  BA/TZ traffic;
- Golden Set intent keys validate query intent, but do not validate answer
  freshness or BA satisfaction.

Next decision point: rerun the same script with `--embedding-backend bge-m3`
and a real historical query dump. Promote the ADR only if `hit_rate >= 30%`,
`hit_precision >= 95%`, and `accuracy_impact <= 5%` on that corpus.

## Candidate Cache Record

```json
{
  "query_embedding": [0.0],
  "original_query": "Как настроить SIP-транк в МАНГО ОФИС?",
  "answer": "Verified answer text",
  "source_refs": ["SIP_trunk-1.23.43.pdf"],
  "timestamp": "2026-05-19T08:58:30+00:00"
}
```

Production records should additionally persist:

- `embedding_model` and model revision;
- prompt version/hash;
- source `version` and `sha256_hash` snapshot from
  `knowledge_base/metadata/source_registry.csv`;
- answer validation status and reviewer metadata when Human-in-the-Loop is
  available.

## Invalidation Strategy

Use `source_registry.csv` as the freshness gate:

1. Resolve every cached `source_ref` against registry fields
   `filename`, `version`, `sha256_hash`, `indexed_date`, and `status`.
2. Treat the cache entry as stale if any referenced source has a different
   hash/version, missing row, or non-active/non-indexed status.
3. Namespace cache entries by `embedding_model`, chunking config hash, and
   prompt hash so reindexing or prompt changes do not reuse old answers.
4. Add a conservative TTL of 24 hours during Pilot even when registry hashes
   match, satisfying the NFR-07 freshness direction.

## Overhead Estimate

The PoC lookup is in-memory `O(N * d)` cosine scan. That is acceptable for a
small research corpus, but production should use FAISS/Chroma or another vector
index once the canonical store grows beyond a few thousand records.

Approximate storage for `BAAI/bge-m3`: one 1024-dim float32 embedding is about
4 KB before metadata and answer text. A 10,000-record canonical store should
remain comfortably below 100 MB excluding verbose answer bodies.

Runtime overhead on a cache miss is one additional query embedding plus vector
lookup before the existing full RAG path. Runtime overhead on a cache hit is the
same embedding/lookup cost and no LLM generation.

## Consequences

- Keep `scripts/poc/semantic_cache_poc.py` as the reproducible BL-30 harness.
- Do not wire a cache into `src/pipeline.py` yet.
- Treat `0.95` as the candidate strict threshold for the next real-data run.
- Add telemetry before any production pilot: cache hit/miss, selected threshold,
  best similarity, source freshness result, latency saved, token estimate, and
  reviewer override rate.
