# ADR-004: Two UI Operation Modes — "Анализ ТЗ" (stateless) and "Консультация" (stateful, history ≤ 6)

> 🔢 **Numbering Note (004B — UI Operation Modes).** В каталоге `docs/ADR/`
> существует и второй документ под номером `004` — [`004-prompt-management.md`](004-prompt-management.md)
> (ADR-004A, Prompt Management). Оба файла официально называются «ADR-004»,
> описывают **ортогональные** области принятия решений и сохраняются с тем
> же номером по конвенции [`docs/ADR/README.md`](README.md). Для однозначности
> в обсуждениях и аудит-логах используйте кодировку «ADR-004B
> (UI Operation Modes)» для этого файла и «ADR-004A (Prompt Management)»
> — для соседнего.

## Status
Accepted (2026-05-17; reaffirmed 2026-05-19 by BL-40 ADR-sync — см. §History v1.1; chat fallback chain synced by BL-42 — см. §History v1.2)

## Context

`src/ui/app.py` is a Streamlit-based KB tester that lets analysts query the
indexed knowledge base. Until BL-07 the UI ran in a single stateless mode:
each query produced one prompt of the form
`<context>…</context>\n<question>…</question>` and returned a one-shot answer.

The Pilot phase (`docs/CONCEPT.md` §8.1.2) introduces two distinct user
scenarios that share retrieval + LLM components but differ sharply in their
token-budget profile:

1. **Анализ ТЗ** — batch validation of requirements from a TZ document.
   Hundreds of requirements pass through the pipeline per session. Adding
   chat history to every prompt would inflate token usage 3–5× and violate
   NFR-06 (`token cost`), which is unacceptable for mass validation.
2. **Консультация** — conversational assistance over the knowledge base
   (clarifications, recommendations, follow-up questions). Without history
   the user has to repaste prior context into every question; the experience
   feels broken and increases human error.

Mixing the two scenarios on a single UI surface with a shared history buffer
silently regresses analysis mode the moment the user asks even one
consultation-style question. We need a hard separation that the UI enforces.

