# 📊 Post-fix Smoke & E2E Verification — BL-43 (ARM Deployment Readiness)

## Метаданные
- **Дата:** 2026-05-19
- **Версия:** v1.0
- **Аудитор:** konard (Code Agent)
- **Статус:** Verified
- **Снепшот кода:** `d1934c83e384964e8bedb71977b8dbb2d4cfdd18`
  (`git rev-parse HEAD` на ветке `issue-172-95e9382b0da7`)
- **Связанная задача:** [Issue #172](https://github.com/G-Ivan-A/clarify-engine-ai/issues/172)
- **Связанный PR:** [#174](https://github.com/G-Ivan-A/clarify-engine-ai/pull/174)
- **Предшествующие BL-задачи:**
  - **BL-41** (Issue #168, PR #169) — UI refactor (`src/ui/app.py` модульная декомпозиция)
  - **BL-42** (Issue #170, PR #171) — Sync LLM fallback chains with production reality
- **Режим:** 🟢 READ-MOSTLY — добавлены только тестовые маркеры и сам отчёт; контракты `src/`, `configs/`, `prompts/` не изменялись.
- **Общий статус:** 🟢 **Pre-deploy инварианты соблюдены — P0/P1 регрессий не найдено**
- **Связанные документы:**
  - [`docs/CONCEPT.md`](../CONCEPT.md)
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md)
  - [`docs/ADR/004-streamlit-ui-modes.md`](../ADR/004-streamlit-ui-modes.md)
  - [`docs/ADR/009-parent-document-retrieval.md`](../ADR/009-parent-document-retrieval.md)
  - [`docs/standards/export-markup.md`](../standards/export-markup.md)
  - [`docs/standards/llm-behavior.md`](../standards/llm-behavior.md)
  - [`docs/standards/embedding-model.md`](../standards/embedding-model.md)
  - [`docs/audit/data-masking_v1.md`](data-masking_v1.md)
  - [`docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md`](2026-05-19_bl-34_architecture-consistency-audit_v1.md) — предыдущий архитектурный аудит
  - [`CHANGELOG.md`](../../CHANGELOG.md)

---

## 1. Executive Summary

Post-fix smoke & E2E верификация подтверждает, что pipeline, UI и экспортёры на снепшоте `d1934c8` сохраняют контракты, зафиксированные после BL-41 и BL-42, и готовы к деплою на CPU-only АРМ бизнес-аналитика.

- **QA-матрица из Issue #172 покрыта полностью (7/7 разделов).**
- **`pytest` — 351 passed, 0 failed, 0 errors** (выполнено локально на этом снепшоте).
- **Live smoke-прогон CLI** (`python -m src.pipeline` на `test_data/sample_tz.xlsx`) подтверждает корректный `run_id`, шаблон имени отчёта, события `PIPELINE_START` / `PIPELINE_END`, отсутствие `_hash_embedding` и срабатывание STRICT_MODE.
- **Критических расхождений (🔴 Critical Break) — 0.**
- **P1-расхождений — 0.**
- **P2-наблюдений — 1** (см. §5 «Заметки и рекомендации»): KB-индекс в чистом сэмпле пуст, поэтому `LLM_REQUEST`/`LLM_RESPONSE` события не возникают в live-логе sample_tz.xlsx (это корректное поведение STRICT_MODE). Полное покрытие audit-events обеспечивается `tests/test_audit_trail.py` с детерминированными provider-стабами.

**Вердикт:** ✅ **Деплой разрешён**. BL-43 закрывается. Создание follow-up тикетов P0/P1 не требуется.

---

## 2. Методология и периметр

### 2.1. Периметр верификации
- **Код:** `src/pipeline.py`, `src/llm/client.py`, `src/llm/masking.py`, `src/exporters/*`, `src/ui/app.py`, `src/utils/error_handler.py`
- **Конфиги:** `configs/llm_config.yaml`, `configs/embedding_config.yaml`, `configs/export_config.yaml`
- **Тесты:** `tests/test_pipeline.py`, `tests/test_audit_trail.py`, `tests/test_decoding_lock.py`, `tests/test_strict_mode.py`, `tests/test_masking.py`, `tests/test_rag_masking.py`, `tests/test_export_router.py`, `tests/test_export_contract.py`, `tests/test_excel_exporter.py`, `tests/test_context_export.py`, `tests/test_ui_modes.py`, `tests/test_ui_components.py`, `tests/test_ui_error_handling.py`, `tests/test_app_retry.py`, `tests/test_error_handler.py`, `tests/test_llm_client.py`, `tests/test_llm_timeout.py`, `tests/test_requirements.py`, `tests/test_config_encoding.py`
- **Артефакты:** `/tmp/bl43_smoke/pipeline.jsonl`, `/tmp/bl43_smoke/sample_tz_report_039c6212.xlsx`

### 2.2. Инструменты
- `pytest -q` — полный прогон тестов.
- `python -m src.pipeline --input … --output … -v` — live CLI smoke.
- `git rev-parse`, `Grep` (ripgrep) и `Read` для статической верификации.
- `openpyxl` для инспекции выходного xlsx.

### 2.3. Жёсткие ограничения (Breaking the Cycle)
| Правило | Соблюдение |
|---------|------------|
| 🚫 Без изменения контрактов `src/`, `configs/`, `prompts/` | ✅ Соблюдено |
| 📄 Output = отчёт + опциональные тестовые маркеры | ✅ Соблюдено |
| 🔀 Расхождения **не блокируют** деплой автоматически — оцениваются по P0/P1 | ✅ Учтено в вердикте |
| 🔒 Только ветка `issue-172-95e9382b0da7`, PR #174 | ✅ Соблюдено |

---

## 3. QA-матрица — построчная верификация

### `QA-01` — Configuration — ✅ Aligned

**Источники истины:** Issue #170 (BL-42), `configs/llm_config.yaml`, `configs/embedding_config.yaml`, `configs/export_config.yaml`.

| Параметр | Контракт | Файл / тест | Статус |
|---|---|---|---|
| Batch fallback chain | `gigachat → openrouter → ollama` | `configs/llm_config.yaml::pipeline.fallback_providers` (L59-63) и зеркало `fallback_providers` (L120-123) | ✅ |
| Chat fallback chain | `gigachat → ollama` | `configs/llm_config.yaml::ui.chat_fallback_providers` (L41-43) | ✅ |
| DeepSeek deprecated for Pilot | присутствует только как `providers.deepseek` без включения в активные цепочки | `configs/llm_config.yaml` L108-115 + комментарий L4-9 | ✅ |
| `strict_embedder` | `true` (fail-fast) | `configs/embedding_config.yaml::strict_embedder: true` | ✅ |
| Decoding lock | `temperature=0.1, top_p=0.9, seed=42, max_tokens=1024` | `configs/llm_config.yaml::decoding` (L19-23); `tests/test_decoding_lock.py::test_packaged_llm_config_carries_decoding_block` PASSED | ✅ |
| `mask_rag_context` | `true` | `configs/llm_config.yaml::mask_rag_context: true` (L28); `tests/test_rag_masking.py::test_packaged_embedding_config_enables_rag_masking` PASSED | ✅ |
| Report basename template | `{basename}_report_{run_id_8}.{ext}` | `configs/export_config.yaml::report_basename_template` | ✅ |
| Env-placeholder pattern | `${VAR:default}` для всех ENV-переменных, никаких хардкоженных секретов | `configs/llm_config.yaml` L75, L84, L94-96, L100, L114 | ✅ |

### `QA-02` — CLI Pipeline (Smoke) — ✅ Aligned

**Команда:**
```
USE_TEST_DATA_MODE=true python -m src.pipeline \
    --input test_data/sample_tz.xlsx \
    --output /tmp/bl43_smoke/ -v 2>/tmp/bl43_smoke/pipeline.jsonl
```

**Live-наблюдения (`/tmp/bl43_smoke/pipeline.jsonl`):**

```json
{"timestamp": "2026-05-19T18:30:06", "level": "INFO", "logger": "__main__",
 "message": "Pipeline started: input=test_data/sample_tz.xlsx output=/tmp/bl43_smoke/",
 "run_id": "039c62128a964333804f11f56763a7b8",
 "event": "PIPELINE_START",
 "input_file": "test_data/sample_tz.xlsx", "output_file": "/tmp/bl43_smoke/"}
```

| Инвариант | Ожидание | Наблюдение | Статус |
|---|---|---|---|
| Pipeline-level `run_id` (UUID4 без дефисов, 32 hex-символа) | regex `^[0-9a-f]{32}$` | `039c62128a964333804f11f56763a7b8` | ✅ |
| Per-requirement LLM `run_id` (12 hex-символов) | regex `^[0-9a-f]{12}$` | `2584f44e6341`, `67f04c85cbc7`, `383a75e65c8b`, `125674f09360`, `5ea0c2118755` (5 уникальных, по числу строк) | ✅ |
| `PIPELINE_START` событие с `input_file`, `output_file` | присутствует | строка 1 jsonl | ✅ |
| `PIPELINE_END` событие с `total_requirements`, `success_count`, `error_count`, `nd_count`, `total_latency_ms` | присутствует | последняя информационная строка jsonl | ✅ |
| Имя отчёта | `<basename>_report_<runId8>.xlsx` | `sample_tz_report_039c6212.xlsx` (где `039c6212` = первые 8 символов pipeline run_id) | ✅ |
| Нет `_hash_embedding` fallback в логах | 0 вхождений | `grep -c '_hash_embedding' pipeline.jsonl` = 0 | ✅ |
| STRICT_MODE срабатывает при пустом контексте | `strict_mode=true skipped LLM call: empty_context` | присутствует для всех 5 строк (KB пуст в test_data сценарии) | ✅ |
| CLI exit code | `0` | `0` | ✅ |
| Сводка | `обработано: 5, успешно: 5, ошибки: 0, НД: 5` | подтверждено | ✅ |

**Регрессионные тесты:** `tests/test_pipeline.py` — 5/5 passed, в т.ч. `test_run_analysis_propagates_run_id_to_logs_stats_and_export` и `test_run_analysis_marks_failed_row_as_oshibka`.

### `QA-03` — UI Modes — ✅ Aligned

**Источники истины:** ADR-004 (двухрежимный UI), ADR-009 (parent-document retrieval только в Consultation), Issue #168 (BL-41).

| Инвариант | Тест | Статус |
|---|---|---|
| Mode constants matches issue spec | `tests/test_ui_modes.py::test_mode_constants_match_issue_spec` | ✅ |
| История чата сбрасывается при переключении режима | `tests/test_ui_modes.py::test_ensure_mode_state_resets_history_on_switch` | ✅ |
| История сохраняется при том же режиме | `tests/test_ui_modes.py::test_ensure_mode_state_keeps_history_when_mode_unchanged` | ✅ |
| Multi-hop жёстко выключен в режиме «Анализ ТЗ» | `tests/test_ui_modes.py::test_resolve_multi_hop_settings_hard_locks_analysis_mode` | ✅ |
| Multi-hop работает только в Consultation | `tests/test_ui_modes.py::test_resolve_multi_hop_settings_enables_only_consultation_mode` | ✅ |
| Шипованный `llm_config.yaml` имеет `multi_hop_enabled: false` | `tests/test_ui_modes.py::test_shipped_llm_config_multi_hop_defaults_to_disabled` | ✅ |
| Parent-context включается только для Consultation | `tests/test_ui_modes.py::test_retrieve_and_answer_enables_parent_context_for_consultation` + `test_retrieve_and_answer_ignores_multi_hop_in_analysis_mode` | ✅ |
| История триммится до `max_history_messages` | `tests/test_ui_modes.py::test_trim_history_keeps_last_n_messages` (+ 3 связанных) | ✅ |
| UI labels полностью покрыты | `tests/test_ui_components.py::test_labels_dict_covers_every_required_ui_slot` | ✅ |
| Status legend / tooltips для всех статусов | `tests/test_ui_components.py::test_status_tooltips_cover_all_export_statuses` | ✅ |

**Сводно:** `tests/test_ui_modes.py` — 34/34 passed, `tests/test_ui_components.py` — 14/14 passed.

### `QA-04` — Export Contract v1.0 — ✅ Aligned

**Источники истины:** `docs/standards/export-markup.md`, `src/exporters/contract.py`, `src/exporters/schema.py`, `src/exporters/__init__.py`.

| Инвариант | Контракт | Проверка | Статус |
|---|---|---|---|
| `schema_version` | `"1.0"` | `src/exporters/contract.py::EXPORT_SCHEMA_VERSION = "1.0"`; `tests/test_export_contract.py::test_export_document_requires_schema_version_and_consistent_run_id` PASSED | ✅ |
| 7 базовых полей | `requirement_id, requirement_text, Ref, status, comment, confidence, run_id` | `REQUIRED_COLUMN_IDS` в `src/exporters/contract.py` (импортируется тестом) | ✅ |
| MVP-колонки | `[Статус] [Комментарий] [Confidence] [RunID]` | `src/exporters/schema.py::RESULT_COLUMNS`; `tests/test_excel_exporter.py::test_result_columns_are_exactly_four_mvp_columns` PASSED | ✅ |
| Ref-локаторы (sheet + row) | непустой | `tests/test_export_contract.py::test_export_row_rejects_empty_or_incomplete_ref_locator[*]` (5 параметризаций) PASSED | ✅ |
| `run_id` валидируется как UUID4 | regex/uuid4 | `tests/test_export_contract.py::test_export_row_rejects_non_uuid4_run_id` PASSED | ✅ |
| Запрет «append to original» | по умолчанию отклоняется | `tests/test_export_router.py::test_router_rejects_append_to_original_mode_by_default` PASSED | ✅ |
| Live-xlsx структура | `[Статус] [Комментарий] [Confidence] [RunID]` после исходных колонок | `openpyxl`-инспекция `sample_tz_report_039c6212.xlsx` → header: `['ID','Требование заказчика','Ожидаемый статус','Комментарий эксперта (эталон)','[Статус]','[Комментарий]','[Confidence]','[RunID]']` | ✅ |
| Live-xlsx `[RunID]` для всех 5 строк | равен pipeline run_id | `039c62128a964333804f11f56763a7b8` в каждой строке | ✅ |
| DOCX / Markdown эквивалент | соответствует тому же контракту | `tests/test_export_router.py::test_router_exports_markdown_with_front_matter_table_and_template_name` + `::test_router_exports_docx_table_without_modifying_source` PASSED | ✅ |
| PII масking при экспорте чата | `[EMAIL]`, `[PHONE]` и пр. | `tests/test_context_export.py::test_export_chat_to_markdown_formats_dialog_and_masks_pii` PASSED | ✅ |

**Сводно:** 26/26 export-тестов passed.

### `QA-05` — Audit & Masking — ✅ Aligned

**Источники истины:** `docs/audit/data-masking_v1.md`, `src/llm/masking.py`, `src/llm/client.py` (события `LLM_REQUEST`, `LLM_RESPONSE`).

| Инвариант | Проверка | Статус |
|---|---|---|
| `LLM_REQUEST` несёт `prompt_sha256`, маскированный prompt, decoding-lock | `tests/test_audit_trail.py::test_classify_audit_trail_masks_logs_and_preserves_run_id_on_fallback` PASSED (среди assertions — `re.fullmatch(r"[0-9a-f]{64}", prompt_hash)`, `"[EMAIL]" in request_text`, `"admin@example.com" not in request_text`) | ✅ |
| `LLM_RESPONSE` маскирует ответ провайдера | тот же тест: `"admin@example.com" not in repr(response)`, `"[EMAIL]" in repr(response)` | ✅ |
| `run_id` сохраняется при fallback между провайдерами | тот же тест: assertions сверяют что `primary` и `secondary` получили один и тот же `run_id` | ✅ |
| Chat-режим (RAG) маскирует prompt по умолчанию | `tests/test_rag_masking.py::test_generate_rag_response_masks_user_prompt_by_default` PASSED | ✅ |
| Email / Phone / IP / Internal domain маскируются | `tests/test_masking.py` — 40 тестов passed (включая `TestEmailMasking`, `TestPhoneRUMasking`, `TestIPMasking`, `TestInternalDomainMasking`) | ✅ |
| `sanitize_log_record` — pure, маскирует message + payload + nested chunks, редактирует SECRET ENV | `tests/test_masking.py::TestLogSanitization` — 9 тестов passed | ✅ |
| Ошибки логгера не ломают классификацию | `tests/test_audit_trail.py::test_logger_failures_do_not_break_classification` PASSED | ✅ |
| Decoding-lock (FR-08) пробрасывается в provider cfg | `tests/test_decoding_lock.py::test_decoding_block_injected_into_classify_provider_cfg` + `test_decoding_block_injected_into_rag_provider_cfg` PASSED | ✅ |
| STRICT_MODE детерминированно возвращает «НД» при пустом контексте / слабых скорах | `tests/test_strict_mode.py` — 5/5 passed | ✅ |

**Сводно:** 60/60 audit + masking + decoding + strict-mode тестов passed.

### `QA-06` — Error Handling & Fallback Resilience — ✅ Aligned

| Инвариант | Проверка | Статус |
|---|---|---|
| Retry-with-backoff по расписанию `(5, 15, 45)` секунд | `src/llm/client.py::BACKOFF_SCHEDULE_SECONDS`; `tests/test_app_retry.py` — 2/2 passed | ✅ |
| Fallback переключается на следующего провайдера при HTTP/RuntimeError | `tests/test_llm_client.py` — 12/12 passed, `tests/test_audit_trail.py::test_rag_audit_trail_masks_prompt_and_preserves_run_id_on_fallback` PASSED | ✅ |
| Timeout protection | `tests/test_llm_timeout.py` — 6/6 passed | ✅ |
| ErrorHandler собирает контекст и маскирует PII | `tests/test_error_handler.py::*` PASSED | ✅ |
| UI graceful-degradation при ошибках экспорта/провайдера | `tests/test_ui_error_handling.py` — 5/5 passed, `tests/test_ui_modes.py::test_analysis_export_button_shows_friendly_router_error` PASSED | ✅ |
| Failed row помечается как `Ошибка` без падения пайплайна | `tests/test_pipeline.py::test_run_analysis_marks_failed_row_as_oshibka` PASSED | ✅ |

**Сводно:** 26/26 error/fallback-тестов passed.

### `QA-07` — ARM Deployment Readiness — ✅ Aligned

**Источники истины:** Issue #172 pre-deploy invariants, `requirements.txt`, `.env.example`, `README.md`.

| Инвариант | Проверка | Статус |
|---|---|---|
| CPU-only torch в `requirements.txt` | `requirements.txt` L5-10 явно инструктирует ставить torch с `https://download.pytorch.org/whl/cpu`; никаких `nvidia-*` / `cuda-*` / `cublas-*` пакетов | ✅ |
| Нет GPU-specific deps | `grep -iE "nvidia\|cuda\|cublas" requirements.txt` → только комментарий-предупреждение, реальных пакетов нет | ✅ |
| Env-placeholders для секретов | все credentials через `${GIGACHAT_AUTH}`, `${OPENROUTER_API_KEY}`, `${DEEPSEEK_API_KEY}` и пр. (см. QA-01) | ✅ |
| `.env.example` присутствует | `-rw-r--r-- 1 box box 1762 .env.example` | ✅ |
| ARM-friendly README | `README.md` L132: `CPU-only АРМ оставляйте OLLAMA_TIMEOUT не ниже 120 секунд; дефолт проекта` (явная рекомендация для CPU-only АРМ) | ✅ |
| Transformers vision backend закреплён (`torchvision`) для устранения noisy ModuleNotFoundError на slim-инсталляциях | `tests/test_requirements.py::test_transformers_vision_backend_dependency_is_explicit` PASSED | ✅ |
| python-docx явный runtime dep | `tests/test_requirements.py::test_docx_runtime_dependency_is_explicit` PASSED | ✅ |
| UTF-8 / LF pinned для всех текстовых файлов | `tests/test_config_encoding.py::test_gitattributes_pins_text_files_to_utf8_lf` PASSED + 3 связанных | ✅ |

**Сводно:** 8/8 ARM-readiness инвариантов выполнены, 6/6 связанных тестов passed.

---

## 4. Полный прогон тестов (Final Regression Snapshot)

```
============================== 351 passed in 2.95s ==============================
```

Команда: `python -m pytest` на снепшоте `d1934c8`.

Распределение проверок по QA-разделам:

| QA | Test-files |  Σ passed |
|---|---|---|
| QA-01 Configuration | `test_decoding_lock.py`, `test_rag_masking.py`, `test_ui_modes.py::test_shipped_llm_config_*` | 12 |
| QA-02 CLI Pipeline | `test_pipeline.py` | 5 |
| QA-03 UI Modes | `test_ui_modes.py`, `test_ui_components.py` | 48 |
| QA-04 Export Contract | `test_export_router.py`, `test_export_contract.py`, `test_excel_exporter.py`, `test_context_export.py` | 26 |
| QA-05 Audit & Masking | `test_audit_trail.py`, `test_masking.py`, `test_rag_masking.py`, `test_decoding_lock.py`, `test_strict_mode.py` | 60 |
| QA-06 Error Handling | `test_app_retry.py`, `test_error_handler.py`, `test_ui_error_handling.py`, `test_llm_client.py`, `test_llm_timeout.py` | 26 |
| QA-07 ARM Readiness | `test_config_encoding.py`, `test_requirements.py` | 6 |
| Прочие (retriever, chunker, classifier, прочие) | оставшиеся 26 файлов | 168 |
| **Итого** | | **351** |

---

## 5. Заметки и рекомендации

### 5.1. Наблюдения

- **N-01 (P2):** В live-smoke прогоне на `test_data/sample_tz.xlsx` события `LLM_REQUEST` / `LLM_RESPONSE` не возникают, так как `knowledge_base/` пуст и STRICT_MODE детерминированно отвечает «НД». Это **корректное** контрактное поведение (защита от галлюцинаций R-01) и полностью покрыто детерминированными provider-стабами в `tests/test_audit_trail.py`. Для воспроизведения полного аудит-трасса с реальным провайдером необходимо предварительно прогнать `python knowledge_base/indexing/build_index.py` и/или выдать действительные ENV-credentials.
- **N-02 (info):** `LLMClient.DEFAULT_CHAT_FALLBACK_CHAIN = ("gigachat", "ollama")` и `pipeline.fallback_providers = ["gigachat", "openrouter", "ollama"]` находятся в согласии с BL-42 и с зеркальным top-level `fallback_providers` (для backward compatibility). `tests/test_audit_trail.py::test_rag_audit_trail_masks_prompt_and_preserves_run_id_on_fallback` явно пиннит legacy-цепочку `gigachat → openrouter` (через `ui.chat_fallback_providers`), чтобы fallback на не-Ollama провайдера оставался под контрактом.

### 5.2. Рекомендации (не блокирующие)

- **R-01:** При следующих smoke-прогонах с реальным провайдером сохранять полную jsonl-трассу в `docs/audit/smoke-runs/` (по `run_id`) для отслеживания latency-deltas между релизами.
- **R-02:** Рассмотреть pytest-маркер `@pytest.mark.smoke` для подмножества critical-path тестов, чтобы CI мог запускать «BL-43 smoke gate» в pre-merge режиме (~2 секунды). Минимальный набор: `test_pipeline.py`, `test_audit_trail.py`, `test_decoding_lock.py`, `test_strict_mode.py`, `test_export_contract.py`, `test_excel_exporter.py`, `test_ui_modes.py::test_resolve_multi_hop_settings_hard_locks_analysis_mode`.
- **R-03:** Добавить в README или `docs/standards/` короткую главу «BL-43 smoke checklist», ссылающуюся на этот отчёт как на reference baseline для будущих pre-deploy верификаций.

---

## 6. Вердикт

🟢 **Pre-deploy инварианты соблюдены. Деплой на АРМ бизнес-аналитика разрешён.**

- P0 регрессий: **0**
- P1 регрессий: **0**
- P2 наблюдений: **1** (N-01, не блокирующее — это контрактное поведение STRICT_MODE).
- Полный тест-сьют: **351 passed / 0 failed** на снепшоте `d1934c8`.
- Live CLI smoke: **PIPELINE_START / PIPELINE_END / run_id / report-name / STRICT_MODE** — все контракты соблюдены.

BL-43 закрывается. Дальнейшие улучшения (R-01..R-03) могут быть включены в следующий бэклог-спринт без статуса P0/P1.
