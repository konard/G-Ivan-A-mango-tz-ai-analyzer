# Changelog

Все значимые изменения проекта `clarify-engine-ai` фиксируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

(сюда будут идти следующие изменения)

## [0.2.0] - 2026-05-18

### ⚠️ BREAKING CHANGES
- **BL-06** (#92): Переход на `chunk_size=512`, `chunk_overlap=64` и section-aware splitting. Требуется полная переиндексация базы знаний: удалить старую ChromaDB-коллекцию и выполнить `python knowledge_base/indexing/build_index.py`.

### Added
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
