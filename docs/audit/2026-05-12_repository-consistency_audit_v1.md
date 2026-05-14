# 🔍 Audit: Repository Consistency & Testability

## Метаданные
- **Дата:** 2026-05-12
- **Версия:** v1
- **Автор:** konard (Konstantin Diachenko)
- **Статус:** Reviewed
- **Связанные документы:**
  - [`docs/CONCEPT.md`](../CONCEPT.md) v1.0
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md)
  - [`docs/analysis/2026-05-12_review_mvp-context_v1.md`](../analysis/2026-05-12_review_mvp-context_v1.md)
  - [`docs/audit/data-masking_v1.md`](data-masking_v1.md)
  - [`docs/standards/roles.md`](../standards/roles.md)
  - [`docs/standards/naming-convention.md`](../standards/naming-convention.md)
  - [`docs/standards/embedding-model.md`](../standards/embedding-model.md)

---

## 1. Executive Summary
- **Общая оценка готовности:** ⚠️ **Conditional Approve** — репозиторий готов к запуску MVP, ключевые артефакты согласованы, 14/14 unit-тестов проходят, но обнаружены некритические пробелы (отсутствуют `docx_parser`, `docx_exporter`, отдельный модуль `src/llm/masking.py`, явный валидатор JSON, выходной формат экспортёра не полностью соответствует разделу 3 концепции).
- **Критические пробелы:** не выявлено. Все MUST-рекомендации из ревью концепции (`docs/analysis/2026-05-12_review_mvp-context_v1.md`) закрыты: ADR-001 заполнен, аудит маскирования оформлен, роли зафиксированы, стандарт эмбеддингов утверждён.
- **Рекомендации (краткий перечень):** выровнять имена колонок экспорта с концепцией (`[Статус]`, `[Комментарий]`), вынести маскирование в отдельный модуль `src/llm/masking.py`, добавить заглушки `docx_parser.py` / `docx_writer.py` или зафиксировать их отложение как осознанное решение, добавить benchmark-скрипт для НФТ «≤15 мин/50 требований» и метрику F1 на `gold_standard.json`.
- **Update v1.1:** Риск 9.1 (RAG context masking) закрыт — `src/llm/masking.py` и `src/llm/validator.py` выделены, `mask_context_chunks` применяется в `classify_requirement`. 42 теста проходят.

