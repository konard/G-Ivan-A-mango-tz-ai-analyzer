# ADR-009: Parent Document Retrieval

## Status

Accepted (2026-05-17; reaffirmed 2026-05-19 by BL-40 ADR-sync — see §History v1.1)

## Context

L1 chunks improve retrieval precision, but a single 512-token child chunk can
omit important neighbouring instructions. Consultation mode needs more coherent
context without changing the default analysis retrieval contract.

## Decision

The indexer persists parent metadata on every child chunk:

- `parent_id` / `section_id`: stable source + section identifier.
- `parent_text`: concatenated text for all chunks in the same parent section.

`HybridRetriever` and `HybridChromaRetriever` keep `use_parent_context: false`
as the default in [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml).
When the flag is enabled, retrieval still ranks L1 child chunks with
BM25 + dense + RRF, then collapses hits by `parent_id` and returns bounded
parent section text. The companion key
`parent_context_max_chars: 6000` (default in
[`configs/embedding_config.yaml`](../../configs/embedding_config.yaml)) limits
each returned parent context so the LLM prompt cannot grow without bound; the
value is intentionally tied to the consultation history cap from
[ADR-004B (UI Operation Modes)](004-ui-operation-modes.md) (`ui.max_history_messages: 6`).

## Mode Contract (BL-40)

The flag is **mode-scoped**:

| UI mode | `use_parent_context` at call site | Notes |
|---------|-----------------------------------|-------|
| 📊 Анализ ТЗ (stateless) | `False` | Token-budget protected (NFR-06 / ADR-004B). Analysis must always receive raw L1 child chunks. |
| 💬 Консультация (stateful) | `True` (passed by `src/ui/app.py`) | Parent sections improve coherence; per-call output is capped by `parent_context_max_chars`. |

The configured default (`False`) is the **fallback for non-UI callers** and
for any future batch consumer. The Streamlit consultation mode is the only
production caller that opts in; the analysis path explicitly does **not** pass
`use_parent_context=True`. Switching the global default to `True` is **out of
scope** for the Pilot and would require a new ADR.

## Consequences

This design keeps the Chroma collection layout simple and backward-compatible:
older indexes without `parent_text` still work, falling back to the child chunk
text. A full reindex is required to get complete L2 parent sections.

## References

- [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) —
  `use_parent_context: false` (default), `parent_context_max_chars: 6000`.
- [`src/retrieval/hybrid.py`](../../src/retrieval/hybrid.py),
  [`src/retrieval/hybrid_chroma.py`](../../src/retrieval/hybrid_chroma.py) —
  `HybridRetriever`, `HybridChromaRetriever`.
- [`src/ui/app.py`](../../src/ui/app.py) — Consultation-mode caller that opts
  into `use_parent_context=True`.
- [ADR-001 (RAG Architecture)](001-rag-architecture.md),
  [ADR-004B (UI Operation Modes)](004-ui-operation-modes.md).
- [BL-34 audit §CHK-06 «Parent Document Retrieval»](../audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md).
- Issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166) (BL-40 ADR-sync).

## History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-17 | First Accepted version: parent metadata on L1 chunks (`parent_id`, `section_id`, `parent_text`), `use_parent_context` flag and `parent_context_max_chars` cap, Consultation-mode opt-in. |
| 1.1 | 2026-05-19 | BL-40 (issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)): ADR-sync with CONCEPT.md v2.5 and BL-34 audit §CHK-06. Added explicit **Mode Contract** table tying `use_parent_context=True` to Консультация only and reaffirming `use_parent_context: false` as the global default in [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml). Pinned the `parent_context_max_chars: 6000` default in §Decision. Code and config defaults unchanged. |
