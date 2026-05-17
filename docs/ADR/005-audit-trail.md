# ADR-005. LLM audit trail with per-request run_id

**Status:** Accepted
**Date:** 2026-05-17
**Owner:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
**Author of draft:** konard (AI issue solver)
**Related:** [CONCEPT.md §7.2](../CONCEPT.md), [ADR-004](004-prompt-management.md), [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.md) BL-23 / BL-04, [issue #103](https://github.com/G-Ivan-A/clarify-engine-ai/issues/103)

---

## Context

The pipeline already has a batch-level `run_id`, but incident analysis needs a
smaller trace key for each LLM request. One pipeline run may classify many
requirements and may retry or fall back across providers, so timestamp-based
matching is not reliable enough.

The audit trail must also satisfy BL-04: prompts, context, provider responses,
and errors are logged only after masking with `configs/masking_rules.yaml`.

## Decision

`LLMClient.classify_requirement()` and `LLMClient.generate_rag_response()`
create a per-request `run_id = uuid.uuid4().hex[:12]` at method entry.
The same value is attached to every provider config in that fallback chain, so
the trace survives provider switching.

The client emits structured `INFO` records:

- `LLM_REQUEST` before a provider call.
- `LLM_RESPONSE` after success or failure.

Both records use `extra=` fields and a parseable key=value message. When the
pipeline JSON formatter is active, those `extra=` fields are serialized as JSON
and then sanitized again before output.

## Log Fields

Required fields:

| Field | Applies to | Meaning |
|-------|------------|---------|
| `event` | both | `LLM_REQUEST` or `LLM_RESPONSE` |
| `run_id` | both | 12-character hex id for the LLM request |
| `request_type` | both | `classification` or `rag` |
| `provider` | both | Provider attempted in the fallback chain |
| `attempt` | both | Retry attempt for that provider |
| `requirement_id` | classification | Source requirement id when available |
| `prompt_version` | both | Prompt version, or `unknown` for runtime prompts |
| `prompt_hash` | both | SHA-256 of the system prompt content |
| `decoding_params` | request | Effective decoding parameters visible to provider |
| `user_prompt` | request | Masked prompt sent to provider |
| `status` | response | `success` or `error` |
| `latency_ms` | response | Provider call duration in milliseconds |
| `response` | response | Masked provider response when available |
| `classification` | classification response | Validated label on success |
| `error` | response | Masked exception text on failure |

Example JSON line:

```json
{
  "timestamp": "2026-05-17T19:55:00",
  "level": "INFO",
  "logger": "src.llm.client",
  "message": "LLM_RESPONSE run_id=\"a1b2c3d4e5f6\" request_type=\"classification\" provider=\"openrouter\" attempt=1 status=\"success\" latency_ms=84.3 classification=\"Да\"",
  "event": "LLM_RESPONSE",
  "run_id": "a1b2c3d4e5f6",
  "request_type": "classification",
  "provider": "openrouter",
  "attempt": 1,
  "status": "success",
  "latency_ms": 84.3,
  "prompt_version": "v1.0",
  "prompt_hash": "e3070fdc8055f7d7653412304647ae541897d8b1b59370eb5c614651f05590f5",
  "classification": "Да"
}
```

Sensitive fragments are replaced before serialization:

```text
LLM_REQUEST run_id="a1b2c3d4e5f6" provider="gigachat" user_prompt="<requirement>[EMAIL] [PHONE]</requirement>"
```

## Parsing Examples

Extract all LLM calls for one request:

```bash
jq -c 'select(.run_id == "a1b2c3d4e5f6" and (.event | startswith("LLM_")))' logs/pipeline.jsonl
```

Show fallback sequence and status:

```bash
jq -r 'select(.event == "LLM_RESPONSE") | [.run_id, .provider, .attempt, .status, .latency_ms] | @tsv' logs/pipeline.jsonl
```

Fallback for plain text logs:

```bash
grep 'LLM_RESPONSE run_id="a1b2c3d4e5f6"' logs/pipeline.log
```

## Rotation and Retention

The repository configures stdout JSON logging only; ELK, Loki, and external
collectors are out of scope for this issue. Deployments that write logs to a
file should use JSON Lines (`*.jsonl`) and rotate by either:

- size: 100 MB per file, keeping 30 files; or
- time: daily rotation, keeping 30 days for Pilot.

For incident investigations, relevant `run_id` slices may be retained for up
to 90 days in a restricted audit location. Raw prompts are never retained
outside the sanitized log stream.

## Consequences

Positive:

- A single LLM request can be reconstructed across retries and provider
  fallback using one 12-hex `run_id`.
- Prompt provenance is tied to `prompt_version` and `prompt_hash`.
- Logger failures are best-effort and do not interrupt classification or RAG
  responses.

Tradeoffs:

- Pipeline-level `run_id` and LLM-level `run_id` are intentionally different
  identifiers. Pipeline logs keep the batch id; LLM audit events carry the
  per-request id required for provider fallback tracing.
- Runtime RAG prompts do not always have a versioned template file available to
  `LLMClient`; in that case `prompt_version="unknown"` and `prompt_hash` is
  still computed from the supplied system prompt content.

## History

- **v1.0 (2026-05-17, konard).** Initial Accepted. Defines `LLM_REQUEST` /
  `LLM_RESPONSE`, per-request 12-hex `run_id`, prompt hash fields, parsing
  examples, and rotation policy.
