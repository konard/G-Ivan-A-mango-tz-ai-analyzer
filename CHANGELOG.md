# Changelog

Все значимые изменения проекта `clarify-engine-ai` фиксируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### ⚠️ BREAKING CHANGES
- **BREAKING (KB schema, BL-32, issue #152):** Документация и конфиг синхронизированы с окном `chunk_size=512`, `chunk_overlap=64`, guardrails `[384, 768]`. Для индексов, созданных на старом окне `256/32` или `250/50`, требуется полная переиндексация KB перед сравнением retrieval-метрик.

### Documentation
- **DOCUMENTATION: BL-40 ADR sync & numbering convention (issue #166).** Pure
  documentation synchronization across `docs/ADR/001..009` with `CONCEPT.md` v2.5
  and the BL-34 architecture-consistency audit. No source/config/contract
  changes. Reaffirmed every Accepted ADR (`001, 002, 004A, 004B, 005, 006,
  007A, 008, 009`) and explicitly excluded Draft ADRs (`003 Multi-Agent`,
  `007B Canonical Cache / Pivot`) from the Pilot architecture per CONCEPT.md
  §2.3 invariants. Promoted the «ADR-NNNA / ADR-NNNB» disambiguation notation
  in [`docs/ADR/README.md`](docs/ADR/README.md) (orthogonal pairs `004A/004B`,
  `007A/007B`, status glossary, BL-40 alignment note). Added §History v1.1
  entries to all reaffirmed ADRs. Highlights:
  ADR-001 — references BL-22 (`docs/standards/llm-behavior.md`) and BL-34
  §CHK-01;
  ADR-002 — explicit **Channel separation** vs. ADR-008 + inline
  `EXPORT_SCHEMA_VERSION = "1.0"`;
  ADR-003 — top-level **🚫 Non-Scope for Pilot** block forbidding `agent_id`,
  `asyncio.Queue`, `parent_run_id`, `agent_trace`, `AGENT_SHARED_SECRET` in
  `src/`;
  ADR-004A/004B — formal Numbering Note blockquotes;
  ADR-005 — explicit `src/llm/masking.py::sanitize_log_record` boundary
  (BL-23 alias);
  ADR-006 — new §Security Contract (`file://` exclusion, path-traversal
  rejection);
  ADR-007B — Numbering Note paired with 007A + §Triggers for Revision tied
  to **Gate 0 — Stability ≥ 5 sessions** (CONCEPT.md §8.1.1);
  ADR-008 — Channel separation vs. ADR-002 + `mask_text()` allow-list;
  ADR-009 — explicit **Mode Contract** table (`use_parent_context=True` only
  in Консультация), pinned `parent_context_max_chars: 6000` default.
- **DOCS: CONCEPT.md → v2.5 SSoT sync (BL-39, issue #164).** Pure documentation
  synchronization (no source/config/contract changes). Bumped header to
  v2.5 / 2026-05-19; expanded §1.1 dual-scope goal (batch + consultation +
  multi-format export); added two-mode workflow table to §2.1
  («📊 Анализ ТЗ» stateless / «💬 Консультация» stateful, history ≤ 6); new
  §2.3 Pre-deploy Invariants block (six invariants from BL-34: strict_embedder,
  zero source modification, ADR-003/007 read-only boundary, PoC location,
  decoding-lock centralization, masking-rules single source); rewrote FR-06
  (pipeline vs UI export channels, `EXPORT_SCHEMA_VERSION = "1.0"`, 7 fields),
  FR-07 (sidebar-radio modes, two-layer history limit, graceful error UX),
  FR-08 (dual `run_id` — pipeline UUID4 + LLM `uuid4.hex[:12]`, full audit
  event set incl. `PIPELINE_START/END`, `LLM_REQUEST/RESPONSE`,
  `ui_generation_failed`); refreshed NFR-03/06/08 and added new NFR-10
  (prompt drift control via SHA-256 + `decoding_lock applied`); expanded §6.2
  component registry from 10 to 15 (added `ParentAwareRetriever`,
  `IterativeRetriever`, `QueryExpansionRetriever`, `PromptLoader`,
  `ExportRouter`, `ErrorHandler`); split §6.3 into §6.3.1 «Анализ ТЗ»
  (HARD-LOCK one-shot) and §6.3.2 «Консультация» (opt-in QueryExpansion /
  Iterative / ParentAware); §6.6 now lists concrete config values (chunk_size
  512/64, rrf_k=60, `strict_rag_mode`, `parent_context_max_chars`); added
  risks R-10 (prompt drift), R-11 (Streamlit state corruption), R-12
  (cache/Pivot misuse); added Gate 0 «Stability ≥ 5 sessions» and pre-deploy
  invariant check to §8.1.1; added open questions 8 (cache validation trigger,
  BL-33) and 9 (Timeline Production UI Gateway, ADR-003 Concept §8.1.3) to
  §10; expanded §11 to reference ADR-004 (prompt + UI), ADR-005, ADR-006,
  ADR-007 (canonical-cache + error-handling), ADR-008, ADR-009 and
  `docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md`.

### Fixed
- **PATCH: BL-34-F drift cleanup & audit recommendations (issue #162).**
  Clarified ADR numbering/export-channel docs, added the CONCEPT pre-deploy
  invariant for Concept/Pivot ADRs, and emitted structured
  `PIPELINE_START` / `PIPELINE_END` audit events.
- **PATCH: Code Review triage hardening (BL-26, issue #142).**
  Added the code-review triage matrix, made `strict_embedder: true` explicit
  while allowing an audited hash fallback only for `strict_embedder: false`,
  keyed the Streamlit retriever cache by the md5 of `embedding_config.yaml`,
  kept DOCX locators page-free with table/list traceability, and expanded
  masking regex coverage for 8-prefix RU phones and multi-level internal
  domains.
- **PATCH: configurable LLM provider HTTP timeouts (issue #139).**
  `LLMClient` resolves per-provider `timeout` / `timeout_seconds` values before
  falling back to `OLLAMA_TIMEOUT`, `PROVIDER_TIMEOUT`,
  `LLM_PROVIDER_TIMEOUT`, then 30 seconds. DeepSeek, GigaChat, OpenRouter, and
  Ollama HTTP calls now use the resolved timeout; regression tests cover
  config/env/default precedence.
- **PATCH: Windows UTF-8 config compatibility (BL-26, issue #125).**
  YAML/Markdown/Python text attributes are pinned to UTF-8/LF and regression
  tests verify config loaders read YAML with explicit `encoding="utf-8"` so
  Russian Windows `cp1251` locales do not trigger `UnicodeDecodeError`.
- **PATCH: Parent-aware retrieval wiring (BL-10, issue #137).**
  KB UI again exposes the `search_kb` retrieval path, composes multi-hop and
  query expansion with `ParentAwareRetriever`, enables parent context only for
  «Консультация», and aligns `configs/embedding_config.yaml.required_metadata`
  with `parent_id` / `section_id` / `parent_text`.

### Added
- **BL-35 (issue #158):** Added the isolated Track 2 cache-validation backlog
  `docs/backlog/2026-05-19_track2-cache-validation_v2.md` with `🟡 DEFERRED`
  status, activation gates 0→3, `T2-BL-*` task sequencing, isolation rules,
  and links to ADR-007, CONCEPT NFR-07, and the main backlog v1.3.
- **BL-31 (issue #153):** Added isolated offline DOCX structure enrichment.
  `scripts/tools/enrich_docx_structure.py` parses `.docx` files and writes
  atomized JSON with deterministic span slicing, SHA-256 `exact_text`
  validation metadata, `parent_id`, export-compatible `Ref`, confidence-based
  manual-review flags, local Ollama support, and heuristic fallback.
- **BL-30 (issue #151):** Added an isolated canonical query cache PoC in
  `scripts/poc/semantic_cache_poc.py`, covering Golden Set replay loading,
  deterministic threshold sweeps (`0.90`, `0.95`, `0.97`), cache hit/latency/
  token/accuracy metrics, optional `BAAI/bge-m3` embeddings, regression tests,
  and draft ADR verdict in `docs/ADR/007-canonical-cache-draft.md`.
- **BL-29 (issue #150):** KB UI analysis export now exposes `.xlsx`, `.docx`,
  and `.md` format selectors with session-state persistence, keeps the MVP
  mode locked to `create_new`, and generates downloads through `ExportRouter`
  with a friendly Streamlit error when export generation fails.
- **BL-27 (issue #146):** Accepted export-markup v1.0 as the shared
  `.xlsx` / `.docx` / `.md` result contract, added Pydantic `ExportRow`
  validation for the 7 required fields plus `Ref` / schema metadata, and
  documented ADR-002 extension rules for `schema_version: "1.1"+`.
- **BL-28 (issue #148):** Multi-format export through `ExportRouter`.
  Added `.docx` and `.md` report adapters, report filename templating via
  `configs/export_config.yaml`, pipeline routing by output suffix, and
  multi-sheet `.xlsx` export that maps results by parser locator without
  modifying the source file.
- **BL-14 (issue #136):** Offline Dependency Extraction for KB chunks.
  `scripts/tools/extract_dependencies.py` enriches ChromaDB metadata with
  `related_sections`, `prerequisites`, `see_also`, and
  `dependencies_extracted` using deterministic regex extraction by default and
  optional local Ollama enrichment via `--use-ollama`. `build_index.py` exposes
  `--extract-dependencies` / `--dependency-use-ollama`, and the KB UI decodes
  the metadata into prompt context plus visible «См. также» / prerequisites in
  source chunk expanders. Tests: `tests/test_extract_dependencies.py`,
  `tests/test_metadata_extraction.py`, `tests/test_citation_links.py`.
- **BL-18 (issue #132):** `.docx` ingest is routed through
  `load_requirements_by_extension()` alongside `.xlsx`; `DocxParser` now emits
  non-empty `locator` metadata for paragraphs and table cells, and Excel ingest
  supports multi-sheet workbooks with `sheet_name` in each locator.
- **MINOR: Multi-hop Retrieval for Consultation mode (BL-11, issue #123).**
  `configs/llm_config.yaml` now exposes `rag.multi_hop_enabled: false`,
  `rag.max_hops: 2`, and `rag.min_confidence_to_stop: 0.8`.
  `src/rag/retriever.py::IterativeRetriever` wraps the existing hybrid
  retriever with bounded follow-up retrieval, cross-hop deduplication by
  `(source, chunk_idx)`, and graceful fallback to the accumulated context when
  reflection times out, fails, or returns invalid JSON. `src/ui/app.py`
  hard-locks this path to «Консультация»; «Анализ ТЗ» ignores the flag and
  remains one-shot retrieval. Reflection uses
  `prompts/system_rag_reflection_v1.0.md` with strict JSON output
  `{sufficient, follow_up, confidence}`. Tests:
  `tests/test_iterative_retriever.py`, `tests/test_ui_modes.py`,
  `tests/test_prompt_loader.py`.
- **BL-12 (issue #124):** Query Expansion для режима «Консультация»:
  `QueryExpansionRetriever` генерирует 3–4 семантические переформулировки
  через `prompts/system_rag_query_expansion_v1.md`, выполняет retrieval по
  вариантам запроса и объединяет хиты через RRF с дедупликацией. Флаги
  `rag.query_expansion_enabled: false` и `rag.expansion_count: 3` добавлены
  в `configs/embedding_config.yaml`; graceful fallback возвращает результаты
  исходного запроса при сбое LLM или невалидном JSON.
- **BL-25 (issue #122):** конфигурируемый блок `providers.ollama` в
  `configs/llm_config.yaml` с `${OLLAMA_*:default}` placeholders для
  `model`, `base_url`, `timeout_seconds` и локальными `options`
  (`num_ctx`, `num_thread`, `keep_alive`, `temperature`). `LLMClient`
  применяет YAML/env значения и централизованный `decoding:` к Ollama
  RAG-вызовам; дефолтный timeout повышен до 180 секунд для CPU-only АРМ.
  Документация обновлена в `README.md`, `.env.example` и
  `docs/standards/llm-behavior.md`; регресс-тест —
  `tests/test_llm_client.py::test_ollama_config_loading`.
- **PATCH: dependency hardening (BL-24a, issue #120).** Добавлен
  `torchvision>=0.18.0` в `requirements.txt`, чтобы optional vision-backends
  из `transformers` не засоряли Streamlit-логи `ModuleNotFoundError` при
  чистой установке зависимостей.

## [0.2.0] - 2026-05-18

### ⚠️ BREAKING CHANGES
- **BL-06** (#92): Переход на `chunk_size=512`, `chunk_overlap=64` и section-aware splitting. Требуется полная переиндексация базы знаний: удалить старую ChromaDB-коллекцию и выполнить `python knowledge_base/indexing/build_index.py`.

### Added
- **MINOR: Parent Document Retrieval L2 (BL-10, issue #118).**
  Индексатор сохраняет `parent_id` / `section_id` / `parent_text` для L1-чанков,
  `HybridRetriever` и `HybridChromaRetriever` поддерживают opt-in
  `use_parent_context`, а режим «Консультация» в KB UI передаёт в LLM
  сгруппированный родительский контекст с лимитом `parent_context_max_chars`.
  ADR — [`docs/ADR/009-parent-document-retrieval.md`](docs/ADR/009-parent-document-retrieval.md);
  тесты — `tests/test_retriever.py`, `tests/test_hybrid_chroma_retriever.py`,
  `tests/test_build_index.py`, `tests/test_ui_modes.py`.
- **MINOR: audit trail with run_id tracing & BL-04 compliance (BL-23, issue #103).**
  `src/llm/client.py` creates a 12-hex per-request `run_id` for
  `classify_requirement()` and `generate_rag_response()`, preserves it through
  provider fallback via provider config, and emits masked structured
  `LLM_REQUEST` / `LLM_RESPONSE` records with provider, decoding params,
  prompt version/hash, response status, and latency. Logger failures are
  best-effort and do not interrupt the main LLM request. ADR:
  [`docs/ADR/005-audit-trail.md`](docs/ADR/005-audit-trail.md); tests:
  `tests/test_audit_trail.py`.
- **MINOR: graceful error handling & retry UX (BL-13, issue #106).**
  KB-тестовый UI (`src/ui/app.py`) теперь обрабатывает сбои ретривера и LLM
  без сырых traceback в интерфейсе: запрос сохраняется в
  `st.session_state["last_query"]`, кнопка «Повторить» переиспользует это
  значение, во время queued generation поля ввода блокируются, а ошибка
  рендерится отдельным `st.error("Не удалось получить ответ.")` без
  фейкового RAG-ответа. UI-логи `ui_prompt_built` /
  `ui_generation_failed` несут `run_id`, `error_type`, `provider` и
  изолированы `try/except`, чтобы сбой логирования не ронял Streamlit.
  ADR — [`docs/ADR/007-error-handling.md`](docs/ADR/007-error-handling.md);
  тесты — `tests/test_ui_error_handling.py`.
- **MINOR: evaluation script for RAG metrics (BL-05, issue #105).**
  `scripts/evaluate/evaluate_rag.py` reads the Golden Set from
  `data/golden_set_v1.jsonl`, loads retrieval settings from
  `configs/embedding_config.yaml`, computes Hit Rate@5 and MRR, and writes
  `outputs/eval_report_v1.json`. The runner supports `--config` and emits a
  clear error when the configured Chroma directory is missing. Metric formulas
  are documented in `docs/standards/evaluation-metrics.md`.
- **MINOR: clickable citation links with page anchors (BL-09.1, issue #104).**
  `configs/ui_config.yaml` задаёт `citations.base_url` и `source_dir`,
  `src/ui/app.py` строит Markdown-ссылки вида
  `http://localhost:8000/docs/file.pdf#page=N`, а
  `src/api/static_serve.py` добавляет безопасный FastAPI endpoint
  `GET /docs/{filename}` с валидацией basename/path traversal и
  `application/pdf`. ADR — [`docs/ADR/006-citation-links.md`](docs/ADR/006-citation-links.md);
  тесты — `tests/test_citation_links.py`, `tests/test_static_serve.py`.
- **MINOR: metadata inheritance & coverage improvement (BL-02 hardening, issue #109).**
  `knowledge_base/indexing/build_index.py` добавляет per-document
  `SectionPropagationState`: чанки без локального заголовка наследуют
  ближайший `section_title` / `section_number`, получают audit-флаг
  `section_inherited`, а после длинного разрыва по страницам контекст
  сбрасывается для защиты от ghost inheritance. До первого заголовка
  используется fallback по имени документа (`section_fallback=source_filename`),
  чтобы UI-цитаты имели человекочитаемую подпись.
- **BL-15 (issue #107):** контекстно-зависимый экспорт из KB UI:
  `src/utils/export.py` генерирует `.xlsx` и `.md` в памяти через
  `io.BytesIO`, `configs/export_config.yaml` задаёт строгий allow-list
  Excel-колонок (`requirement_id`, `requirement_text`, `classification`,
  `reasoning`, `citations`), а `src/ui/app.py` показывает кнопки
  «📥 Скачать отчет (.xlsx)» для режима «Анализ ТЗ» и
  «📥 Сохранить диалог (.md)» для режима «Консультация». Экспорт применяет
  `mask_text()` ко всем строковым значениям и не включает служебные поля
  вроде `raw` / `provider`. ADR — [`docs/ADR/008-data-export.md`](docs/ADR/008-data-export.md);
  тесты — `tests/test_context_export.py`.
- `docs/standards/llm-behavior.md` v1.0 — стандарт параметров декодирования LLM (BL-22, issue #101): канонический блок `decoding:` (`temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024`), таблица рекомендуемых значений по провайдерам/режимам (DeepSeek, GigaChat, OpenRouter, Ollama), допустимый коридор изменений в Пилоте, обязательное аудит-логирование `decoding_lock applied`. Зарегистрирован в `docs/standards/README.md`.
- **Prompt Library `prompts/` + `src/llm/prompt_loader.py` (BL-08, issue #94).**
  Все системные и few-shot-промпты вынесены из `src/llm/client.py` и
  `src/ui/app.py` в версионируемые файлы по конвенции
  `<name>_v<MAJOR>.<MINOR>.<ext>`: `prompts/system_classifier_v1.0.md`,
  `prompts/system_rag_v1.0.md`, `prompts/few_shot_examples_v1.0.json`.
  Loader (`load_prompt`, `load_few_shot_examples`,
  `load_prompt_from_path`) вычисляет SHA-256 содержимого и пишет
  `INFO`-запись в JSON-лог с `prompt_name`, `prompt_version`,
  `prompt_sha256`, `run_id` — audit-трасса BL-23. `LLMClient`
  использует `load_prompt_from_path` через существующий
  `DEFAULT_PROMPT_PATH`, публичные сигнатуры не меняются; `src/ui/app.py`
  загружает `system_rag_v1.0.md` через `@st.cache_resource`. Архитектура
  и DoD — [`docs/ADR/004-prompt-management.md`](docs/ADR/004-prompt-management.md);
  изменения промптов — `prompts/prompt_changelog.md`; 16 unit-кейсов в
  `tests/test_prompt_loader.py`.
- **BL-07 (issue #93):** два режима работы KB-тестового UI (`src/ui/app.py`) — **«📊 Анализ ТЗ»** (полностью stateless, токен-cost совпадает с pre-BL-07 baseline) и **«💬 Консультация по документации»** (stateful чат, история ≤ `ui.max_history_messages` сообщений, по умолчанию 6). Переключатель режимов в `st.sidebar.radio`, кнопка «🧹 Очистить историю», автоматический сброс истории при смене режима (`_ensure_mode_state`), инлайн истории в `<history>`-блок промпта без изменения сигнатуры `LLMClient.generate_rag_response()`, JSON-лог `ui_prompt_built mode=… history_messages=… approx_tokens=…` на каждый вызов. Конфиг — `configs/llm_config.yaml` (`ui.max_history_messages`). ADR — [`docs/ADR/004-ui-operation-modes.md`](docs/ADR/004-ui-operation-modes.md); обновлён `docs/CONCEPT.md` §6.2 (компонент UI) и §6.8 (режимы работы UI). Регресс-тесты — `tests/test_ui_modes.py`.
- `src/rag/chunker.py::split_sections` и флаг `section_aware_chunking` в `configs/embedding_config.yaml` — section-aware splitter режет текст по заголовкам (Markdown `#`, нумерованные разделы `\d+(\.\d+)+`, локализованные `Раздел N` / `Section N`, CAPS-блоки PDF) до применения token-окна; заголовок остаётся в первом чанке секции (BL-06, issue #92).
- `tests/test_chunker.py` — unit-тесты L1-контракта: дефолты 512/64, guardrails 384–768, корректность section-aware разбиения и пропагация флагов из конфига (BL-06, issue #92).
- `src/rag/retriever.py` — `HybridChromaRetriever.search()` теперь пишет INFO-лог `bm25_hits=… dense_hits=… fused=… rrf_k=60 top_k=…` на каждый запрос. Лог подтверждает, что в production-пути UI отрабатывает именно фьюжн BM25 + Dense + RRF, а не только векторный поиск (BL-01 DoD, issue #91).
- `tests/test_hybrid_chroma_retriever.py::test_hybrid_chroma_search_logs_fusion_breakdown` — регресс-тест, проверяющий формат строки фьюжн-лога (issue #91).
- `src/ui/app.py` — Streamlit UI для ручного тестирования RAG-пайплайна по базе знаний: поле запроса, кнопка «Search KB», вывод ответа LLM в Markdown, секция «Source Chunks» с именем файла, обрезанным текстом и similarity-скором; сайдбар с тоглом Debug Mode и выбором провайдера (DeepSeek / GigaChat). ChromaDB читается из `knowledge_base/vector_store/` (коллекция `clarify_engine_kb`), эмбеддер `BAAI/bge-m3`, конфиг провайдеров — `configs/llm_config.yaml`, секреты — `.env`. Запуск: `streamlit run src/ui/app.py` (issue #70).
- `python-dotenv` в `requirements.txt` — необходим UI для чтения `.env`.
- `.env.example` — шаблон переменных окружения с плейсхолдерами `DEEPSEEK_API_KEY`, `GIGACHAT_API_KEY` и флагами `USE_TEST_DATA_MODE`, `STRICT_EMBEDDER` (issue #59; `YANDEXGPT_API_KEY` исключён в issue #64).
- `scripts/evaluate/evaluate_quality.py` — CLI для замера качества классификации (Macro-F1 и per-class P/R/F1) против `test_data/gold_standard.json`, поддерживает Excel и JSON-предсказания, JSON-логирование и опциональный детальный отчёт (issue #47, NFR-01).
- `tests/test_quality.py` — smoke-тесты метрик, парсеров входных файлов и CLI evaluate_quality.
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md` — аудит согласованности репозитория, полноты документации и тестируемости требований (issue #21).
- `docs/analysis/2026-05-15_analysis_repo-state-and-mvp-recommendations_v1.md` — анализ состояния репозитория, оценка готовности MVP, профиль нагрузки и рекомендации по доработке кода, архитектуры и документации (issue #35).
- `src/rag/chunker.py` — токенайзер-чанкер на основе `BAAI/bge-m3`, параметры 200–300 токенов с overlap 50 (issue #45 MUST 2).
- `scripts/evaluate/evaluate_quality.py` — расчёт точности/полноты/F1 по `[Статус]` против `test_data/gold_standard.json` (issue #45 SHOULD 1).
- `scripts/evaluate/benchmark_pipeline.py` — бенчмарк пропускной способности пайплайна на N синтетических требований в режимах `stub` / `production` (issue #45 SHOULD 1).
- `CONTRIBUTING.md` — Definition of Done, матрица команд, правила ветвления (issue #45 MAY 1).
- `SECURITY.md` — политика обработки утечек, SLA, контакты Product Owner (issue #45 MAY 1).
- `tests/test_excel_exporter.py`, `tests/test_app_retry.py`, `tests/test_evaluate_quality.py` — регресс-тесты на FR-06 (4-колоночный экспорт), retry-by-RunID и контракт F1-оценщика.
- **BL-01** (#91): Hybrid retrieval (BM25 + `BAAI/bge-m3` dense) с RRF-фьюзией (`k=60`) и INFO-логированием `bm25_hits`, `dense_hits`, `fused`, `rrf_k`, `top_k`.
- **BL-02** (#109): Metadata inheritance (Section Propagation) для чанков базы знаний: наследование `section_title` / `section_number`, audit-флаг `section_inherited`, fallback по имени документа и улучшение coverage.
- **BL-04** (#91): Strict embedder config и централизованное логирование параметров retrieval-пути.
- **BL-06** (#92): Chunker L1: section-aware splitting, improved heading detection, guardrails 384–768 токенов и тесты L1-контракта.
- **BL-07** (#93): Два режима UI (`Анализ ТЗ` / `Консультация по документации`) с историей диалога, очисткой истории и логированием `ui_prompt_built`.
- **BL-08** (#94): Prompt Library (`prompts/`) с версионированием, SHA-256 аудитом, fallback-цепочкой и `src/llm/prompt_loader.py`.
- **BL-15** (#107): Контекстно-зависимый экспорт из KB UI: `.xlsx` для режима анализа ТЗ и `.md` для консультаций, с маскированием строковых данных.
- **BL-22** (#101): Decoding Config: стандарт `docs/standards/llm-behavior.md`, централизованные параметры `temperature`, `top_p`, `seed`, `max_tokens` и аудит `decoding_lock applied`.
- **BL-23** (#103): Расширенный audit trail с `run_id`, latency, provider fallback, prompt version/hash, статусами ответов и masked structured `LLM_REQUEST` / `LLM_RESPONSE`.
- **BL-13** (#106): Graceful error handling and retry UX in KB UI: сохранение последнего запроса, кнопка повторной попытки, блокировка ввода во время queued generation и безопасное отображение ошибок.
- **BL-05** (#105): Evaluation script for RAG metrics: Hit Rate@5, MRR и JSON-отчёт `outputs/eval_report_v1.json`.
- **BL-09.1** (#104): Clickable citation links with page anchors and safe FastAPI static endpoint `GET /docs/{filename}`.
- `src/ui/app.py` — Streamlit UI для ручного тестирования RAG-пайплайна по базе знаний: поле запроса, выбор провайдера, Debug Mode, ответ LLM и секция Source Chunks.
- `python-dotenv` в `requirements.txt` и `.env.example` с плейсхолдерами `DEEPSEEK_API_KEY`, `GIGACHAT_API_KEY`, `USE_TEST_DATA_MODE`, `STRICT_EMBEDDER`.
- `scripts/evaluate/evaluate_quality.py` и `tests/test_quality.py` — CLI и smoke-тесты для метрик качества классификации.
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md` и `docs/analysis/2026-05-15_analysis_repo-state-and-mvp-recommendations_v1.md` — аудит состояния репозитория и рекомендации к MVP.
- `scripts/evaluate/benchmark_pipeline.py` — бенчмарк пропускной способности пайплайна на синтетических требованиях.
- `CONTRIBUTING.md` и `SECURITY.md` — Definition of Done, матрица команд, правила ветвления и политика обработки утечек.
- `tests/test_excel_exporter.py`, `tests/test_app_retry.py`, `tests/test_evaluate_quality.py` — регресс-тесты на FR-06, retry-by-RunID и контракт F1-оценщика.

### Changed
- `configs/embedding_config.yaml` и `docs/standards/embedding-model.md` обновлены под параметры `chunk_size=512`, `chunk_overlap=64`, `metadata_coverage_min=0.65`, section propagation и обязательную схему метаданных.
- `src/rag/chunker.py` переведён на L1-параметры 512/64, guardrails 384–768 и section-aware splitter, включаемый через YAML.
- `src/ui/app.py` показывает кликабельные citation labels с `section_title`, `section_number` или fallback-подписью раздела.
- `docs/ADR/003-multi-agent-orchestration-draft.md` обновлён до Concept (Review) v1.1 с контрактами очередей, event envelope, отказоустойчивостью, security/compliance и observability.
- Проект переименован с `mango-tz-ai-analyzer` на `clarify-engine-ai`; брендовые упоминания заменены на нейтральные термины.
- `docs/CONCEPT.md` обновлён до версии 2.0 с актуальными FR/NFR, рисками, Exit Criteria, глоссарием и реестром связанных документов.
- `requirements.txt` актуализирован для retrieval-зависимостей (`rank_bm25`, `chromadb`, `sentence-transformers`) и установки CPU-версии `torch`.
- `src/llm/client.py` использует экспоненциальный backoff `[5с, 15с, 45с]` для retriable-ошибок при последовательных LLM-вызовах.
- `src/pipeline.py` помечает полный отказ строки как `[Статус: Ошибка]` и продолжает обработку остальных требований.
- `src/exporters/excel_exporter.py` ограничивает экспорт ровно четырьмя MVP-колонками `[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]`.
- `src/app.py` вызывает реальный `run_analysis`, отображает прогресс и счётчики, поддерживает повтор только ошибочных строк и вкладку справки для БА.
- `src/rag/retriever.py` удалил hash-embedding fallback в Strict-Embedder Mode и теперь падает с явной ошибкой при недоступной модели.
- `knowledge_base/indexing/build_index.py` добавил SHA-256 хеши, синхронизацию с `source_registry.csv` и чанкинг через `src/rag/chunker.py`.
- `configs/masking_rules.yaml` оставляет только согласованные паттерны Email/Phone/IP/Domain; маски ФИО/юрлиц/ИП отложены.

### Documentation
- Созданы и обновлены ADR: `docs/ADR/004-prompt-management.md`, `docs/ADR/004-ui-operation-modes.md`, `docs/ADR/005-audit-trail.md`, `docs/ADR/006-citation-links.md`, `docs/ADR/007-error-handling.md`, `docs/ADR/008-data-export.md`.
- Обновлены `docs/CONCEPT.md`, `docs/standards/embedding-model.md`, `docs/standards/llm-behavior.md`, `docs/standards/evaluation-metrics.md`, `docs/standards/README.md`.
- Добавлены sprint/audit материалы в `docs/audit/` и `docs/analysis/`, включая отчёты по состоянию репозитория, MVP-рекомендациям и RAG-оптимизации.

### Removed
- `knowledge_base/indexing/chunk_config.yaml` удалён; параметры чанкинга читаются только из `configs/embedding_config.yaml`.
- Провайдеры Qwen (DashScope) и YandexGPT удалены из fallback-цепочки, конфигов, `.env.example` и документации; актуальная цепочка — DeepSeek и GigaChat.

## [0.1.0-mvp] - 2026-05-12

### Added
- Концепция MVP: [`docs/CONCEPT.md`](docs/CONCEPT.md) v1.0 (разделы 1–8).
- ADR-001: RAG с гибридным поиском (BM25 + Dense + RRF), `BAAI/bge-m3`, ChromaDB.
- Стандарты: roles, naming-convention, embedding-model, шаблоны для analysis / decision.
- Аудит маскирования данных: [`docs/audit/data-masking_v1.md`](docs/audit/data-masking_v1.md).
- Streamlit UI (`src/app.py`) с вкладками «Анализ ТЗ» и «Концепция и БЗ».
- Excel-парсер (`src/parsers/excel_parser.py`), гибридный retriever (`src/rag/retriever.py`), LLM-клиент с fallback на 4 провайдера (`src/llm/client.py`), Excel-экспортёр (`src/exporters/excel_exporter.py`), end-to-end пайплайн (`src/pipeline.py`).
- Конфигурации: `configs/llm_config.yaml`, `configs/embedding_config.yaml`, `configs/classification_rules.json`, `configs/masking_rules.yaml`.
- Промпты: `prompts/system_classifier_v1.0.md`, `few_shot_examples.json`, `prompt_changelog.md`.
- Тестовые данные: `test_data/sample_tz.xlsx`, `test_data/gold_standard.json`.
- Unit-тесты (14): `tests/test_excel_parser.py`, `tests/test_llm_client.py`, `tests/test_pipeline.py`, `tests/test_retriever.py`.