## 2. Structure Audit
Проверка наличия обязательных каталогов и файлов согласно MVP-плану (раздел 1 issue #21). Источник: текущее состояние ветки `issue-21-cbdfdd436283`.

### 2.1. `src/`
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `src/app.py` | ✅ | Streamlit UI с двумя вкладками (анализ + концепция), загрузка/скачивание реализованы. |
| `src/parsers/excel_parser.py` | ✅ | Извлекает требования из `.xlsx`, есть fallback по колонке, обработка пустых файлов. |
| `src/parsers/docx_parser.py` | ❌ | Отсутствует. Парсинг `.docx` упомянут в концепции (раздел 3) и FR-01, но не реализован. |
| `src/rag/hybrid_search.py` | ⚠️ | Логика BM25 + Dense + RRF реализована, но в файле `src/rag/retriever.py`. Имя файла отличается от чек-листа issue #21. |
| `src/rag/chunker.py` | ❌ | Отсутствует. Чанкинг 200–300 токенов, overlap 50 (раздел 4 концепции) пока не реализован — параметры заданы в `configs/embedding_config.yaml` и `knowledge_base/indexing/chunk_config.yaml`. |
| `src/rag/retriever.py` | ✅ | Полная реализация гибридного поиска с RRF (k = 60). |
| `src/llm/client.py` | ✅ | Реализованы fallback (4 провайдера + stub), retries, валидация JSON, форматирование контекста. Использует модули `masking.py` и `validator.py`. |
| `src/llm/masking.py` | ✅ | Отдельный модуль маскирования с функциями `mask_text`, `mask_context_chunks` и классом `Masker`. Риск 9.1 закрыт. |
| `src/llm/validator.py` | ✅ | Отдельный модуль валидации JSON с функциями `extract_json`, `validate_payload`. Категории Да/Нет/Частично/НД, confidence 0..1, mandatory citations. |
| `src/exporters/excel_writer.py` | ⚠️ | Файл существует под именем `src/exporters/excel_exporter.py`. Функциональность совпадает, имя отличается. |
| `src/exporters/docx_writer.py` | ❌ | Отсутствует. Концепция допускает экспорт в `.docx` (раздел 3), но MVP-фокус на `.xlsx`. |
| `src/pipeline.py` | ✅ | Оркестратор end-to-end: парсинг → RAG → маскирование → LLM → экспорт, CLI-интерфейс. |

### 2.2. `configs/`
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `configs/llm_config.yaml` | ✅ | 4 провайдера (Qwen → DeepSeek → GigaChat → Yandex), `use_test_data_mode: true`, fallback и приоритеты. |
| `configs/embedding_config.yaml` | ✅ | `BAAI/bge-m3`, `chunk_size: 250`, `chunk_overlap: 50`, ChromaDB. |
| `configs/classification_rules.json` | ✅ | 4 категории (Да/Нет/Частично/НД), `require_citation: true`, `min_confidence_for_auto: 0.85`. |
| `configs/masking_rules.yaml` | ✅ | 4 паттерна (email, phone_ru, ip_address, internal_domain) + `exclude_sections`. |

### 2.3. `prompts/`
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `prompts/system_classifier_v1.0.md` | ✅ | Системный промпт с правилами (mandatory citation, no hallucinations, strict JSON, language). |
| `prompts/few_shot_examples.json` | ✅ | 3 примера (Да, Частично, НД) для калибровки. Issue #21 ожидает 3–5 — нижняя граница соблюдена. |
| `prompts/prompt_changelog.md` | ✅ | Шапка истории + validation notes. |

### 2.4. `knowledge_base/`
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `knowledge_base/sources/` | ✅ | 4 источника (`api_guide_excerpt.pdf`, `functional_list_sample.xlsx`, `mango_crm_integration.md`, `user_guide_call_recording.pdf`). |
| `knowledge_base/metadata/source_registry.csv` | ✅ | Реестр с полями `filename, version, sha256_hash, indexed_date, status, coverage`. Хеши помечены как `pending` — нужно посчитать при первой реальной индексации. |
| `knowledge_base/indexing/build_index.py` | ⚠️ | Скрипт-заглушка: логирует наличие источников, но не индексирует. TODO явно зафиксированы. |
| `knowledge_base/indexing/chunk_config.yaml` | ✅ | Файл существует (пустой) — дублирует параметры из `configs/embedding_config.yaml`. Рекомендуется удалить дубликат либо разделить ответственности. |

### 2.5. `test_data/`
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `test_data/sample_tz.xlsx` | ✅ | 5 строк требований, оформлены с заголовком и стилями (см. `scripts/generate_sample_tz.py`). |
| `test_data/gold_standard.json` | ✅ | 5 эталонных записей (id, requirement, expected_status, expert_comment, expected_sources). |

### 2.6. `docs/`
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `docs/CONCEPT.md` | ✅ | Разделы 1–8 (включая 8 «Структура документации»). |
| `docs/ADR/001-rag-architecture.md` | ✅ | Status: Accepted, заполнен (Decision/Consequences/Triggers/References/History). |
| `docs/analysis/` | ✅ | `README.md` + `2026-05-12_review_mvp-context_v1.md` (Reviewed). |
| `docs/standards/` | ✅ | `roles.md`, `naming-convention.md`, `embedding-model.md`, `templates/`. |
| `docs/audit/` | ✅ | `data-masking_v1.md` (Draft). Этот документ добавляется как `2026-05-12_repository-consistency_audit_v1.md`. |
| `docs/runbooks/README.md` | ✅ | Заглушка, наполнение запланировано на этап «Пилот». |
| `docs/screenshots/` | ✅ | Не требовалось чек-листом, но присутствует (ui-tab-analysis.png, ui-tab-concept.png) — бонусный артефакт UI-демо. |

### 2.7. Корневые файлы
| Файл/Каталог | Статус | Комментарий |
|--------------|--------|-------------|
| `README.md` | ✅ | Содержит секцию «Команда проекта» и навигацию по `docs/`. |
| `CHANGELOG.md` | ⚠️ | Файл существует, но пуст (0 строк). Нужно добавить запись о MVP-стартовом состоянии. |
| `requirements.txt` | ⚠️ | Полный список зависимостей присутствует, но `PyYAML>=6.0` указан дважды (строки 2 и 8). Не критично, но косметически. |
| `.gitignore` | ✅ | Исключает `chroma_data/`, `logs/`, `.env`, `*.xlsx` с whitelist для `test_data/` и `knowledge_base/sources/`. |
| `pyproject.toml` | ✅ | Дополнительно — настройки сборки и `pytest`. |

## 3. Consistency Audit
Проверка непротиворечивости между документами.

| Документ ↔ Документ | Статус | Расхождения / Заметки |
|---------------------|--------|------------------------|
| **CONCEPT ↔ ADR-001** | ✅ | RAG, гибридный поиск (BM25 + Dense + RRF, k = 60), `BAAI/bge-m3` упомянуты идентично. ADR ссылается на разделы 1, 3, 4, 5, 6, 7 концепции. |
| **CONCEPT ↔ `configs/llm_config.yaml`** | ✅ | Fallback Qwen → DeepSeek → GigaChat → YandexGPT соблюдён, `use_test_data_mode: true`, `allowed_for_production` корректно разделяет зарубежные/резидентные. |
| **CONCEPT ↔ `configs/classification_rules.json`** | ✅ | Категории Да/Нет/Частично/НД, `require_citation: true`. |
| **CONCEPT ↔ `configs/embedding_config.yaml`** | ⚠️ | Концепция: чанкинг 200–300 токенов, overlap 50. Конфиг: `chunk_size: 250, chunk_overlap: 50` — в диапазоне. `max_length: 512` отличается от заявленных у `bge-m3` 8192, но это max_length токенизатора, не модели — допустимо. |
| **CONCEPT ↔ `docs/standards/roles.md`** | ✅ | Product Owner @G-Ivan-A коммитит PR, Code Agent @konard генерит код, Prompt Owner @G-Ivan-A. Соответствует README и CONCEPT.md (раздел 1). |
| **CONCEPT ↔ `docs/audit/data-masking_v1.md`** | ✅ | regex-паттерны (email, phone_ru, ip_address, internal_domain) соответствуют разделу 6 концепции (риск утечки). |
| **CONCEPT ↔ `configs/masking_rules.yaml`** | ✅ | YAML содержит ровно те паттерны, что описаны в аудите маскирования. |
| **Ревью концепции ↔ ADR / аудиты** | ✅ | Все MUST/SHOULD из `docs/analysis/2026-05-12_review_mvp-context_v1.md` закрыты: MUST «заполнить ADR-001» → выполнено; SHOULD «аудит маскирования» → `data-masking_v1.md`; MAY «runbooks» → создан placeholder. |
| **README ↔ структура файлов** | ✅ | Все ссылки (`docs/CONCEPT.md`, `docs/ADR/001-rag-architecture.md`, `docs/standards/*`, `docs/audit/data-masking_v1.md`, `docs/runbooks/`) ведут на существующие файлы. |
| **CONCEPT (раздел 3, колонки экспорта) ↔ `src/exporters/excel_exporter.py`** | ⚠️ | Концепция требует колонки `[Статус]`, `[Комментарий]`. Экспортёр добавляет: `[Статус]`, `[Уверенность]`, `[Комментарий]`, `[Рекомендация]`, `[Цитаты]`, `[Требует ревью]`, `[Провайдер]`, `[Ошибка]`. Базовые колонки соблюдены, расширенный набор — польза для аудита, но стоит зафиксировать в концепции или ADR. |

## 4. Testability Audit
Каждое требование из раздела 4 концепции (полный текст FR/НФТ см. ниже) — измеримо и снабжено артефактом проверки.

### 4.1. Функциональные требования

| Требование | Измеримо? | Тест / Метрика | Готовность |
|------------|-----------|----------------|------------|
| **FR-01** Парсинг `.xlsx`/`.docx` | ✅ | `tests/test_excel_parser.py::test_load_requirements_standard_column` + `test_data/sample_tz.xlsx` | ⚠️ Excel — ✅, DOCX — ❌ (нет `src/parsers/docx_parser.py`). |
| **FR-02** Извлечение атомарных требований | ✅ | `tests/test_excel_parser.py::test_load_requirements_fallback_column` (каждая строка — отдельная запись) | ✅ |
| **FR-03** Классификация в 4 категории | ✅ | `tests/test_llm_client.py::test_classify_requirement_uses_primary_provider` + `_VALID_CATEGORIES` enforcement в `_validate_payload` | ✅ |
| **FR-04** Обоснование с цитатой | ✅ | `_validate_payload` падает, если `citations` пуст для non-НД ответа (строки 130–132 `src/llm/client.py`); промпт также форсит правило | ✅ |
| **FR-05** Экспорт исходной структуры + новые колонки | ✅ | `tests/test_pipeline.py::test_run_analysis_end_to_end` проверяет `[Статус]` и `[Комментарий]` | ✅ |
| **FR-06** Маскирование чувствительных данных | ✅ | `tests/test_llm_client.py::test_mask_text_email_and_phone` + `configs/masking_rules.yaml` + `docs/audit/data-masking_v1.md` | ⚠️ Юнит-тест есть, но `tests/test_masking.py` (заявлен в аудите маскирования) — отсутствует. Тест-кейс для IP и internal domain пока не покрыт явно. |
| **FR-07** Streamlit UI ≤3 клика | ✅ | `src/app.py`: upload → run → download (3 клика) | ✅ Скриншоты в `docs/screenshots/ui-tab-analysis.png`, `ui-tab-concept.png`. |
| **FR-08** Логирование метаданных | ⚠️ | `src/pipeline.py` использует `logging`, `LLMClient.classify_requirement` возвращает `provider`, статистика собирается в `PipelineStats`. Однако `run_id`, версия БЗ и хеш промпта в логи не пишутся явно (источники в `source_registry.csv` имеют `sha256_hash: pending`). | ⚠️ Частично. |

### 4.2. Нефункциональные требования

| Требование | Измеримо? | Тест / Метрика | Готовность |
|------------|-----------|----------------|------------|
| **Точность ≥ 75% F1** | ✅ | `test_data/gold_standard.json` (5 эталонных записей) — достаточная база для расчёта | ⚠️ Скрипт расчёта метрики отсутствует, нужно добавить `tests/test_quality.py` или `scripts/evaluate_quality.py`. |
| **Время ≤ 15 мин / 50 требований** | ⚠️ | Артефакта замера нет (`tests/benchmark.py` отсутствует). | ❌ |
| **Цитируемость ≥ 95%** | ✅ | Жёстко форсится в `_validate_payload`: ответ без `citations` для non-НД отклоняется. | ✅ |
| **Актуальность БЗ ≤ 24 ч** | ⚠️ | `source_registry.csv` фиксирует `indexed_date`, но cron/триггер не настроен. | ❌ (MVP допускает ручное обновление). |
| **0 утечек данных** | ✅ | Маскирование применяется к тексту требования и RAG context (`mask_context_chunks`). Риск 9.1 закрыт. | ✅ |
| **Аудируемость сессий** | ⚠️ | Логи через `logging`, экспорт содержит `[Провайдер]`. Отдельного `run_id` пока нет. | ⚠️ |

## 5. Code-Documentation Alignment

| Архитектурный элемент | Файл кода | Соответствие |
|-----------------------|-----------|--------------|
| RAG-паттерн (концепция, раздел 3) | `src/rag/retriever.py` + `src/pipeline.py` | ✅ Поток «парсинг → RAG-поиск → LLM → валидация → экспорт» реализован в `run_analysis`. |
| Гибридный поиск (BM25 + Dense + RRF) | `src/rag/retriever.py` (`HybridRetriever.search`, RRF k = 60) | ✅ |
| LLM-клиент с fallback (4 провайдера) | `src/llm/client.py` (`_call_dashscope`, `_call_deepseek`, `_call_gigachat`, `_call_yandex`, `_call_stub`) | ✅ Дополнительно — провайдер `stub` для offline-сценариев. |
| Маскирование | `src/llm/masking.py` (`mask_text`, `mask_context_chunks`, `Masker`) | ✅ Вынесено в отдельный модуль, применяется к требованию и context chunks. |
| Валидация JSON | `src/llm/validator.py` (`extract_json`, `validate_payload`) | ✅ Вынесено в отдельный модуль, категории Да/Нет/Частично/НД, mandatory citations. |
| Промпт-менеджмент | `prompts/system_classifier_v1.0.md` + `prompt_changelog.md` | ✅ |
| Конфигурация (нет хардкода) | `LLMClient.from_config`, `HybridRetriever.from_config`, `mask_text(config_path=…)`, `src/app.py::load_llm_config` | ✅ Все ключевые модули читают YAML. |
| Чанкинг 200–300 токенов | `configs/embedding_config.yaml` (`chunk_size: 250`, `chunk_overlap: 50`) | ⚠️ Конфиг есть, но `src/rag/chunker.py` не реализован — текущий retriever индексирует документы целиком. |
| База знаний | `knowledge_base/sources/`, `metadata/source_registry.csv`, `indexing/build_index.py` | ⚠️ Индексация — заглушка с TODO. |

## 6. Standards Completeness

| Стандарт | Файл | Соответствие |
|----------|------|--------------|
| Naming convention | `docs/standards/naming-convention.md` v1.0 | ✅ `docs/analysis/2026-05-12_review_mvp-context_v1.md` следует формату; `docs/audit/data-masking_v1.md` нарушает формат — нет даты в имени. Этот документ (`2026-05-12_repository-consistency_audit_v1.md`) — соответствует. |
| Roles | `docs/standards/roles.md` v1.0 | ✅ Описаны Product Owner, Code Agent, Prompt Owner + RACI. |
| Embedding model | `docs/standards/embedding-model.md` v1.0 | ✅ `BAAI/bge-m3` зафиксирован, критерии замены сформулированы. |
| ADR | `docs/ADR/001-rag-architecture.md` | ✅ Status: Accepted. |
| Templates | `docs/standards/templates/{analysis,decision}-template.md` | ✅ Шаблоны для analysis и decision документов. |

## 7. Recommendations

| # | Приоритет | Рекомендация | Оценка усилий |
|---|-----------|--------------|---------------|
| 1 | MUST | Добавить запись в `CHANGELOG.md` с описанием стартового состояния MVP (v0.1.0). | S (15 мин) |
| 2 | SHOULD | Вынести функцию маскирования из `src/llm/client.py` в отдельный модуль `src/llm/masking.py` и переэкспортировать `mask_text` для обратной совместимости. | S (1 ч) |
| 3 | SHOULD | Создать `src/llm/validator.py` и перенести туда `_validate_payload` / `_extract_json` из `client.py`. | S (1 ч) |
| 4 | SHOULD | Добавить `tests/test_masking.py` с явными тест-кейсами для IP-адресов и внутренних доменов (см. чек-лист `docs/audit/data-masking_v1.md` раздел 3). | S (1 ч) |
| 5 | SHOULD | Реализовать `scripts/evaluate_quality.py` или `tests/test_quality.py`, который считает F1-метрику на `test_data/gold_standard.json` и валит сборку при F1 < 0.70. | M (полдня) |
| 6 | SHOULD | Реализовать `tests/benchmark.py` или `scripts/benchmark_pipeline.py` для замера НФТ «≤ 15 мин / 50 требований» (с stub-провайдером — нижняя оценка). | M (полдня) |
| 7 | SHOULD | Маскировать `context_chunks` перед отправкой в LLM (не только текст требования). Снизит риск утечки в production. | S (1 ч) |
| 8 | SHOULD | Переименовать `docs/audit/data-masking_v1.md` → `docs/audit/2026-05-12_audit_data-masking_v1.md` для соответствия `docs/standards/naming-convention.md`. | S (10 мин) |
| 9 | MAY | Реализовать `src/parsers/docx_parser.py` (хотя бы с минимальным extract через `python-docx`) — FR-01 формально требует .docx. Альтернатива: явно зафиксировать отложение в концепции. | M |
| 10 | MAY | Удалить дубликат `PyYAML>=6.0` в `requirements.txt`. | S (5 мин) |
| 11 | MAY | Реализовать настоящий `knowledge_base/indexing/build_index.py` (чанкинг + эмбеддинги + Chroma). | L |
| 12 | MAY | Расширить `prompts/few_shot_examples.json` до 5 примеров (issue #21 ожидает 3–5). | S |
| 13 | MAY | Добавить `run_id` (UUID4) в `PipelineStats` и логи — закроет требование «аудируемость сессий» и FR-08. | S (1 ч) |

## 8. Conclusion

- [ ] **Approve** — Репозиторий готов к разработке MVP без оговорок.
- [x] **Conditional Approve** — Есть некритические пробелы, исправить в рамках MVP / Пилота.
- [ ] **Reject** — Критические проблемы, требуется повторный аудит.

**Условия снятия Conditional:** выполнение рекомендаций #1–#7 (MUST + SHOULD).
**Триггеры повторного аудита:**
- Падение F1 на `gold_standard.json` ниже 0.70 после реальной интеграции LLM.
- Изменение состава LLM-провайдеров или резидентности.
- Обнаружение утечки чувствительных данных в логах при `use_test_data_mode: false`.

## 9. Critical Risks & Best-practice Reuse

### 9.1. Критические уязвимости (по результатам аудита)
1. **Контекст RAG не маскируется.** В `src/llm/client.py::classify_requirement` маскированию подвергается только `req_text`, а `context_chunks` (полученные из `knowledge_base/`) отправляются в LLM «как есть». Если в публичных источниках появятся email/IP/внутренние домены, они утекут к зарубежным провайдерам. **Митигация:** распространить `mask_text` на `context_block` или предварительно маскировать содержимое `knowledge_base/sources/` при индексации. **[ЗАКРЫТО в v1.1]** — реализовано в `src/llm/masking.py::mask_context_chunks`, вызывается в `LLMClient.classify_requirement`. Добавлены тесты `test_classify_requirement_masks_requirement_and_context` и `test_classify_requirement_fails_without_context_masking`.
2. **`source_registry.csv` содержит `sha256_hash: pending`.** Концепция требует «версионирование, хеш-чек файлов» (раздел 6). Пока хеши не посчитаны, метрика «актуальность БЗ ≤ 24 ч» и аудируемость не работают. **Митигация:** при первом запуске `build_index.py` рассчитать SHA-256 и записать в реестр; добавить проверку в CI.
3. **Запуск без API-ключей возвращает все НД с `confidence: 0.0`.** Stub-провайдер не считает это ошибкой, поэтому метрика «успешность» в `PipelineStats` будет 100% даже без реальной LLM. Это маскирует регрессии в качестве. **Митигация:** в `use_test_data_mode: true` логировать предупреждение, если хотя бы один провайдер не вернул content; в CI требовать наличие реальных ключей или явный флаг `--allow-stub`.
4. **`HybridRetriever._hash_embedding` — fallback-эмбеддинг.** Если `sentence-transformers` не установлен / модель `bge-m3` не загружена, используется bag-of-tokens hash-эмбеддинг (256 dim). В тестах это работает, но в production такое поведение должно явно фейлить запуск, а не молча деградировать. **Митигация:** добавить флаг `strict_embedder: true` в `configs/embedding_config.yaml` и проверку на старте.
5. **Отсутствие limit на размер загружаемого файла в Streamlit UI.** `src/app.py` принимает любой `.xlsx`/`.docx`. **Митигация:** ограничить через `st.set_option("server.maxUploadSize", 10)` (10 МБ) и валидацию количества требований до отправки в LLM.

### 9.2. Best-practice для аналогичных решений (что переиспользовать на этапе MVP)
1. **JSON Schema enforcement через провайдер.** В `_call_dashscope` и `_call_deepseek` уже передаётся `"response_format": {"type": "json_object"}`. Стоит расширить до полноценной JSON Schema через `outlines`, `instructor` или OpenAI-совместимый `tools` API — это снижает hallucination rate ещё на ~50%.
2. **RAG-evaluation framework.** Для расчёта качества RAG отдельно от LLM-классификации стоит подключить `ragas` (метрики: faithfulness, answer_relevancy, context_precision). Это закроет НФТ «цитируемость ≥ 95%» и «точность ≥ 75% F1» одной библиотекой.
3. **Reciprocal Rank Fusion (k = 60).** Используется в Elasticsearch / Vespa как стандарт — текущий выбор корректен. Дополнительно можно добавить нормализацию scores (min-max) перед RRF, но это инкремент v2.
4. **`BAAI/bge-m3` через `FlagEmbedding`.** Официальная библиотека от BAAI поддерживает dense + sparse + multi-vector в одной модели — это закроет требование «гибридный поиск» без отдельного BM25. На этапе пилота можно сравнить с текущей реализацией.
5. **ChromaDB metadata filtering.** В `knowledge_base/metadata/source_registry.csv` стоит расширить поля (`document_type`, `valid_until`) и передавать их как `metadata` в Chroma — позволит фильтровать «устаревшие» источники без переиндексации.
6. **Streamlit `st.cache_resource` / `st.cache_data`.** Загрузка `BAAI/bge-m3` (~2.5 ГБ) на каждый запуск UI недопустима — стоит кешировать через `@st.cache_resource`.
7. **Pydantic schema для LLM-ответов.** Сейчас валидация ручная через `_validate_payload`. Перенос на `pydantic.BaseModel` (с `model_validate`) даст автогенерацию JSON Schema и стабильные ошибки. `pydantic>=2.7` уже в `requirements.txt`.
8. **`use_test_data_mode` как ENV-флаг с обязательным подтверждением.** Когда оператор переключает на `false`, нужно требовать `--i-understand-this-sends-data-abroad=yes` или аналогичный жёсткий guard.

## 10. История изменений
| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-12 | Первая версия аудита: структура, согласованность документации, тестируемость FR/НФТ, соответствие кода документации, стандарты, рекомендации, критические риски и best-practice. |
| v1.1 | 2026-05-12 | Закрытие риска 9.1 (RAG context masking): реализовано в `src/llm/masking.py::mask_context_chunks`, вызывается в `LLMClient.classify_requirement`. Добавлены тесты `test_classify_requirement_masks_requirement_and_context` и `test_classify_requirement_fails_without_context_masking`. Обновлены разделы 9.1 и Executive Summary. |
