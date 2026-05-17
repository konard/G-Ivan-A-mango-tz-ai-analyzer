# 🧮 Standard: Embedding Model

**Версия:** 1.1 | **Дата:** 2026-05-17 | **Статус:** Approved

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

## 5. Chunking, Metadata Schema & RAG Flags (Sprint 1 / BL-16a)

Этот раздел добавлен в версии 1.1 (BL-16a, issue #87) и фиксирует контракты,
которые подключаются к стандарту до изменения кода BL-02 / BL-03 / BL-04.

### 5.1 Chunking parameters (MVP, Sprint 1)
| Параметр | Значение | Источник | Комментарий |
|----------|----------|----------|-------------|
| `chunk_size` | **250** ток. | `configs/embedding_config.yaml` | MVP-окно; будет поднято до 512 в BL-16b (Sprint 2) после BL-06. |
| `chunk_overlap` | **50** ток. | `configs/embedding_config.yaml` | MVP-перекрытие; будет поднято до 64 в BL-16b. |
| `min_chunk_size` | **200** ток. | `configs/embedding_config.yaml` | Нижняя граница (соответствует [CONCEPT §6.2](../CONCEPT.md#62-индексация-базы-знаний)). |
| `max_chunk_size` | **300** ток. | `configs/embedding_config.yaml` | Верхняя граница; код-валидация в `src/rag/chunker.py`. |

> ⚠️ **BL-16a НЕ меняет `chunk_size`/`chunk_overlap`.** Сдвиг к `512 / 64`
> выполняется задачей BL-16b после внедрения BL-06 (section-aware splitter).
> До этого момента стандарт декларирует целевые границы (`min`/`max`), а не
> новые значения окна.

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

**Покрытие schema-check'ом:** `≥ 95 %` чанков должны содержать непустые
`page_number` и `section_title` после reindex (BL-02). Несоответствие
логируется как `schema_warning` и попадает в отчёт `evaluate_rag.py`.

### 5.3 STRICT_MODE (BL-03)
Флаг `strict_rag_mode` в `configs/embedding_config.yaml` управляет
поведением `src/llm/client.py` при пустом или слабом результате поиска:

| Флаг | Значение по умолчанию | Поведение |
|------|------------------------|-----------|
| `strict_rag_mode` | `true` | При `len(context)==0` или `max_score < strict_min_score` LLM-вызов **не выполняется**. Возвращается детерминированный fallback («ничего не найдено в базе знаний»). |
| `strict_min_score` | `0.30` | Порог релевантности RRF-фьюжна. Подбирается на Golden Set (BL-05). |

Флаг защищает от риска R-01 «галлюцинации LLM» ([CONCEPT §7](../CONCEPT.md#7-управление-рисками)).
Тест регрессии — запрос вне домена (`out_of_domain`) в `tests/test_strict_mode.py`.

### 5.4 Masking of the RAG channel (BL-04)
Флаг `mask_rag_context` в `configs/embedding_config.yaml` включает
маскирование контекста перед формированием промпта:

| Флаг | Значение по умолчанию | Поведение |
|------|------------------------|-----------|
| `mask_rag_context` | `true` | `LLMClient.generate_rag_response` применяет `src/llm/masking.py::mask_context_chunks` ко всем чанкам, переданным в LLM. |

Отключение допустимо **только** в offline-прогонах `evaluate_rag.py` с
синтетическими данными. Контракт привязан к NFR-04 (резидентность данных) и
NFR-05 (0 утечек), см. [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md) §3.

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
