# Changelog

Все значимые изменения проекта `clarify-engine-ai` фиксируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- `.env.example` — шаблон переменных окружения с плейсхолдерами `DEEPSEEK_API_KEY`, `GIGACHAT_API_KEY`, `YANDEXGPT_API_KEY` и флагами `USE_TEST_DATA_MODE`, `STRICT_EMBEDDER` (issue #59).
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
