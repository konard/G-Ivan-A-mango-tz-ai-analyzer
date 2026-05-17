# Changelog

Все значимые изменения проекта `clarify-engine-ai` фиксируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### ⚠️ BREAKING CHANGE
- **BL-06 (issue #92): `chunk_size` поднят с 250 до 512, `chunk_overlap` — с 50 до 64.** Изменение размера окна меняет структуру индекса ChromaDB — после мерджа владелец задачи выполняет полный reindex (`python knowledge_base/indexing/build_index.py`) и прогоняет Golden Set (BL-05). Старая коллекция `clarify_engine_kb` несовместима с новыми параметрами; её необходимо пересоздать.

### Added
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

### Changed
- `configs/embedding_config.yaml` — `chunk_size: 512`, `chunk_overlap: 64`, `min_chunk_size: 384`, `max_chunk_size: 768`, новый флаг `section_aware_chunking: true` (BL-06, issue #92). См. ⚠️ BREAKING CHANGE выше.
- `src/rag/chunker.py` — `DEFAULT_CHUNK_SIZE = 512`, `DEFAULT_CHUNK_OVERLAP = 64`, `MIN_CHUNK_SIZE = 384`, `MAX_CHUNK_SIZE = 768`, добавлен section-aware splitter (вкл. по умолчанию); `TokenChunker.from_config` пробрасывает `section_aware_chunking` из YAML (BL-06, issue #92).
- `docs/standards/embedding-model.md` — обновлён до v1.2 (BL-06, issue #92): §5.1 актуализирован под L1-параметры 512/64 + section-aware, добавлена запись в §8 «История изменений».
- `docs/ADR/003-multi-agent-orchestration-draft.md` обновлён до **Concept (Review) v1.1** (issue #81): добавлены §2.1.1 контракт диспетчеризации очереди (`asyncio.Queue` / Redis Streams + `Semaphore` + backpressure), §2.4 единый event envelope, §2.5 контракт отказоустойчивости `Data-Enricher` (retry / DLQ / healthcheck `/ready` & `/live`, изоляция от online-пайплайна); §3.2 уточнена кластеризация Market-Analyst (`centroid_distance + min_cluster_size + manual_validation_threshold` вместо `cosine ≥ 0.95`); **новый §4 Security & Compliance** — prompt-injection mitigation, data-poisoning prevention, `sanitize_for_log()`, access control offline-агентов, mapping на ISO/IEC 23894 и NIST AI RMF; §7 расширен инфраструктурными триггерами (RAM ≥ 16 ГБ, CPU ≥ 4 cores, выделенная нода для offline-агентов); **новый §8 Trace & Observability** — additive-расширение FR-08 форматом `agent_trace` (`agent_id`, `step`, `input_hash`, `output_hash`, `latency_ms`, `attempt`, `outcome`). Статус документа остаётся `Concept`; кодовые изменения по-прежнему заблокированы до `Accepted`.
- Проект переименован: `mango-tz-ai-analyzer` → `clarify-engine-ai`. Удалены все упоминания `mango`, `Mango Office`, `MANGO`, `Манго` из кода, конфигов, тестов, промптов и документации; заменены на нейтральные термины (`internal_kb`, `product_docs`, «целевая платформа», `clarify_engine_kb`). Файл `knowledge_base/sources/mango_crm_integration.md` переименован в `crm_integration.md` (issue #59).
- `docs/CONCEPT.md` обновлён до версии 2.0 (issue #37): развёрнутая редакция SSoT-документа с согласованной структурой документации, детализированными FR-01..FR-08 и критериями приёмки, полным набором НФТ NFR-01..NFR-09, расширенной матрицей рисков R-01..R-09, Exit Criteria для MVP / Пилота / Масштабирования, глоссарием и реестром связанных документов.
- `requirements.txt` — раскомментированы `rank_bm25`, `chromadb`, `sentence-transformers`; добавлена инструкция установки `torch` (CPU) для облачных сред (issue #45 MUST 1).
- `src/llm/client.py` — экспоненциальный backoff `[5с, 15с, 45с]` для retriable-ошибок (timeout / 5xx / rate-limit), последовательные вызовы (issue #45 MUST 3).
- `src/pipeline.py` — на полный отказ строка помечается `[Статус: Ошибка]`, пайплайн продолжает обработку оставшихся требований (issue #45 MUST 3).
- `src/exporters/excel_exporter.py` — экспорт ограничен ровно четырьмя MVP-колонками `[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]` (issue #45 MUST 4).
- `src/app.py` — Streamlit UI вызывает реальный `run_analysis`, отображает прогресс и счётчики Успешно/Ошибки, кнопка «Повторить только ошибки» фильтрует строки по `RunID` без повторной загрузки файла; добавлена вкладка «Справка для БА» (issue #45 MUST 5).
- `src/rag/retriever.py` — Strict-Embedder Mode: при недоступной модели `RuntimeError("Embedding model unavailable. Strict mode enabled.")`, fallback на hash-эмбеддинг удалён (issue #45 MUST 2).
- `knowledge_base/indexing/build_index.py` — SHA-256 хеши, синхронизация с `source_registry.csv`, чанкинг через `src/rag/chunker.py` (issue #45 MUST 2).
- `configs/masking_rules.yaml` — оставлены только согласованные паттерны Email/Phone/IP/Domain; маски ФИО/юр.лиц/ИП отложены (issue #45 MUST 3).

### Removed
- `knowledge_base/indexing/chunk_config.yaml` — параметры чанкинга читаются только из `configs/embedding_config.yaml` (issue #45 MUST 2).
- **LLM fallback-цепочка упрощена до двух провайдеров — DeepSeek (приоритет 1, free tier) и GigaChat (приоритет 2, RU-резидентный).** Из `configs/llm_config.yaml`, `src/llm/client.py`, `.env.example`, документации (`README.md`, `docs/CONCEPT.md`, `docs/ADR/001-rag-architecture.md`) удалены провайдеры Qwen (DashScope) и YandexGPT, а также связанные с ними переменные окружения и колеры (issue #64).

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
