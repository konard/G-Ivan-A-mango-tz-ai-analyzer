# ADR-007: Graceful UI Error Handling and Retry

## Status
Accepted (2026-05-17)

## Context

`src/ui/app.py` is the manual Streamlit UI for knowledge-base RAG checks.
Provider outages, API limits, network timeouts, and retriever failures used to
surface as raw exception text in the page. In Streamlit this is especially
fragile because every interaction reruns the script: without explicit session
state the failed query can be lost, and a retry button cannot safely replay the
same request.

Related documents:
- [`docs/CONCEPT.md`](../CONCEPT.md) §6.4.
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.md) — BL-13.
- Issue [#106](https://github.com/G-Ivan-A/clarify-engine-ai/issues/106).

## Decision

The KB UI owns a small failure-state machine in `st.session_state`:

| Key | Purpose |
|-----|---------|
| `last_query` | Last submitted query. This is the single retry source required by BL-13. |
| `pending_query` | Query queued for generation on the next rerun. |
| `pending_mode` | UI mode that owns the pending query (`stateless` / `consultation`). |
| `pending_run_id` | UUID for the queued generation attempt. |
| `is_processing` | Enables disabled input controls while the queued request runs. |
| `last_error` | Retryable error metadata: mode, user message, run_id, error_type, provider. |
| `last_analysis_result` | Last successful stateless answer so a post-processing rerun does not erase the output. |

Submit and retry both queue a query, set `is_processing=True`, and call
`st.rerun()`. The next run renders the relevant input control disabled
(`st.text_area` in analysis mode, `st.chat_input` in consultation mode), then
executes retrieval and LLM generation under `st.spinner(...)`. After success
or failure, the UI clears the pending state and reruns again so controls return
to their normal enabled state.

Failures from `LLMError`, `RetriableProviderError`, Python/request timeouts,
connection errors, `KBError`, and unexpected retrieval/provider exceptions are
converted into a generic user-facing notification:

> Не удалось получить ответ.

The raw exception, stack trace, prompt, and provider payload are never rendered
in the page. The retry button is a separate Streamlit button labeled
`Повторить`; it reads `st.session_state["last_query"]` and queues that value
without clearing the current input widget.

Successful answers are rendered through the normal answer/chat surfaces. Failed
attempts do not create assistant chat messages and do not populate export rows,
so the UI never invents a fake RAG answer when all providers fail.

## Logging

The UI emits two guarded log events:

- `ui_prompt_built`: `run_id`, `ui_mode`, history message count, approximate token count.
- `ui_generation_failed`: `run_id`, `error_type`, `provider`, `ui_mode`.

Both logging calls are wrapped in `try/except pass`. A broken logging backend
must not break the Streamlit request path. The log payload intentionally omits
raw prompts and query text; `run_id` is the correlation handle.

`LLMError` carries optional `provider` and `last_error` attributes so the UI can
log the last failed provider when the LLM fallback chain is exhausted.

## Notification Types

| Situation | UI notification | Retry |
|-----------|-----------------|-------|
| Retrieval/query generation failure | `st.error("Не удалось получить ответ.")` | `Повторить` button |
| Missing saved query on retry | `st.warning(...)` | Not queued |
| Retriever initialisation failure before a query | `st.error("Не удалось подготовить поиск по базе знаний.")` | No query-specific retry |
| Successful generation | Answer block / chat message | No error block |

## Consequences

### Positive
- Provider and retriever outages no longer leak raw tracebacks or prompts into
  the UI.
- The original query is preserved across reruns and can be retried explicitly.
- Analysis and consultation modes keep their existing answer surfaces while
  errors stay visually separate.
- Logging remains useful for operators but isolated from the user path.

### Negative
- The Streamlit flow now needs two reruns per submitted query: one to render
  disabled controls during processing, one to re-enable controls afterward.
- Debug prompt/chunk details for consultation mode must be persisted with the
  latest assistant message so they survive the post-processing rerun.

## References
- [`src/ui/app.py`](../../src/ui/app.py) — implementation.
- [`src/llm/client.py`](../../src/llm/client.py) — `LLMError` provider metadata.
- [`tests/test_ui_error_handling.py`](../../tests/test_ui_error_handling.py) — regression tests.
- Issue [#106](https://github.com/G-Ivan-A/clarify-engine-ai/issues/106), PR [#114](https://github.com/G-Ivan-A/clarify-engine-ai/pull/114).

## History
| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-17 | First version: Streamlit retry state, generic error block, guarded logging, and disabled controls for queued generation (BL-13, issue #106). |
