# Track 2 Cache Validation Backlog — v2.0

> Isolated backlog contract for cache validation and engineering. This document
> does not activate GitHub implementation issues and does not change the
> MVP/Pilot critical path.

## Metadata

- **Date:** 2026-05-19
- **Version:** v2.0
- **Status:** 🟡 DEFERRED
- **Owner:** Product Owner / Tech Lead
- **Review owner:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Scope:** Track 2 only — cache validation and engineering
- **Linked issue:** [#158](https://github.com/G-Ivan-A/clarify-engine-ai/issues/158)
- **Linked backlog:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.3.md`](2026-05-17_backlog_rag-optimization_v1.3.md)
- **Linked ADR:** [`docs/ADR/007-canonical-cache-draft.md`](../ADR/007-canonical-cache-draft.md) — Draft, Verdict: Pivot
- **Linked concept:** [`docs/CONCEPT.md`](../CONCEPT.md) §5 NFR-07, §6.6 configuration and freshness direction

## 1. Purpose

Track 2 formalizes the cache hypothesis after BL-30 and keeps all cache
optimization work outside the MVP/Pilot delivery path until explicit activation.

The track answers one question: can a canonical query cache reduce latency and
LLM cost without lowering answer precision, freshness, or auditability?

This document is the contract for validating that question. It is not a request
to wire cache behavior into `src/`, change configuration, or create active
implementation issues.

## 2. Activation Gates

| Gate | Status | Required evidence | Transition condition |
|------|--------|-------------------|----------------------|
| **Gate 0 — Stability baseline** | Required before Track 2 starts | At least 5 stable MVP/Pilot validation sessions with no cache dependency, stable retrieval behavior, and no open P0 regression blocking deployment | PO confirms Track 2 may start; tasks `T2-BL-*` can be created as GitHub issues |
| **Gate 1 — Real corpus validation** | Locked until Gate 0 | `cache_validation_corpus.json` with at least 200 PII-free historical queries, each carrying `intent_id`; ADR-007 updated with real-corpus `hit_rate`, `precision`, and `accuracy` metrics | `hit_rate >= 30%`, `hit_precision >= 95%`, `accuracy_impact <= 5%` on real traffic |
| **Gate 2 — Engineering readiness** | Locked until Gate 1 | Cache telemetry exists in an isolated PoC path; p95 lookup latency is measured; freshness checks against `source_registry.csv` are specified | Lookup p95 `< 50ms` at 1000 entries and all cache-hit logs include threshold, hit/miss, and freshness result |
| **Gate 3 — Pilot activation decision** | Locked until Gate 2 | Human-in-the-Loop review report, TTL behavior, invalidation behavior, and reviewer override rate are available for PO review | PO explicitly approves limited pilot activation or rejects production cache integration |

Gate transitions must be recorded in ADR-007 before any downstream task changes
status from `DEFERRED`.

## 3. Backlog Phases

| ID | Task | Phase | Dependencies | Priority | DoD |
|----|------|-------|--------------|----------|-----|
| `T2-BL-33` | Collect and anonymize historical queries | Phase 1 — Validation corpus | Gate 0 ✅ | P1 | `cache_validation_corpus.json` contains `>= 200` PII-free records with `intent_id` |
| `T2-BL-30r` | Re-run cache PoC on real corpus | Phase 1 — Validation corpus | `T2-BL-33` ✅ | P1 | Metrics `hit_rate`, `precision`, and `accuracy` are recorded in ADR-007 |
| `T2-BL-34` | Cache telemetry instrumentation | Phase 2 — Engineering proof | Gate 1 ✅ | P2 | Log fields `cache_hit/miss`, `latency_saved`, and `threshold_used` are added in the isolated cache path |
| `T2-BL-35` | Vector index for cache lookup (FAISS/Chroma) | Phase 2 — Engineering proof | `T2-BL-34` ✅ | P2 | Lookup is `< 50ms` at 1000 records; integration stays in `scripts/poc/` |
| `T2-BL-36` | Invalidation through `source_registry.csv` | Phase 3 — Safety controls | `T2-BL-35` ✅ | P2 | Cache hit validates source `sha256` / `version`; namespace includes `prompt_hash` |
| `T2-BL-37` | TTL and conservative aging (24h) | Phase 3 — Safety controls | `T2-BL-36` ✅ | P2 | Cache records include `expires_at`; expired records are cleaned on startup |
| `T2-BL-38` | Human-in-the-Loop validation of cached answers | Phase 3 — Safety controls | `T2-BL-37` ✅ | P1 | Metrics include `reviewer_override`; review report is appended to ADR-007 |

## 4. Isolation Rules

- Track 2 is **DEFERRED** until Gate 0 is passed and PO explicitly approves
  activation.
- Track 2 must not block MVP/Pilot deployment, Pilot validation, or P0/P1
  backlog work.
- Track 2 tasks use the `T2-` prefix and must not consume the main `BL-*`
  sequence.
- Track 2 changes must remain isolated to validation artifacts, ADR updates, or
  `scripts/poc/` until Gate 3 approval.
- No production cache integration is allowed in `src/`, `configs/`, or the UI
  from this backlog alone.
- Cache activation requires a separate PO-approved issue or ADR decision after
  Gate 3.

## 5. Metrics Contract

| Metric | Minimum threshold | Source |
|--------|-------------------|--------|
| Real-corpus hit rate | `>= 30%` | ADR-007 decision criteria |
| Cache hit precision | `>= 95%` | ADR-007 decision criteria |
| Accuracy impact | `<= 5%` | ADR-007 decision criteria |
| Cache lookup latency | p95 `< 50ms` at 1000 records | `T2-BL-35` |
| Freshness window | `<= 24h` | `T2-BL-37`, NFR-07 direction |
| Reviewer override rate | Reported, no hard gate before pilot | `T2-BL-38` |

## 6. Traceability

| Source | Track 2 dependency |
|--------|--------------------|
| [`docs/ADR/007-canonical-cache-draft.md`](../ADR/007-canonical-cache-draft.md) | Pivot verdict, candidate threshold `0.95`, metrics thresholds, freshness strategy |
| [`docs/CONCEPT.md`](../CONCEPT.md) §5 NFR-07 | Knowledge-base freshness and 24h freshness direction |
| [`docs/CONCEPT.md`](../CONCEPT.md) §6.6 | Configuration and source-registry driven freshness controls |
| [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.3.md`](2026-05-17_backlog_rag-optimization_v1.3.md) | Main MVP/Pilot backlog; Track 2 remains a deferred artifact linked from §14 |

## 7. Definition of Done

- This document exists at
  `docs/backlog/2026-05-19_track2-cache-validation_v2.md`.
- Status is explicitly `🟡 DEFERRED`.
- Gates 0→1→2→3 have concrete metrics and transition conditions.
- Tasks `T2-BL-33` through `T2-BL-38` are defined with dependencies and DoD.
- Isolation rules explicitly prevent MVP/Pilot blocking and production cache
  activation from this document alone.
- ADR-007, CONCEPT, and the main backlog v1.3 are linked.

## 8. Change History

| Version | Date | Change |
|---------|------|--------|
| v2.0 | 2026-05-19 | Created isolated deferred Track 2 backlog contract for cache validation and engineering. |
