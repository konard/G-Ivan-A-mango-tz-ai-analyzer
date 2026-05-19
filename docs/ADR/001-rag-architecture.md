# ADR-001: RAG Architecture with Hybrid Search

## Status
Accepted (2026-05-12; revised 2026-05-19 for Sprint 2 BL-32 — see §History v1.4)

## Context
- Требуется классификация требований ТЗ с обязательным цитированием (см. [`docs/CONCEPT.md`](../CONCEPT.md), разделы 1 и 4).
- Необходим поиск по публичной документации и внутреннему перечню функциональности.
- Требования к точности: ≥ 75% F1-score, ≥ 95% цитируемость (концепция, раздел 4, НФТ).
- Чувствительные данные не должны покидать корпоративный контур; зарубежные LLM-API допустимы только в режиме `use_test_data_mode: true` (концепция, раздел 5).

## Decision
Использовать RAG-паттерн с гибридным поиском:
1. **Vector Store:** ChromaDB (локальное развёртывание, Apache 2.0).
2. **Embeddings:** `BAAI/bge-m3` (1024 dimensions, multilingual). Стандарт зафиксирован в [`docs/standards/embedding-model.md`](../standards/embedding-model.md).
3. **Search Strategy:** Hybrid (BM25 + Dense + RRF).
   - BM25 — для точных терминов и артикулов.
   - Dense (cosine similarity) — для семантического поиска.
   - RRF (Reciprocal Rank Fusion, k = 60) — для ранжирования.
4. **LLM Fallback Chain:** DeepSeek → GigaChat (концепция, раздел 5). MVP-цепочка упрощена в 2026-05 (issue #64): Qwen (DashScope) и YandexGPT исключены.

## Consequences

### Positive
- Компенсация слабых сторон pure-dense поиска (точные термины, артикулы, числа).
- Поддержка мультиязычности (русский + техническая терминология) благодаря `bge-m3`.
- Локальное развёртывание векторного хранилища (данные не покидают контур).
- Гибридная схема поддерживает требования к цитируемости ≥ 95% (раздел 4 концепции).

### Negative
- Требует больше ресурсов, чем pure-dense (два индекса, дополнительная стадия RRF).
- Сложнее в отладке: два канала поиска и стадия фьюжна, нужен унифицированный лог результатов поиска.
- Появляются дополнительные настройки (веса BM25/Dense, параметр k у RRF), которые необходимо валидировать в пилоте.

### Neutral
- Модель эмбеддингов может быть заменена через конфиг без изменения кода (см. критерии замены в [`docs/standards/embedding-model.md`](../standards/embedding-model.md)).
- Vector store также абстрагирован конфигом — допустима последующая замена ChromaDB на резидентную альтернативу при изменении требований ИБ.
- **Chunk size tuning (BL-32).** После BL-06 production-контракт чанкинга зафиксирован как `chunk_size=512`, `chunk_overlap=64`, guardrails `[384, 768]`. Изменение этих значений меняет границы чанков и требует полного reindex KB.

### Sprint 1 Addenda (BL-16a, issue #87)
- **Metadata Enrichment (BL-02).** Каждый чанк в ChromaDB обязан содержать `page_number`, `section_title`, `section_number`, `product`, `section_inherited` в дополнение к `source` / `chunk_idx`. Контракт зафиксирован в [`docs/standards/embedding-model.md`](../standards/embedding-model.md) §5.2–5.3; schema-check выполняется при индексации и в `evaluate_rag.py` (BL-05). После issue #109 MVP-порог покрытия searchable metadata установлен на `≥ 65 %`; продуктовая цель цитируемости `≥ 95 %` остаётся целевой метрикой пилота.
- **STRICT_MODE (BL-03).** Флаги `strict_rag_mode` / `strict_min_score` в `configs/embedding_config.yaml` блокируют LLM-вызов при пустом или слабом контексте. Снижает риск R-01 (галлюцинации); подбор порога — на Golden Set.
- **Masked RAG channel (BL-04).** Флаг `mask_rag_context` в `configs/embedding_config.yaml` включает применение `mask_context_chunks` ко всем чанкам перед формированием промпта. NFR-04 / NFR-05.
- **Temperature lock (BL-22).** Блок `decoding:` в [`configs/llm_config.yaml`](../../configs/llm_config.yaml) (`temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024`) подключается `LLMClient`'ом ко всем провайдерам fallback-цепочки. Цель — детерминизм regression-прогонов Golden Set (BL-05) и стабильность F1.
- **Log sanitization (BL-23).** `src/llm/masking.py::sanitize_log_record` подключается как `logging.Filter` в `src/pipeline.py` и применяется к отчётам `evaluate_rag.py`. Контракт повторяет ADR-003 §4.3 (`sanitize_for_log()`). NFR-05.

## Triggers for Revision
- Падение фактической точности ниже 70% по итогам пилота (Exit Criteria MVP, раздел 7 концепции).
- Изменение состава доступных LLM-провайдеров (например, недоступность DeepSeek или GigaChat).
- Смена требований резидентности данных (например, запрет на использование зарубежных API даже в тестовом режиме).
- Появление верифицированной российской модели эмбеддингов с качеством ≥ `bge-m3`.
- Включение `MULTIHOP_ENABLED=true` (BL-11) либо расширение fallback-цепочки за пределы DeepSeek → GigaChat.
- Любое изменение `chunk_size` / `chunk_overlap` / guardrails после принятого окна `512 / 64` и `[384, 768]` требует ревизии § Consequences, BREAKING-записи в `CHANGELOG.md` и полной переиндексации KB.

## References
- [`docs/CONCEPT.md`](../CONCEPT.md) — концепция MVP, разделы 3 (Описание решения) и 5 (Архитектура и стек).
- [`docs/standards/embedding-model.md`](../standards/embedding-model.md) — стандарт модели эмбеддингов.
- [`docs/analysis/2026-05-12_review_mvp-context_v1.md`](../analysis/2026-05-12_review_mvp-context_v1.md) — ревью концепции MVP (рекомендация MUST: заполнить ADR-001).

## History
| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-05-12 | Первая версия ADR: фиксация RAG с гибридным поиском (BM25 + Dense + RRF), ChromaDB и `BAAI/bge-m3`. |
| 1.1 | 2026-05-16 | Упрощение LLM fallback-цепочки до двух провайдеров (DeepSeek → GigaChat); исключены Qwen (DashScope) и YandexGPT (issue #64). |
| 1.2 | 2026-05-17 | BL-16a (issue #87): добавлен раздел «Sprint 1 Addenda» (Metadata Enrichment BL-02, STRICT_MODE BL-03, Masked RAG channel BL-04, Temperature lock BL-22, Log sanitization BL-23). Triggers for Revision дополнены пунктом про переход на `chunk_size=512` (BL-16b) и расширение fallback-цепочки. |
| 1.3 | 2026-05-17 | BL-02 hardening (issue #109): metadata coverage MVP-порог уточнён до `≥ 65 %`, добавлен `section_inherited` и section propagation с защитой от ghost inheritance. |
| 1.4 | 2026-05-19 | BL-32 (issue #152): Consequences и Triggers синхронизированы с принятым окном `chunk_size=512`, `chunk_overlap=64`, guardrails `[384, 768]`; изменение окна явно требует reindex KB. |
