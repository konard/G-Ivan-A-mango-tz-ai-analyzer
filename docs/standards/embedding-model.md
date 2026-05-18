# 🧮 Standard: Embedding Model

**Версия:** 1.5 | **Дата:** 2026-05-18 | **Статус:** Approved

---

## 1. Назначение
Документ фиксирует модель эмбеддингов, используемую в RAG-пайплайне `clarify-engine-ai` для MVP и Production, и условия её замены. Является стандартом-приложением к [ADR-001](../ADR/001-rag-architecture.md).

## 2. Current Model (MVP & Production)
- **Model:** `BAAI/bge-m3`
- **Dimensions:** 1024
- **Languages:** 100+ (including Russian)
- **Max Length:** 8192 tokens
- **Execution:** Local (CPU/GPU)
- **Data Residency:** ✅ Data stays within corporate boundary

## 3. Why Approved
- Top-3 quality on Russian language benchmarks.
- No fine-tuning required for MVP.
- Local execution → no data transfer to external providers.
- Meets IB/security requirements (раздел 6 концепции — управление рисками утечки).
- Согласуется с пунктом 4 концепции о чанкинге 200–300 токенов и реестре источников.

## 4. Replacement Criteria
Модель может быть заменена при выполнении любого из условий:
- Падение качества ниже 90% от текущего уровня релевантности в production (по результатам пилота / регрессионных прогонов).
- Требование ИБ перейти на 100% российского вендора моделей эмбеддингов.
- Появление верифицированной российской модели с качеством ≥ `BAAI/bge-m3` на русскоязычных бенчмарках.

## 5. Chunking, Metadata Schema & RAG Flags (Sprint 2 / BL-06)

