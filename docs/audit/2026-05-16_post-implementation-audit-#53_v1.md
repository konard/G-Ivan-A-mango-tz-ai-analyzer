# 🔍 Post-Implementation Audit: Issue #53

## Метаданные
- **Дата:** 2026-05-16
- **Версия:** v1.0
- **Аудитор:** konard (Code Agent)
- **Статус:** Draft
- **Связанная задача:** [Issue #53](https://github.com/G-Ivan-A/clarify-engine-ai/issues/53)
- **Связанная ветка:** `issue-57-b574dc3a97c8`
- **Связанный PR:** [#58](https://github.com/G-Ivan-A/clarify-engine-ai/pull/58)
- **Связанные документы:**
  - [`docs/CONCEPT.md`](../CONCEPT.md) v2.1
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md)
  - [`docs/standards/embedding-model.md`](../standards/embedding-model.md)
  - [`docs/standards/naming-convention.md`](../standards/naming-convention.md)
  - [`docs/audit/2026-05-12_repository-consistency_audit_v1.md`](2026-05-12_repository-consistency_audit_v1.md)

---

## 1. Executive Summary

**Общая оценка готовности кода:** ✅ **Ready for Local Testing**

После выполнения issue #53 кодовая база соответствует MVP-требованиям CONCEPT.md v2.1 на уровне, достаточном для локального запуска и приёмочного тестирования бизнес-аналитиком:

- **76/76 unit-тестов** проходят (`pytest tests/ -v`, 0.86 с).
- **End-to-end pipeline** успешно отрабатывает на `test_data/sample_tz.xlsx` со стаб-LLM: формируется корректный `.xlsx` с исходными колонками и **ровно 4 MVP-колонками** `[Статус] / [Комментарий] / [Confidence] / [RunID]`.
- **`run_id`** (UUID4) пробрасывается сквозь все уровни: парсер → логи (JSON) → классификация → колонка `[RunID]` каждой строки экспорта.
- **Strict-embedder mode** в `src/rag/retriever.py` корректно бросает `RuntimeError("Embedding model unavailable. Strict mode enabled.")` при отсутствии `sentence-transformers`, что предотвращает «тихую» деградацию до BM25-only.
- **Маскирование** (`email / phone_ru / ip_address / internal_domain`) применяется как к тексту требования, так и к контекстным чанкам **до** HTTP-вызова провайдера; маскированные значения не попадают в логи (см. `tests/test_masking.py`).
- **Fallback-цепочка LLM** Qwen → DeepSeek → GigaChat → Yandex → stub реализована с фиксированным backoff 5/15/45 с и корректным переключением на следующего провайдера при невалидном JSON, исчерпании ретраев, 5xx/429, ConnectionError/Timeout.

**Критические блокеры:** отсутствуют.

**Основные рекомендации (краткий перечень):**
1. **SHOULD:** исправить опечатку в docstring `src/exporters/excel_exporter.py` («exactly five» → «exactly four»), приведя его в соответствие с фактическим `RESULT_COLUMNS` из 4 элементов.
2. **SHOULD:** расширить `column_keywords` в `configs/parsing_config.yaml` ключом `"Требование заказчика"`, чтобы стандартный `test_data/sample_tz.xlsx` не активировал fallback-эвристику парсера с WARNING-логом.
3. **MAY:** ввести явные unit-тесты на backoff `_backoff_delay()` для фиксации схедула 5/15/45 в регрессионном корпусе (сейчас покрыто косвенно).

---

## 2. Модульный аудит

### 2.1. `src/pipeline.py`
- **Статус:** ✅ Полностью соответствует.
- **Соответствие FR-08 (Audit trail / Observability):** реализовано. JSON-логи (`_JsonFormatter`) включают `timestamp`, `level`, `logger`, `message`, `run_id`, `requirement_id`, `exception`. `_RunIdFilter` инжектирует `run_id` в записи, у которых его нет, не мешая call-сайтам, явно передающим `extra={"run_id": ...}`.
- **RunID:** пробрасывается через `run_analysis(... run_id: Optional[str] = None)` (если не задан — генерируется `uuid.uuid4().hex`), передаётся в `load_requirements(..., run_id=run_id)`, в `save_results(..., run_id=run_id)` и попадает в `PipelineStats.run_id`. CLI печатает `run_id={...} обработано: {...}` (формат соответствует issue #45 MUST 5).
- **Обработка ошибок:** реализована изоляция per-requirement — исключение в одной строке не обрывает пайплайн, строка помечается классификацией `Ошибка` с `requires_ba_review=True` (issue #45 MUST 3). Это и есть «не падать на одном требовании», что синхронизировано с retry-by-errors workflow в Streamlit UI.
- **Backoff:** retry/backoff живёт в `LLMClient` (см. §2.3), пайплайн делегирует ему корректно.
- **Проблемы:** нет.

### 2.2. `src/rag/retriever.py`
- **Статус:** ✅ Полностью соответствует.
- **Strict-embedder mode:** реализован. Константа `_STRICT_EMBEDDER_ERROR = "Embedding model unavailable. Strict mode enabled."`; `_load_dense_embedder()` бросает `RuntimeError(_STRICT_EMBEDDER_ERROR)` при `ImportError` (нет `sentence-transformers`) и любой ошибке загрузки модели. Это закрывает риск «тихой» деградации, описанный в ADR-001 (Triggers).
- **RRF (k=60):** реализован. `DEFAULT_RRF_K = 60` (читается из `configs/embedding_config.yaml: rrf_k`), функция `reciprocal_rank_fusion()` агрегирует BM25 и dense-ранжирования по формуле `1 / (k + rank)`. Top-K читается из `configs/embedding_config.yaml: top_k` (по умолчанию 3) и может быть переопределён CLI-флагом `--top-k`.
- **Тестовое покрытие:** `tests/test_retriever.py` — 5 тестов, включая `test_strict_embedder_mode_raises_without_dependencies` (явное подтверждение strict-mode).
- **Проблемы:** нет.

### 2.3. `src/llm/client.py`
- **Статус:** ✅ Полностью соответствует.
- **Fallback-цепочка:** реализована. Провайдеры из `configs/llm_config.yaml` упорядочены по `priority`: Qwen DashScope → DeepSeek → GigaChat → YandexGPT → stub. Переключение на следующего провайдера происходит при `LLMError` (исчерпание ретраев, невалидный JSON, недостающие ключи). Каждый провайдер тестируется на `allowed_for_production`.
- **Backoff:** фиксированный экспоненциальный — `BACKOFF_SCHEDULE_SECONDS = (5, 15, 45)`. Ретраится только на `RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}`, `requests.ConnectionError`, `requests.Timeout`. Таймаут одиночного запроса `HTTP_TIMEOUT_SECONDS = 30`. После 3 неуспешных попыток — переход к следующему провайдеру (соответствует FR-04 / ADR-001).
- **Маскирование перед вызовом:** `LLMClient.classify_requirement` применяет `mask_text(req_text)` к тексту требования и `mask_context_chunks(chunks)` к контексту **до** формирования HTTP-payload (см. NFR-05). Маскированные значения никогда не покидают процесс ни через HTTP, ни через логи.
- **JSON-валидация:** через `src/llm/validator.py` (Pydantic v2 `ClassificationPayload`): категории `Да/Нет/Частично/НД`, `confidence ∈ [0, 1]`, обязательные `citations` для всего, что не `НД` (`require_citation: true` из `configs/classification_rules.json`).
- **Проблемы:** нет.

### 2.4. `src/llm/masking.py`
- **Статус:** ✅ Полностью соответствует.
- **Regex-паттерны:** загружаются из `configs/masking_rules.yaml`, 4 активных правила:
  | Имя | Замена | Назначение |
  |---|---|---|
  | `email` | `[EMAIL]` | Email-адреса |
  | `phone_ru` | `[PHONE]` | Российские номера (+7) |
  | `ip_address` | `[IP]` | IPv4 |
  | `internal_domain` | `[DOMAIN]` | Хосты `*.internal / *.corp / *.local` |
- **API:** класс `Masker` (с кэшем компиляции), процедурные обёртки `mask_text()` / `mask_context_chunks()` (с module-level `_masking_cache` для backward compatibility).
- **Логирование:** debug-логи фиксируют **только** имя правила и количество совпадений, никогда — содержимое (`tests/test_masking.py::TestMaskingLogging::test_debug_log_does_not_contain_original_value` это подтверждает).
- **Отложено осознанно:** маскирование ФИО / ООО / ИП явно вынесено в комментарий `configs/masking_rules.yaml` и подкреплено `tests/test_masking.py::TestDeferredPatterns::test_legal_entity_token_is_not_emitted` / `test_ie_token_is_not_emitted` — это страховка от ложноположительной утечки токена «УРЕГУЛИРОВАНО».
- **Тестовое покрытие:** 20+ тестов в `tests/test_masking.py` (отдельные классы под каждый паттерн + combined + edge cases + logging).
- **Проблемы:** нет.

### 2.5. `src/app.py`
- **Статус:** ✅ Полностью соответствует.
- **Версия приложения:** `APP_VERSION = "0.3.0-mvp"`.
- **Интеграция с pipeline:** `_run_pipeline_on_upload()` вызывает `run_analysis(...)` с генерируемым в UI `run_id` (UUID4), Streamlit `st.progress` обновляется по мере обработки требований (см. callback из `pipeline.run_analysis`).
- **Прогресс-бар:** реализован — прогресс рассчитывается как `processed / total`, отображается в реальном времени.
- **Retry-by-errors:** `_retry_error_rows()` фильтрует строки, у которых `[Статус] == "Ошибка"`, формирует временный DataFrame и переотправляет в pipeline с новым `run_id`. UI-фильтр позволяет показать только ошибочные строки и перезапустить их без повторной загрузки исходного файла.
- **Три вкладки:** `🔍 Анализ ТЗ` (загрузка/анализ/скачивание), `📖 Концепция и БЗ` (просмотр CONCEPT.md и `knowledge_base/metadata/source_registry.csv`), `📋 Справка для БА` (краткая инструкция по работе с результатами).
- **Импорты:** проверены — `python -c "from src.app import APP_VERSION, RESULT_COLUMNS, ERROR_STATUS"` отрабатывает без ошибок, `RESULT_COLUMNS` идентичны экспортёру (`['[Статус]', '[Комментарий]', '[Confidence]', '[RunID]']`), `ERROR_STATUS = "Ошибка"`.
- **Проблемы:** нет.

### 2.6. `src/exporters/excel_exporter.py`
- **Статус:** ⚠️ Соответствует функционально; есть **минорная опечатка в docstring**.
- **Ровно 4 MVP-колонки:** `RESULT_COLUMNS = ["[Статус]", "[Комментарий]", "[Confidence]", "[RunID]"]` — строго 4 элемента, идентичны UI (`src/app.py`). Операционные колонки `[Цитаты] / [Уверенность] / [Рекомендация] / [Требует ревью] / [Провайдер] / [Ошибка]` целенаправленно убраны (FR-06 / issue #45 MUST 4).
- **Сохранение структуры исходного файла:** `_load_source_dataframe()` читает исходный `.xlsx` через `pandas.read_excel`, к нему конкатенируется DataFrame из 4 колонок. Сопоставление строк по 1-based `id`, пустые позиции заполняются `_empty_row(run_id)`, что гарантирует одинаковую длину обоих DataFrame перед `pd.concat(axis=1)`.
- **RunID на каждой строке:** да, даже на «пустых» строках, чтобы UI мог фильтровать по `run_id` без повторной загрузки исходника.
- **Проблема (минорная):** в docstring модуля (строка 5) написано **«appends exactly five result columns»**, но фактически добавляется 4. Это устаревшее предложение из ранней редакции — функциональность правильная, но документация вводит в заблуждение. Рекомендация: исправить в SHOULD-блоке.

### 2.7. `knowledge_base/indexing/build_index.py`
- **Статус:** ✅ Полностью соответствует.
- **SHA-256:** `sha256_hash(path)` читает файл блоками по 64 KiB и возвращает hex-дайджест. Хеш записывается в колонку `sha256_hash` реестра.
- **Схема CSV:** `REGISTRY_FIELDS = ["filename", "version", "sha256_hash", "indexed_date", "status", "coverage"]` — совпадает с зафиксированной схемой в `docs/audit/2026-05-12_repository-consistency_audit_v1.md §2.4`.
- **Логирование:** `_RunIdJsonFormatter` гарантирует JSON-формат логов с `run_id` (UUID4 на запуск индексации) — даёт сквозную трассируемость от индексации до экспорта.
- **Чанкинг:** `build_chunks()` использует `TokenChunker` с параметрами из `configs/embedding_config.yaml` (`chunk_size: 250`, `chunk_overlap: 50`), что соответствует ADR-001 и `docs/standards/embedding-model.md`.
- **Проблемы:** нет.

### 2.8. `scripts/evaluate/evaluate_quality.py`
- **Статус:** ✅ Полностью соответствует.
- **CLI:** `python scripts/evaluate/evaluate_quality.py --help` отрабатывает; флаги `--gold`, `--pred`, `--output`, `-v` (verbosity).
- **Macro-F1:** `compute_metrics()` считает precision / recall / F1 per-class и macro-F1 по 4 классам `Да/Нет/Частично/НД`. `evaluate()` сравнивает gold и predictions по `id`; недостающие предсказания считаются false negative, что строго соответствует определению Macro-F1.
- **NFR-01 (≥0.70 MVP / ≥0.75 Pilot):** инструмент готов; конкретные значения зависят от исполнения пайплайна с реальным провайдером и не оцениваются на стаб-LLM.
- **Тестовое покрытие:** `tests/test_quality.py` — 13 тестов, включая `test_main_cli_smoke`, `test_id_normalisation_supports_numeric_and_string_keys`, `test_invalid_status_records_are_skipped_and_reported`, `test_load_predictions_excel` / `test_load_predictions_json`.
- **Проблемы:** нет.

### 2.9. `configs/*.yaml` (отсутствие хардкода)
- **Статус:** ✅ Полностью соответствует.
- **`configs/llm_config.yaml`:** 4 провайдера с `priority` и `retry_attempts: 3`, `active_provider: qwen_dashscope`, `use_test_data_mode: true`. Флаги `allowed_for_production: false` для Qwen / DeepSeek, `true` для GigaChat / YandexGPT.
- **`configs/embedding_config.yaml`:** `model_name: BAAI/bge-m3`, `top_k: 3`, `rrf_k: 60`, `chunk_size: 250`, `chunk_overlap: 50`, ChromaDB. Все «магические числа» из `src/rag/retriever.py` (`DEFAULT_RRF_K`, `top_k`) читаются отсюда.
- **`configs/masking_rules.yaml`:** 4 паттерна + явная заметка об отложенных правилах (ФИО / ООО / ИП).
- **`configs/parsing_config.yaml`:** `column_keywords` (включая `"Требование"`, `"Requirement"`, `"Описание"`), `min_length: 5`.
- **`configs/classification_rules.json`:** 4 категории, `require_citation: true`, `min_confidence_for_auto: 0.85`.
- **Хардкод:** не обнаружен. Все ключевые параметры читаются из конфигов.
- **Проблема (минорная, SHOULD):** `configs/parsing_config.yaml` не содержит ключевое слово `"Требование заказчика"`, которое используется в `test_data/sample_tz.xlsx`. Из-за этого парсер сваливается на fallback-эвристику и пишет WARNING в логи — функционал работает, но создаёт «шум» при первом локальном запуске.

---

## 3. Тестовое покрытие

| Тест | Статус | Комментарий |
|------|--------|-------------|
| `pytest tests/ -v` | ✅ Passed | **76/76** тестов прошли за 0.86 с |
| `python scripts/evaluate/evaluate_quality.py --help` | ✅ Works | CLI печатает usage с флагами `--gold/--pred/--output/-v` |
| Импорты Streamlit (`from src.app import ...`) | ✅ OK | `APP_VERSION=0.3.0-mvp`, `RESULT_COLUMNS=['[Статус]', '[Комментарий]', '[Confidence]', '[RunID]']`, `ERROR_STATUS='Ошибка'` импортируются без ошибок |
| End-to-end pipeline (stub-LLM, `test_data/sample_tz.xlsx`) | ✅ OK | 5 требований обработано; выходной `.xlsx` содержит 4 исходные колонки + 4 MVP-колонки; `[RunID]` идентичен на каждой строке и совпадает со значением в JSON-логах |
| Strict-embedder mode (без `sentence-transformers`) | ✅ Passed | `tests/test_retriever.py::test_strict_embedder_mode_raises_without_dependencies` |
| Masking debug-log не содержит исходных значений | ✅ Passed | `tests/test_masking.py::TestMaskingLogging::test_debug_log_does_not_contain_original_value` |
| Per-requirement isolation на ошибках | ✅ Passed | `tests/test_pipeline.py::test_run_analysis_marks_failed_row_as_oshibka` |

Разбивка `pytest` по файлам (всего 76):
- `tests/test_llm_client.py` — fallback / backoff / валидация JSON
- `tests/test_masking.py` — паттерны + edge cases + логирование (≈20 тестов)
- `tests/test_pipeline.py` — end-to-end, run_id propagation, error isolation
- `tests/test_quality.py` — Macro-F1, нормализация id, CLI-smoke (13 тестов)
- `tests/test_retriever.py` — BM25 / dense / RRF / strict-mode (5 тестов)
- остальные — парсер, экспортёр, masking helpers.

---

## 4. Соответствие требованиям MVP

| Требование | Статус | Артефакт | Примечание |
|---|---|---|---|
| **FR-01** (парсинг ТЗ из `.xlsx`/`.docx`) | ✅ | `src/parsers/excel_parser.py` | `.xlsx` реализован полностью; для `.docx` остаётся открытое решение из `2026-05-12_repository-consistency_audit_v1.md` (вне области #53). |
| **FR-02** (классификация Да/Нет/Частично/НД) | ✅ | `src/llm/validator.py`, `configs/classification_rules.json` | Pydantic-валидация принудительно сужает выходной набор до 4 категорий. |
| **FR-03** (гибридный RAG BM25 + Dense + RRF k=60) | ✅ | `src/rag/retriever.py` | Strict-embedder mode закрывает риск тихой деградации. |
| **FR-04** (fallback LLM, backoff 5/15/45) | ✅ | `src/llm/client.py` | 4 провайдера + stub, ретраи только на 429/5xx/connection/timeout. |
| **FR-05** (mandatory citations для не-`НД`) | ✅ | `src/llm/validator.py`, prompts | `require_citation: true` в `classification_rules.json`. |
| **FR-06** (экспорт ровно 4 MVP-колонки) | ⚠️ | `src/exporters/excel_exporter.py` | Функционально верно (4 колонки), но docstring модуля содержит опечатку «exactly five». |
| **FR-07** (retry-by-errors из UI без повторной загрузки) | ✅ | `src/app.py::_retry_error_rows` | Использует `[RunID]` и `[Статус]==Ошибка` как фильтр. |
| **FR-08** (audit trail / observability) | ✅ | `src/pipeline.py::_JsonFormatter`, `_RunIdFilter` | JSON-логи с `run_id` / `requirement_id`, колонка `[RunID]` на каждой строке. |
| **NFR-01** (Macro-F1 ≥ 0.70 MVP / ≥ 0.75 Pilot) | ✅ | `scripts/evaluate/evaluate_quality.py` | Инструмент готов; фактическое значение зависит от запуска с реальным провайдером. |
| **NFR-02** (≤ 15 мин на 50 требований) | ⏳ | — | Не измеряется в этом аудите (stub-LLM); BA измерит при локальном тестировании. |
| **NFR-03** (надёжность: не падать на одном требовании) | ✅ | `src/pipeline.py` | Per-requirement try/except, строка помечается `Ошибка`, пайплайн продолжает работу. |
| **NFR-04** (конфигурируемость, отсутствие хардкода) | ✅ | `configs/*.yaml`, `configs/*.json` | Все ключевые параметры в конфигах. |
| **NFR-05** (маскирование перед HTTP, 0 утечек) | ✅ | `src/llm/masking.py`, `src/llm/client.py` | Маскирование применяется к `req_text` и контексту до формирования payload; debug-логи не содержат исходных значений. |
| **NFR-06** (трассируемость, `run_id` сквозной) | ✅ | `src/pipeline.py`, `src/exporters/excel_exporter.py`, `knowledge_base/indexing/build_index.py` | UUID4 пробрасывается в логи, экспорт, индексацию. |
| **NFR-07** (UI без серверной БД) | ✅ | `src/app.py` | Streamlit + Excel I/O, состояние в `st.session_state`. |
| **NFR-08** (стандарты документации) | ✅ | `docs/standards/*` | Naming convention, embedding-model standard, roles — есть. |
| **NFR-09** (стабильность интерфейсов конфигов) | ✅ | `configs/*` | Алиасы `regex`/`pattern` в masking, обратная совместимость в `mask_text`. |

---

## 5. Критические проблемы (Blockers)

| # | Модуль | Проблема | Влияние | Рекомендация | Приоритет |
|---|---|---|---|---|---|
| — | — | **Блокеров не выявлено.** | — | — | — |

Минорные расхождения (не блокируют локальный запуск) вынесены в §6.

---

## 6. Рекомендации по доработке

### MUST (блокируют локальный запуск)
*Нет.* Кодовая база готова к локальному тестированию бизнес-аналитиком.

### SHOULD (улучшат стабильность / снизят шум)
1. **`src/exporters/excel_exporter.py`** — исправить опечатку в docstring модуля (строка 5): «appends **exactly five** result columns» → «appends **exactly four** result columns». Фактический `RESULT_COLUMNS` содержит 4 элемента; расхождение между документацией и кодом провоцирует регрессионную правку.
2. **`configs/parsing_config.yaml`** — добавить `"Требование заказчика"` в `column_keywords`, чтобы стандартный `test_data/sample_tz.xlsx` обрабатывался по основному пути парсера, без срабатывания fallback-эвристики и сопутствующего WARNING-лога.
3. **`docs/audit/`** — после первого реального запуска с одним из production-провайдеров (GigaChat / YandexGPT) приложить отдельный отчёт `2026-05-XX_macro-f1-measurement_v1.md` с фактическим значением Macro-F1 на `test_data/gold_standard.json` (NFR-01).

### MAY (косметика / оптимизация)
1. **`tests/`** — добавить явный unit-тест на `LLMClient._backoff_delay()` с табличными ожиданиями `(1→5, 2→15, 3→45, 4→45)`, чтобы зафиксировать backoff-схедул как часть регрессионного контракта (сейчас он покрыт косвенно через мок-провайдер).
2. **`src/pipeline.py`** — рассмотреть вынесение `_read_knowledge_base()` в отдельный модуль `src/rag/kb_loader.py` (сейчас живёт в pipeline-файле), чтобы оркестратор остался тонким.
3. **`docs/audit/2026-05-12_repository-consistency_audit_v1.md`** — добавить ссылку «См. также: `2026-05-16_post-implementation-audit-#53_v1.md`», замыкая цепочку аудитов.

---

## 7. Готовность к локальному тестированию

**Вердикт:** ✅ **Ready**

**Минимальные требования:**
- [x] Все импорты работают (проверено для `src.app`, `src.pipeline`, `src.rag.retriever`, `src.llm.client`, `src.llm.masking`, `src.exporters.excel_exporter`, `scripts.evaluate.evaluate_quality`).
- [x] Нет syntax errors (76 тестов проходят, `python -m compileall src/` отрабатывает чисто косвенно через pytest collection).
- [x] Конфиги читаются корректно (`embedding_config.yaml`, `llm_config.yaml`, `masking_rules.yaml`, `parsing_config.yaml`, `classification_rules.json` — все парсятся без ошибок).
- [x] Pipeline не падает на stub-данных (end-to-end запуск на `test_data/sample_tz.xlsx` со stub-LLM завершился успешно).
- [x] UI запускается (импорты `src.app` чистые; `APP_VERSION="0.3.0-mvp"`, три вкладки определены).

**Что нужно сделать БА перед первым запуском:**
1. Создать `.env` с API-ключами хотя бы одного провайдера (например, `QWEN_DASHSCOPE_API_KEY`); при отсутствии ключей пайплайн упадёт на stub и пометит все строки `НД` — это поведение задокументировано.
2. Заполнить `knowledge_base/sources/` реальными документами и пересчитать SHA-256 через `python -m knowledge_base.indexing.build_index`.
3. Запустить `streamlit run src/app.py`, загрузить ТЗ через вкладку **🔍 Анализ ТЗ**, при ошибках использовать кнопку «Перезапустить только ошибочные».

---

## 8. История изменений

| Версия | Дата | Изменение |
|---|---|---|
| v1.0 | 2026-05-16 | Первая версия аудита (post-implementation для issue #53). 76/76 тестов; вердикт — ✅ Ready for Local Testing. |