Related documents:
- [`docs/CONCEPT.md`](../CONCEPT.md) §6 (Architecture), FR-07 (Streamlit UI),
  NFR-06 (token cost).
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.md) — BL-07.
- [`docs/ADR/001-rag-architecture.md`](001-rag-architecture.md) — RAG pipeline.
- Issue [#93](https://github.com/G-Ivan-A/clarify-engine-ai/issues/93).

## Decision

We split the UI into two modes selected via a sidebar `st.sidebar.radio`:

1. **📊 Анализ ТЗ — stateless.**
   - `st.session_state.messages` is reset on entry and on every mode switch.
   - The prompt shape is unchanged: `<context>…</context>\n<question>…</question>`.
   - There is no history block. Token cost matches the pre-BL-07 baseline.

2. **💬 Консультация по документации — stateful.**
   - `st.session_state.messages` keeps the chat turns.
   - A hard cap `ui.max_history_messages` (default `6`) caps how many of
     the most recent messages are forwarded to the LLM. The cap is
     **enforced before the call** and **again after the call** so neither
     prompts nor in-memory state can grow unbounded.
   - History is rendered into the user prompt as a `<history>` block
     (`Пользователь:` / `Ассистент:` lines) so the LLM can distinguish
     speakers without changing the signature of
     `LLMClient.generate_rag_response()` (DoD requirement of issue #93).
   - A "🧹 Очистить историю" sidebar button resets the buffer on demand.

Switching modes always clears history. This is enforced by
`_ensure_mode_state` which compares the active mode to the previously stored
one and calls `_reset_history()` on transition.

A coarse token estimate (`len(prompt) // 4`) is logged on every call as
`ui_prompt_built mode=… history_messages=… approx_tokens=…`. Real tokeniser
metrics live with the provider; this log line lets operators correlate UX
mode with token-budget impact without adding a runtime dependency.

The signature of `LLMClient.generate_rag_response(system_prompt, user_prompt)`
**does not change**. History is purely a UI concern; the client stays
provider-agnostic.

## Consequences

### Positive
- Analysis mode keeps the previous token profile — no regression for mass
  TZ validation, NFR-06 stays satisfied.
- Consultation mode delivers the conversational UX users expect, with a
  predictable upper bound on prompt size.
- The mode toggle is a single, discoverable Streamlit control. Operators
  can reset history at any moment without restarting the app.
- `LLMClient` remains a pure transport layer; future modes (e.g. multi-hop)
  can compose new prompt shapes without touching the client.

### Negative
- Two code paths in `main()` add complexity to the UI. Mitigated by sharing
  retrieval and LLM call logic via `_retrieve_and_answer`.
- Consultation answers depend on whatever happens to be in the trimmed
  history; users have to remember to "Очистить историю" when switching
  topics within consultation mode (the "switch modes" reset is automatic,
  but inside consultation it isn't).
- A coarse token estimate is not a real tokeniser. It tracks the trend
  reliably but the absolute value is approximate.

### Neutral
- `ui.max_history_messages` is configurable per environment via
  `configs/llm_config.yaml`. Lowering it to `0` effectively turns
  consultation mode back into stateless mode without code changes.

## Configuration

```yaml
# configs/llm_config.yaml
ui:
  max_history_messages: 6
  # BL-42 (issue #170): contractual fallback chain for "Консультация" chat
  # mode. Read by LLMClient.generate_rag_response via _chat_fallback_chain().
  # DeepSeek is intentionally absent (paid-only, deprecated for Pilot).
  chat_fallback_providers:
    - "gigachat"
    - "ollama"
```

The Python helper `get_max_history_messages()` clamps invalid values to a
non-negative integer and falls back to the default (`6`) when the key is
missing or malformed.

The chat fallback chain is resolved by `LLMClient._chat_fallback_chain()` in
the following order: `ui.chat_fallback_providers` → `pipeline.fallback_providers`
→ top-level `fallback_providers` → built-in default
(`DEFAULT_CHAT_FALLBACK_CHAIN = ("gigachat", "ollama")`). No hardcoded chain
is left in `src/llm/client.py` (Pre-deploy Invariant #5).

## Triggers for Revision
- Pilot feedback shows `max_history_messages: 6` is too low for productive
  consultation (target: BA satisfaction ≥ 4.0 / 5, see R-04).
- The token-cost log shows consultation prompts crossing the provider
  context window despite the cap (would imply per-message length, not
  message count, should be the throttle).
- A future ADR introduces a multi-message LLM client signature; this ADR
  would migrate from inline history to a `messages: list[Message]` argument.

## References
- [`docs/CONCEPT.md`](../CONCEPT.md) §6, FR-07, NFR-06.
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.md) — BL-07.
- [`configs/llm_config.yaml`](../../configs/llm_config.yaml) — `ui.max_history_messages`.
- [`src/ui/app.py`](../../src/ui/app.py) — implementation.
- Issue [#93](https://github.com/G-Ivan-A/clarify-engine-ai/issues/93), PR [#99](https://github.com/G-Ivan-A/clarify-engine-ai/pull/99).

## History
| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-05-17 | Первая редакция: фиксация двух режимов UI (Анализ ТЗ — stateless, Консультация — stateful с историей ≤ 6 сообщений), кнопка очистки, сброс при смене режима, логирование оценки токенов (issue #93, BL-07). |
| 1.1 | 2026-05-19 | BL-40 (issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)): ADR-sync. Добавлен явный «Numbering Note (004B — UI Operation Modes)» со ссылкой на [`docs/ADR/README.md`](README.md) и кодировкой ADR-004A/004B. Контракт `ui.max_history_messages: 6` и `_ensure_mode_state` подтверждены без изменений; код и тесты не модифицируются. |
| 1.2 | 2026-05-19 | BL-42 (issue [#170](https://github.com/G-Ivan-A/clarify-engine-ai/issues/170)): синхронизация fallback-цепочки чата с production-реальностью Пилота. В §Configuration зафиксирован новый ключ `ui.chat_fallback_providers: ["gigachat", "ollama"]` и резолвер `LLMClient._chat_fallback_chain()`. DeepSeek исключён из чата (paid-only, deprecated for Pilot). Контракт `ui.max_history_messages: 6` без изменений. |