Этот раздел подключает контракты chunking-параметров и схемы метаданных к
стандарту. Версия 1.1 (BL-16a, issue #87) добавила сам раздел; версия 1.2
(BL-06, issue #92) перевела `chunk_size`/`chunk_overlap` на L1-параметры
`512 / 64` и расширила guardrails; версия 1.3 (BL-02 hardening, issue #109)
добавляет section propagation и реалистичный MVP-порог покрытия `0.65`.
Версия 1.4 (BL-10, issue #118) добавляет Parent Document Retrieval (L2).
Версия 1.5 (BL-10, issue #137) фиксирует runtime-обвязку
`ParentAwareRetriever`, порядок применения L2 после multi-hop/query expansion
и синхронизацию YAML-схемы обязательных parent metadata.

### 5.1 Chunking parameters (Sprint 2, BL-06 L1)
| Параметр | Значение | Источник | Комментарий |
|----------|----------|----------|-------------|
| `chunk_size` | **512** ток. | `configs/embedding_config.yaml` | L1-окно, согласовано с [`RAG_OPTIMIZATION_ANALYSIS.md §3.1`](../RAG_OPTIMIZATION_ANALYSIS.md). |
| `chunk_overlap` | **64** ток. | `configs/embedding_config.yaml` | ≈ 12.5 % от окна (рекомендация LlamaIndex). |
| `min_chunk_size` | **384** ток. | `configs/embedding_config.yaml` | Нижняя граница — guardrail для пограничных случаев в `src/rag/chunker.py`. |
| `max_chunk_size` | **768** ток. | `configs/embedding_config.yaml` | Верхняя граница; bge-m3 эффективен на 256–1024 ток. |
| `section_aware_chunking` | **`true`** | `configs/embedding_config.yaml` | Section-aware splitter режет текст по заголовкам Markdown / нумерованным разделам / CAPS-блокам до применения token-окна. |

> ⚠️ **BREAKING CHANGE.** Изменение `chunk_size` с 250 на 512 меняет структуру
> индекса ChromaDB. Сразу после мерджа BL-06 владелец задачи выполняет полный
> reindex локально (`python knowledge_base/indexing/build_index.py`) и
> прогоняет Golden Set (BL-05) для валидации регрессий по метрикам
> retrieval / answer-quality.

### 5.2 Required chunk metadata schema
Каждый чанк, сохраняемый в ChromaDB, **обязан** содержать следующие ключи в
`metadata`. Поле `source` и `chunk_idx` уже присутствуют в MVP; четыре новых
поля добавляются задачей BL-02 в окне «Reindex & Metadata Enrichment».

| Ключ | Тип | Заполнение | Используется в |
|------|-----|------------|-----------------|
| `source` | str | имя файла-источника (`example.pdf`) | UI-цитаты, audit |
| `chunk_idx` | int | порядковый номер чанка внутри документа | дедупликация, debug |
| `page_number` | int \| null | номер страницы PDF (1-based); `null` для txt/md | NFR-02 (цитируемость), BL-09 |
| `section_title` | str \| null | заголовок ближайшего раздела (regex CAPS / `\d+\.\d+\.\d+`) | NFR-02, BL-09 |
| `section_number` | str \| null | нумерация раздела (`7.3.6`); `null` если нет нумерации | NFR-02, BL-10 (Parent Retrieval) |
| `product` | str | продукт-владелец источника (`mango_office`, `corporate_telephony`, …) | фильтрация выборки, BL-14 |
| `section_inherited` | bool | `true`, если `section_title` / `section_number` унаследованы от предыдущего заголовка | audit, schema debug |
| `parent_id` | str | стабильный идентификатор родительского раздела (`source::section_number::section_title`) | BL-10 L2 grouping |
| `section_id` | str | алиас `parent_id` для совместимости с section-level consumers | BL-10 L2 grouping |
| `parent_text` | str | полный текст родительского раздела, собранный из L1-чанков | BL-10 LLM context |

Дополнительное поле `section_fallback` может присутствовать в metadata для
аудита fallback-стратегии (`none`, `source_filename`). Оно не входит в
обязательную схему, но используется UI для человекочитаемой подписи цитат.

**Покрытие schema-check'ом:** `≥ 65 %` чанков должны содержать непустые
`page_number`, `section_title`, `section_number` и `product` после reindex
(BL-02 hardening). `section_inherited=false` является валидным значением и не
снижает coverage. Несоответствие логируется индексатором и попадает в отчёт
`docs/analysis/metadata-coverage-fix_v1.md`.

### 5.3 Section Propagation (BL-02 hardening)
Индексатор создаёт отдельный `SectionPropagationState` на каждый документ:

| Параметр | Значение | Назначение |
|----------|----------|------------|
| `section_propagation.enabled` | `true` | Включает наследование ближайшего найденного заголовка между чанками. |
| `section_propagation.max_pages_without_heading` | `6` | Сбрасывает контекст, если после последнего заголовка прошло больше 6 страниц. |
| `section_propagation.fallback_to_document_title` | `true` | До первого заголовка использует имя файла как безопасный fallback-раздел. |
| `section_propagation.fallback_section_number` | `document` | Значение `section_number` для fallback-раздела уровня документа. |
| `metadata_coverage_min` | `0.65` | Минимальный MVP-порог покрытия searchable metadata. |

Алгоритм:
1. Чанк сначала проверяется регулярными выражениями заголовков (`extract_section`).
2. При найденном заголовке вычисляется depth (`4.2` → 2). Новый заголовок того
   же или более высокого уровня сбрасывает нижележащий контекст; дочерний
   заголовок добавляется в стек.
3. Чанк без заголовка наследует верхний элемент стека и получает
   `section_inherited=true`.
4. Если превышен `max_pages_without_heading`, стек очищается, чтобы избежать
   ghost inheritance между главами.
5. Если активного контекста нет, включается fallback по имени файла:
   `section_number=document`, `section_title=<source stem>`,
   `section_fallback=source_filename`.

### 5.4 STRICT_MODE (BL-03)
Флаг `strict_rag_mode` в `configs/embedding_config.yaml` управляет
поведением `src/llm/client.py` при пустом или слабом результате поиска:

| Флаг | Значение по умолчанию | Поведение |
|------|------------------------|-----------|
| `strict_rag_mode` | `true` | При `len(context)==0` или `max_score < strict_min_score` LLM-вызов **не выполняется**. Возвращается детерминированный fallback («ничего не найдено в базе знаний»). |
| `strict_min_score` | `0.30` | Порог релевантности RRF-фьюжна. Подбирается на Golden Set (BL-05). |

Флаг защищает от риска R-01 «галлюцинации LLM» ([CONCEPT §7](../CONCEPT.md#7-управление-рисками)).
Тест регрессии — запрос вне домена (`out_of_domain`) в `tests/test_strict_mode.py`.

### 5.5 Masking of the RAG channel (BL-04)
Флаг `mask_rag_context` в `configs/embedding_config.yaml` включает
маскирование контекста перед формированием промпта:

| Флаг | Значение по умолчанию | Поведение |
|------|------------------------|-----------|
| `mask_rag_context` | `true` | `LLMClient.generate_rag_response` применяет `src/llm/masking.py::mask_context_chunks` ко всем чанкам, переданным в LLM. |

Отключение допустимо **только** в offline-прогонах `evaluate_rag.py` с
синтетическими данными. Контракт привязан к NFR-04 (резидентность данных) и
NFR-05 (0 утечек), см. [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md) §3.

### 5.6 Parent Document Retrieval (BL-10 L2)
По умолчанию `use_parent_context: false`, чтобы сохранить контракт L1-поиска.
В режиме «Консультация» UI включает L2-контекст явно:

| Флаг | Значение по умолчанию | Поведение |
|------|------------------------|-----------|
| `use_parent_context` | `false` | Ретривер ранжирует L1-чанки, затем при включении группирует их по `parent_id` и возвращает `parent_text`. |
| `parent_context_max_chars` | `6000` | Верхняя граница длины одного родительского контекста перед передачей в LLM. |

При отсутствии `parent_text` ретривер использует исходный child chunk, поэтому
старые индексы не ломаются. Для получения полноценного L2-контекста требуется
полный reindex.

`ParentAwareRetriever` применяется как внешний runtime-wrapper после
опциональных `IterativeRetriever` (multi-hop) и `QueryExpansionRetriever`.
Это сохраняет ранжирование по child chunks, исключает повторное расширение
одних и тех же разделов внутри каждого wrapper'а и гарантирует, что режим
«Анализ ТЗ» остаётся на L1-контексте даже при включённых L2-флагах в коде.

## 6. Operational Notes
- Конфигурация модели задаётся в `configs/` (имя модели, размерность, устройство исполнения) и не требует изменения кода RAG-пайплайна.
- Любая смена модели сопровождается обновлением этого файла (увеличение версии) и заметкой в `CHANGELOG.md`.
- Несовместимая смена размерности эмбеддингов требует переиндексации [`knowledge_base/`](../../knowledge_base/) и упоминается в новой версии ADR-001.
- Изменение `chunk_size` / `chunk_overlap` требует обновления §5.1 и BREAKING-записи в `CHANGELOG.md` (см. BL-16b).

## 7. References
- [`docs/CONCEPT.md`](../CONCEPT.md) — концепция MVP, разделы 5 (НФТ) и 6.2 (индексация KB).
- [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — архитектура RAG с гибридным поиском (см. Consequences → Metadata Enrichment).
- [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md) — аудит маскирования (RAG-канал, лог-санитайзер).
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.2.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.2.md) §3 — BL-16a, BL-02, BL-03, BL-04.
- [`docs/analysis/2026-05-12_review_mvp-context_v1.md`](../analysis/2026-05-12_review_mvp-context_v1.md) — открытый вопрос о целевой модели эмбеддингов в production.

## 8. История изменений
| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-05-12 | Первая версия стандарта: фиксация `BAAI/bge-m3` как модели эмбеддингов MVP и Production. |
| 1.1 | 2026-05-17 | BL-16a (issue #87): добавлен §5 с контрактами chunking-параметров, обязательной схемы метаданных (`page_number`, `section_title`, `section_number`, `product`), флагов `strict_rag_mode` / `strict_min_score` (BL-03) и `mask_rag_context` (BL-04). `chunk_size` / `chunk_overlap` не меняются — это сдвиг в BL-16b (Sprint 2). |
| 1.2 | 2026-05-17 | BL-06 (issue #92): `chunk_size` поднят с 250 до **512**, `chunk_overlap` — с 50 до **64**, guardrails расширены до 384–768 ток. Включён section-aware splitter (`section_aware_chunking: true`). **BREAKING CHANGE** для существующего индекса ChromaDB — требуется полный reindex после мерджа. |
| 1.3 | 2026-05-17 | BL-02 hardening (issue #109): добавлены `section_inherited`, section propagation с page-distance reset, fallback по имени документа и MVP-порог `metadata_coverage_min: 0.65`. |
| 1.4 | 2026-05-18 | BL-10 (issue #118): добавлены `parent_id`, `section_id`, `parent_text`, флаги `use_parent_context` / `parent_context_max_chars` и L2 Parent Document Retrieval для режима «Консультация». |
| 1.5 | 2026-05-18 | BL-10 (issue #137): закреплены `ParentAwareRetriever`, применение L2 после multi-hop/query expansion и синхронизация `required_metadata` в YAML с parent-полями индексатора. |
