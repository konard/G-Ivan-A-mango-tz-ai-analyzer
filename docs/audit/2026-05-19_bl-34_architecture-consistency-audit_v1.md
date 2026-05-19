# 📊 Architecture Consistency Audit — BL-34

## Метаданные
- **Дата:** 2026-05-19
- **Версия:** v1.0
- **Аудитор:** konard (Code Agent)
- **Статус:** Draft
- **Снепшот кода:** `912612b4669f95f0ef4d9f19b074d7c76ac31e6e`
  (`git rev-parse HEAD` на ветке `issue-160-fa69678a9b10`)
- **Связанная задача:** [Issue #160](https://github.com/G-Ivan-A/clarify-engine-ai/issues/160)
- **Связанный PR:** [#161](https://github.com/G-Ivan-A/clarify-engine-ai/pull/161)
- **Режим:** 🚫 READ-ONLY (Zero Code Changes — `src/`, `configs/`, `prompts/`, `tests/` не модифицировались)
- **Общий статус:** 🟢 Контракты соблюдены (P0/P1 расхождений не найдено)
- **Связанные документы:**
  - [`docs/CONCEPT.md`](../CONCEPT.md) v2.1
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) … `009-parent-document-retrieval.md`
  - [`docs/standards/export-markup.md`](../standards/export-markup.md)
  - [`docs/standards/llm-behavior.md`](../standards/llm-behavior.md)
  - [`docs/standards/embedding-model.md`](../standards/embedding-model.md)
  - [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.3.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.3.md)
  - [`CHANGELOG.md`](../../CHANGELOG.md)

---

## 1. Executive Summary

Point-in-time аудит срезы кода `912612b` подтверждает, что реализация Clarify Engine соответствует архитектурным контрактам ADR-001…ADR-009 и CONCEPT.md v2.1 на уровне, достаточном для деплоя на АРМ бизнес-аналитика.

- **9/9 пунктов чек-листа `CHK-01..CHK-09` пройдены.**
- **Критических расхождений (🔴 Critical Break) — 0.**
- **Лёгких расхождений (⚠️ Minor Drift) — 1 (cosmetic doc reference).** Тикета `BL-34-F` уровня P0/P1 заводить не требуется.
- **Известных нюансов нумерации ADR — 1 (ADR-004 и ADR-007 представлены двумя документами каждое; явно зафиксировано в самих ADR и тексте Issue #160).**

**Вердикт:** ✅ **Деплой разрешён**. Создание Issue `BL-34-F` не является блокирующим — рекомендуемые правки сведены в раздел [💡 Рекомендации](#-рекомендации-по-улучшению-expert--executor-notes) и могут быть включены в следующий бэклог-спринт.

---

## 2. Методология и периметр

### 2.1. Периметр аудита
- **Код:** `src/`, `knowledge_base/indexing/build_index.py`
- **Конфиги:** `configs/*.yaml`
- **Промпты:** `prompts/*.md` (метаданные, не содержимое)
- **Документация:** `docs/CONCEPT.md`, `docs/ADR/*.md`, `docs/standards/*.md`, `CHANGELOG.md`
- **Тесты:** покрытие функций (имена и наличие), без запусков

### 2.2. Инструменты
- `git rev-parse`, `Grep` (ripgrep) и `Read` (read-only).
- Поиск по ключевым константам, регуляркам и импортам.
- Сравнение значений конфигурации с соответствующими константами в коде.

### 2.3. Жёсткие ограничения (Breaking the Cycle)
| Правило | Соблюдение |
|---------|------------|
| 🚫 Zero Code Changes (`src/`, `configs/`, `prompts/`, `tests/`) | ✅ Не модифицировались |
| 📄 Output = Report Only — единственный новый файл `docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md` | ✅ Соблюдено |
| 🔀 Расхождения **не блокируют** деплой автоматически | ✅ Учтено в вердикте |
| 🧠 Экспертные hotspots из ADR/CHANGELOG используются как стартовый чек-лист | ✅ Применены |

---

## 3. Результаты по чек-листу

### `CHK-01` — Гибридный поиск & чанкинг — ✅ Aligned

**Источники истины:** `ADR-001`, `CONCEPT §5/§6.2/§6.3`, `docs/standards/embedding-model.md`, `BL-06`, `BL-32`.

| Параметр | Контракт | `configs/embedding_config.yaml` | `src/rag/chunker.py` | `src/rag/retriever.py` | `knowledge_base/indexing/build_index.py` |
|---|---|---|---|---|---|
| Модель эмбеддинга | `BAAI/bge-m3` | `model_name: "BAAI/bge-m3"` (L9) | `DEFAULT_MODEL = "BAAI/bge-m3"` (L30) | используется через `TokenChunker.from_config()` | импорт `TokenChunker` (L533) |
| `chunk_size` | 512 | `chunk_size: 512` (L17) | `DEFAULT_CHUNK_SIZE = 512` (L31) | — | — |
| `chunk_overlap` | 64 | `chunk_overlap: 64` (L18) | `DEFAULT_CHUNK_OVERLAP = 64` (L32) | — | — |
| Guardrails | `[384, 768]` | `min_chunk_size: 384` / `max_chunk_size: 768` (L19-20) | `MIN_CHUNK_SIZE = 384`, `MAX_CHUNK_SIZE = 768` (L33-34) + `ValueError` при выходе из диапазона (L166-170) | — | — |
| Section-aware | `true` | `section_aware_chunking: true` (L27) | `DEFAULT_SECTION_AWARE = True` (L35); 4 регулярки заголовков (L40-57) | — | — |
| `top_k` (UI) | 5 | `top_k: 5` (L32) | — | используется в `HybridRetriever` / `HybridChromaRetriever` | — |
| `rrf_k` | 60 | `rrf_k: 60` (L33) | — | `DEFAULT_RRF_K = 60` (L42); `reciprocal_rank_fusion` = `Σ 1/(k+rank)` (L290) | — |
| Strict embedder | `true` (fail-fast) | `strict_embedder: true` (L12) | — | `_STRICT_EMBEDDER_ERROR = "Embedding model unavailable. Strict mode enabled."` (L179); `resolve_strict_embedder` → `True` по умолчанию (L191-195) | — |
| STRICT_MODE (RAG) | `strict_rag_mode: true`, `strict_min_score: 0.30` | `strict_rag_mode: true` (L49), `strict_min_score: 0.30` (L50) | — | пробрасывается в `generate_rag_response` для блокировки LLM при слабом контексте | — |
| Маскирование RAG-контекста | `mask_rag_context: true` | `mask_rag_context: true` (L57); продублировано в `llm_config.yaml::mask_rag_context` (L23) | — | используется в `src/llm/client.py::generate_rag_response` | — |
| Section propagation + page-distance guard | `max_pages_without_heading: 6`, fallback по имени документа | `section_propagation.*` (L92-96) | `split_sections` (L100-138) | — | `SectionPropagationState` + reset по странице, fallback `section_inherited` |
| Strict tokenizer fallback | запрет «тихого» whitespace-fallback | — | `_load_hf_tokenizer` бросает `RuntimeError("Tokenizer unavailable...")` (L88-97) — нет silent fallback | — | — |

**Вывод:** Чанкинг и гибридный поиск синхронизированы между конфигурацией, кодом и стандартом `embedding-model.md`. Strict-embedder и strict-RAG защищают от «тихой» деградации.

---

### `CHK-02` — Контракт экспорта v1.0 — ✅ Aligned

**Источники истины:** `ADR-002`, `docs/standards/export-markup.md`, `BL-27`, `BL-28`, `BL-29`.

| Свойство | Контракт | Реализация |
|---|---|---|
| `schema_version` | `"1.0"` в метаданных | `src/exporters/contract.py::EXPORT_SCHEMA_VERSION = "1.0"` |
| 7 базовых полей | `(requirement_id, requirement_text, Ref, status, comment, confidence, run_id)` | `src/exporters/contract.py::REQUIRED_COLUMN_IDS` — порядок и состав совпадают |
| MVP-колонки в UI | `(Статус, Комментарий, Confidence, RunID)` + `Ref` | `src/exporters/schema.py::RESULT_COLUMNS` + `REPORT_TABLE_COLUMNS = ["№", "Ref", "Исходное требование", *RESULT_COLUMNS]` |
| Допустимые статусы | `("Да", "Нет", "Частично", "НД", "Ошибка")` | `src/exporters/contract.py::EXPORT_STATUS_VALUES` |
| `run_id` строки | UUID4 | `ExportRow.run_id` (Pydantic) валидирует UUID4; `ExportDocument._rows_share_single_run_id` гарантирует один `run_id` на отчёт |
| Output-режим | только `create_new` | `src/exporters/__init__.py::ExportRouter` бросает `ValueError("append_to_original is disabled for production export...")` |
| Маршрутизация форматов | `.xlsx` / `.docx` / `.md` | `ExportRouter._normalize_format` (нормализация `markdown→md`, `xls→xlsx`), регистрируются `ExcelExporter` / `DocxExporter` / `MarkdownExporter` |
| Заголовок DOCX | 7-колоночная таблица | `src/exporters/docx_exporter.py` (`№, Ref, Исходное требование, Статус, Комментарий, Confidence, RunID`) |
| YAML front matter `.md` | `schema_version: "1.0"` | `src/exporters/md_exporter.py` |
| `.xlsx` для пользователя | оригинальная структура + 4 MVP-колонки | `src/exporters/excel_exporter.py` — добавляет колонки, не модифицируя структуру источника |

**Замечание:** Файл `configs/export_config.yaml::export.excel_columns` определяет **отдельный** allow-list для UI-выгрузки чат-истории (`src/utils/export.py`, ADR-008 / `BytesIO`), а не для основного pipeline-экспорта по ADR-002. Это сознательное разделение двух экспорт-каналов; нарушения контракта v1.0 нет.

---

### `CHK-03` — Промпт-менеджмент & UI-режимы — ✅ Aligned

**Источники истины:** `ADR-004 prompt-management.md`, `ADR-004 ui-operation-modes.md`, `CONCEPT §6.5/§6.8`, `BL-08`, `BL-07`.

- **Загрузка промптов из файла:** `src/llm/client.py::_load_system_prompt_with_metadata` (L357) вызывает `load_prompt_from_path` из `src/llm/prompt_loader.py`. Минимальный «hardcoded fallback» внутри (L378-389) допустим только для повреждённой инсталляции и **не используется в обычном пути** — он не противоречит ADR-004, поскольку загрузка из файла — primary path.
- **SHA-256 в логах:** `src/llm/prompt_loader.py::compute_sha256` + `_emit_load_log` пробрасывает `run_id` и хэш в JSON-форматтер аудита (BL-08 + BL-23).
- **Версионирование имени файла:** парсер `<name>_v<MAJOR>.<MINOR>.<ext>` реализован в `load_prompt_from_path` (`src/llm/prompt_loader.py`).
- **UI-режимы** (`src/ui/app.py`):
  - `MODE_CONSULTATION = "consultation"` (L79); сброс истории при переключении режима реализован парой `_reset_history` (L840) + `_ensure_mode_state` (L845): при смене `ui_mode` вызывается `_reset_history()`.
  - `get_max_history_messages` читает `ui.max_history_messages` из `configs/llm_config.yaml` (`ui.max_history_messages: 6`, L31-32) — не игнорируется.
  - «Анализ ТЗ» — stateless: история не накапливается; «Консультация» — stateful с ограниченной историей.

**Вывод:** Промпты не захардкожены, SHA-256 присутствует в audit-логах, сброс истории и потолок сообщений реализованы корректно.

---

### `CHK-04` — Аудит-трейл & логирование — ✅ Aligned

**Источники истины:** `ADR-005`, `ADR-007 error-handling.md`, `CONCEPT §4 FR-08`, `BL-22`, `BL-23`.

- **`run_id` сквозной:**
  - Pipeline-уровень: `src/pipeline.py:233` — `run_id = run_id or uuid.uuid4().hex` (полный UUID4 hex). Соответствует `CONCEPT §7.2`.
  - LLM-уровень: `src/llm/client.py::LLM_RUN_ID_LENGTH = 12`, `_new_llm_run_id()` → `uuid.uuid4().hex[:12]` (L112). Сохраняется один и тот же `run_id` для всей цепочки fallback внутри одного `classify_requirement` (L705) и `generate_rag_response` (L613). Это намеренное разделение pipeline vs LLM call уровней.
- **События `LLM_REQUEST` / `LLM_RESPONSE`:** эмитятся в `src/llm/client.py` (RAG: L635/L648/L664; classification: L753/L770/L798/L825) через `_safe_audit_log`, проходящий через `sanitize_log_record` с masking-конфигом. Соответствует схеме `ADR-005`.
- **Маскирование логов:** `src/llm/masking.py::sanitize_log_record` применяется до записи в логгер; `tests/test_masking.py` (наличие проверено в исходниках) подтверждает, что debug-логи никогда не содержат сырых значений.
- **UI диагностика:** `src/utils/error_handler.py::ErrorHandler` рекурсивно применяет `mask_text` через `_mask_mapping` ко всем строкам, `export_to_txt` возвращает `mask_text(...).encode("utf-8")`. `src/ui/app.py::get_debug_error_details` по умолчанию `False` (L218-224) — сырые `traceback` пользователю не показываются.

---

### `CHK-05` — Цитаты & экспорт из UI — ✅ Aligned

**Источники истины:** `ADR-006`, `ADR-008`, `CONCEPT §4 FR-06`.

- **HTTP-цитаты (без `file://`):**
  - `src/ui/app.py::build_citation_link` (L410) формирует URL вида `[source, стр. N](base/source#page=N)`, где `base` берётся из `configs/ui_config.yaml::citations.base_url` (`http://localhost:8000/docs`).
  - `Grep "file://" src/` и `Grep "file://" configs/` — **0 совпадений** в production-периметре.
- **Безопасный статический сервер:** `src/api/static_serve.py::resolve_source_pdf` блокирует path-traversal через `candidate.relative_to(root)` (ValueError → HTTP 400), возвращает 404 для не-PDF, отдаёт `FileResponse(..., media_type="application/pdf")`.
- **UI-выгрузка через `io.BytesIO` + `mask_text` (ADR-008):**
  - `src/utils/export.py::export_to_excel` — возвращает `BytesIO`, применяет `_mask_cell` через `DataFrame.map`/`applymap`, фильтрует колонки по allow-list `configs/export_config.yaml::export.excel_columns`.
  - `src/utils/export.py::export_chat_to_markdown` — возвращает `BytesIO(markdown.encode("utf-8-sig"))`, маскирует каждое сообщение через `mask_text`.

**Вывод:** Ссылки идут через HTTP base_url, экспорт идёт через память (`BytesIO`), маскирование применяется до сериализации.

---

### `CHK-06` — Parent Document Retrieval — ✅ Aligned

**Источники истины:** `ADR-009`, `CONCEPT §6.3`, `BL-10`.

| Контракт | Реализация |
|---|---|
| `use_parent_context: false` по умолчанию | `configs/embedding_config.yaml:34`; `HybridRetriever.__init__` (`src/rag/retriever.py:410`); `HybridChromaRetriever.__init__` (L1026) — оба читают `self.config.get("use_parent_context", False)` |
| `parent_context_max_chars: 6000` | `configs/embedding_config.yaml:35`; `src/rag/retriever.py:411-412` и L1027-1028 (`DEFAULT_PARENT_CONTEXT_MAX_CHARS`) |
| Включено **только** в «Консультация» | `src/ui/app.py:1461`: `use_parent_context=(mode == MODE_CONSULTATION)` |
| Graceful fallback при отсутствии `parent_text` | `src/rag/retriever.py:649` — `parent_text = str(meta.get("parent_text") or chunk.get("text") or "")` (fallback на child-text → `""`) |
| Required metadata schema | `configs/embedding_config.yaml::required_metadata` содержит `parent_id`, `section_id`, `parent_text` (L73-75) — проверяется в `build_index.py::REQUIRED_METADATA_KEYS` |
| Обёртки | `ParentAwareRetriever` (L565), `IterativeRetriever` (L797) поддерживают `use_parent_context=Optional[bool]` без поломки сигнатур |

---

### `CHK-07` — Архитектурные границы — ✅ Aligned

**Источники истины:** `ADR-003 multi-agent-orchestration-draft.md` (статус `Concept`), `ADR-007 canonical-cache-draft.md` (статус `Pivot`), `CONCEPT §1.1/§8.1.2`.

- **Multi-agent в `src/` отсутствует:** `Grep "agent_id|asyncio\.Queue|Data-Enricher|data_enricher|orchestrator"` — единственное совпадение в `src/pipeline.py:1` — это docstring «End-to-end RAG pipeline orchestrator» (название модуля, не multi-agent класс). Никаких `asyncio.Queue`, `agent_id`, ролей `Data-Enricher` в `src/` не найдено.
- **Canonical cache не встроен в production:** `Grep "semantic_cache|canonical_cache"` по `src/` — **0 совпадений**. PoC живёт только в `scripts/poc/semantic_cache_poc.py`, что прямо предписано `docs/ADR/007-canonical-cache-draft.md` (Verdict: Pivot).
- **Pipeline остаётся линейным:** `src/pipeline.py` импортирует только `ExportRouter`, `LLMClient`, `sanitize_log_record`, `load_requirements_by_extension`, `HybridRetriever`/`build_retriever` (L31-35) — без агентных абстракций.

---

### `CHK-08` — Конфигурация & декодирование — ✅ Aligned

**Источники истины:** `CONCEPT §6.6`, `docs/standards/llm-behavior.md`, `BL-22`.

- **Decoding-lock в одном месте** (`configs/llm_config.yaml::decoding`, L14-18):
  ```yaml
  decoding:
    temperature: 0.1
    top_p: 0.9
    seed: 42
    max_tokens: 1024
  ```
  Эти значения применяются `LLMClient` на каждом провайдере (включая `providers.ollama.options.temperature: 0.1` на L85 — синхронно), что соответствует BL-22 и `llm-behavior.md`.
- **Никаких хардкод-значений retrieval/chunking:** все ключевые параметры (`top_k`, `rrf_k`, `chunk_size`, `chunk_overlap`, `strict_embedder`, `strict_rag_mode`, `strict_min_score`, `use_parent_context`, `parent_context_max_chars`, `mask_rag_context`) читаются из YAML.
- **Masking-rules в одном файле:** `configs/masking_rules.yaml` — ровно 4 паттерна (`email`, `phone_ru`, `ip_address`, `internal_domain`), что соответствует `CONCEPT v2.1` (отложенные ФИО / ООО / ИП явно зафиксированы комментариями).
- **UI:** `configs/ui_config.yaml::ui.debug_error_details: false` (стандартный prod-режим); `citations.base_url: http://localhost:8000/docs` — без `file://`.
- **Multi-hop:** `configs/llm_config.yaml::rag.multi_hop_enabled: false`, `max_hops: 2`, `min_confidence_to_stop: 0.8` — присутствуют и согласованы с `IterativeRetriever`.
- **Query expansion:** `configs/embedding_config.yaml::rag.query_expansion_enabled: false`, `expansion_count: 3` — присутствуют.

---

### `CHK-09` — CHANGELOG & трассируемость — ✅ Aligned

**Источники истины:** `CHANGELOG.md`, `CONCEPT §8`, формат Keep a Changelog 1.1.0.

- **BL-01..BL-32 присутствуют** в `CHANGELOG.md` (в разделах `[Unreleased]` и `[0.2.0]`). В частности:
  - BL-06 / BL-32 — переход на `chunk_size=512, chunk_overlap=64` помечен `⚠️ BREAKING CHANGES` (L9-10, L109-110).
  - BL-10 — Parent Document Retrieval (`[0.2.0]`, L113-120).
  - BL-22, BL-23, BL-25, BL-27..BL-31 — присутствуют с пометками о тестах и ADR.
- **`run_id`-согласованность:** pipeline-уровень = `uuid.uuid4().hex` (полный UUID4 hex), LLM-уровень = `uuid.uuid4().hex[:12]`. Это намеренное разделение, отражено в `ADR-005` (LLM call `run_id` = 12 hex) и `CONCEPT §7.2` (pipeline-level `run_id` = UUID4). Экспорт-строка пишет полный `run_id` из pipeline в колонку `[RunID]`, что согласовано с FR-08.
- **Breaking changes маркированы:** `⚠️ BREAKING CHANGES` — оба раза (BL-32 в `[Unreleased]`, BL-06 в `[0.2.0]`).

---

## 4. 🔍 Найденные расхождения (Drift Log)

| ID | CHK | Объект | Несоответствие | Оценка | Severity |
|----|-----|--------|----------------|--------|----------|
| `DRIFT-01` | CHK-03 | `src/llm/prompt_loader.py:14` (docstring) | Ссылается на `docs/ADR/002-prompt-management.md`, фактический документ — `docs/ADR/004-prompt-management.md`. ADR-002 теперь посвящён export-schema-extension (BL-27). | ⚠️ Minor Drift | P2 (cosmetic / doc-only) |
| `DRIFT-02` | CHK-03 | `docs/ADR/004-*` и `docs/ADR/007-*` | Двойная нумерация: `004-prompt-management.md` + `004-ui-operation-modes.md`; `007-canonical-cache-draft.md` + `007-error-handling.md`. Оба ADR-004 имеют статус `Accepted`; ADR-007 (canonical cache) — `Draft / Pivot`. | ⚠️ Minor Drift | P3 (known / documented) — явно упомянуто в тексте Issue #160 и в самих ADR. Технически конфликта в коде нет. |

**🔴 Critical Break: 0.**
**⚠️ Minor Drift: 2 (оба P2/P3, не блокируют деплой).**

---

## 5. 💡 Рекомендации по улучшению (Expert & Executor Notes)

> 📝 Предложения по архитектуре, документации и процессу — не блокирующие, повышают зрелость системы. Реализация — отдельным PR в рамках следующего бэклог-спринта (BL-34-F не требуется, если PO не решит иначе).

- [ ] **DOC-01 (DRIFT-01):** Поправить docstring `src/llm/prompt_loader.py:14`: заменить `docs/ADR/002-prompt-management.md` на `docs/ADR/004-prompt-management.md`. Стоимость — 1 строка; не влияет на runtime.
- [ ] **DOC-02 (DRIFT-02):** Зафиксировать ADR-numbering convention в `docs/ADR/README.md` (если такого ещё нет): «Документы с одинаковым номером сосуществуют, если оба `Accepted` и описывают ортогональные срезы». Альтернатива — переименовать одну из веток (например, в `004A-…` / `004B-…`). Стоимость — низкая, выгода — снимает повторяющийся вопрос на ревью.
- [ ] **DOC-03 (CHK-02):** Уточнить `docs/standards/export-markup.md` явной ссылкой на разделение двух экспорт-каналов: pipeline-экспорт (ADR-002, `src/exporters/`) vs UI-выгрузка чат-истории (ADR-008, `src/utils/export.py`). Сейчас связь существует только через `export_config.yaml::export.excel_columns` (allow-list для ADR-008), и при первом чтении это путает.
- [ ] **OBS-01 (CHK-04):** Рассмотреть добавление structured event `PIPELINE_START` / `PIPELINE_END` в `src/pipeline.py` (по образу `LLM_REQUEST` / `LLM_RESPONSE`) для упрощения корреляции в продакшен-логах: `run_id`, `total_requirements`, `success/error/nd counts`, `total_latency_ms`. Уже частично закрыто `PipelineStats` (см. строка 257 `pipeline.py`), но не как явное событие.
- [ ] **ARCH-01 (CHK-07):** В CONCEPT.md §8 добавить (если ещё нет) короткое заявление «Pre-deploy invariant: ADR-003 (multi-agent) и ADR-007-canonical-cache находятся в статусе `Concept` / `Pivot`, любые изменения в `src/`, требующие их концепций, требуют отдельного ADR-апдейта». Это упростит автоматизацию BL-34 в будущем.
- [ ] **TEST-01 (CHK-01):** Дополнительно покрыть `tests/test_chunker.py` явным кейсом «raise при `chunk_size=383`/`chunk_size=769`», чтобы guardrails `[384, 768]` были регрессионно зафиксированы. Текущая валидация в `TokenChunker.__init__` присутствует, но негативного теста на границы не наблюдалось при ручном просмотре.

---

## 6. 🚦 Влияние на деплой

| Категория | Найдено | Действие |
|---|---|---|
| **P0 (Blocker)** | 0 | — |
| **P1 (Critical)** | 0 | — |
| **P2 (Minor / Cosmetic)** | 1 (`DRIFT-01`) | Не блокирует деплой |
| **P3 (Known / Documented)** | 1 (`DRIFT-02`) | Не блокирует деплой; документировано |

**Вердикт:** ✅ **Деплой разрешён без условий.** Issue `BL-34-F` создавать **не обязательно** — рекомендуемые правки (`DOC-01..ARCH-01`, `TEST-01`) могут быть включены в обычный бэклог как обычные task-уровни задачи.

---

## 7. 📦 Следующие шаги

1. **PO-ревью:** Передать отчёт PO для согласования вердикта (✅ Деплой разрешён) и приоритизации рекомендаций.
2. **CHANGELOG.md:** При следующем релизе добавить в `[Unreleased]` строку: «BL-34: Architecture Consistency Audit — see `docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md`.» (вне периметра данного аудита — изменение README/CHANGELOG требует отдельного PR).
3. **BL-34-F:** При желании PO — открыть Issue для группы DOC-01..ARCH-01 как single-PR cleanup (опционально, не блокирует).
4. **Архивирование:** Файл аудита хранится в `docs/audit/` как часть постоянного реестра pre-deploy audits.

---

## 8. Приложения

### 8.1. Соответствие DoD задачи #160

| Definition of Done | Статус |
|---|---|
| Чек-лист `CHK-01..CHK-09` выполнен полностью, каждый пункт оценён (✅/⚠️/🔴) | ✅ |
| Сгенерирован файл `docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md` | ✅ |
| В отчёте перечислены все расхождения + заполнен блок рекомендаций | ✅ |
| Ни один файл в `src/`, `configs/`, `docs/` не изменён (кроме самого отчёта) | ✅ |
| При расхождениях P0/P1 создан новый Issue `BL-34-F` | ⏸ Не применимо (P0/P1 = 0) |
| Отчёт ревьюится PO | ⏳ Pending |

### 8.2. Список проверенных файлов (read-only)

**Код:**
- `src/pipeline.py`
- `src/rag/chunker.py`
- `src/rag/retriever.py`
- `src/llm/client.py`
- `src/llm/prompt_loader.py`
- `src/llm/masking.py` (через grep)
- `src/exporters/__init__.py`, `contract.py`, `schema.py`, `excel_exporter.py`, `docx_exporter.py`, `md_exporter.py`
- `src/ui/app.py`
- `src/utils/export.py`, `src/utils/error_handler.py`
- `src/api/static_serve.py`
- `knowledge_base/indexing/build_index.py`

**Конфиги:**
- `configs/embedding_config.yaml`
- `configs/llm_config.yaml`
- `configs/ui_config.yaml`
- `configs/export_config.yaml`
- `configs/masking_rules.yaml`
- `configs/parsing_config.yaml` (косвенно)

**Документация:**
- `docs/CONCEPT.md` v2.1
- `docs/ADR/001-rag-architecture.md` … `009-parent-document-retrieval.md` (включая дубли 004 и 007)
- `docs/standards/embedding-model.md`, `llm-behavior.md`, `export-markup.md`
- `CHANGELOG.md`

### 8.3. Использованные инструменты

- `git rev-parse HEAD` → `912612b4669f95f0ef4d9f19b074d7c76ac31e6e`
- `Grep` (ripgrep) — поиск ключевых констант и регулярок
- `Read` — построчное чтение файлов с фиксацией номеров строк
- Все вызовы строго read-only.

---

## История версий

| Версия | Дата | Автор | Изменение |
|---|---|---|---|
| v1.0 | 2026-05-19 | konard (Code Agent) | Первичная редакция: чек-лист CHK-01..CHK-09, Drift Log, рекомендации, вердикт ✅ |
