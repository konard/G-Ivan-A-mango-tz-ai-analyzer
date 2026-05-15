# Changelog

Все значимые изменения проекта `mango-tz-ai-analyzer` фиксируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md` — аудит согласованности репозитория, полноты документации и тестируемости требований (issue #21).
- `docs/analysis/2026-05-15_analysis_repo-state-and-mvp-recommendations_v1.md` — анализ состояния репозитория, оценка готовности MVP, профиль нагрузки и рекомендации по доработке кода, архитектуры и документации (issue #35).

### Changed
- `docs/CONCEPT.md` обновлён до версии 2.0 (issue #37): развёрнутая редакция SSoT-документа с согласованной структурой документации, детализированными FR-01..FR-08 и критериями приёмки, полным набором НФТ NFR-01..NFR-09, расширенной матрицей рисков R-01..R-09, Exit Criteria для MVP / Пилота / Масштабирования, глоссарием и реестром связанных документов.

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
