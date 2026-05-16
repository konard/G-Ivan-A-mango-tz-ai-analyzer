# 🧮 Standard: Embedding Model

**Версия:** 1.0 | **Дата:** 2026-05-12 | **Статус:** Approved

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

## 5. Operational Notes
- Конфигурация модели задаётся в `configs/` (имя модели, размерность, устройство исполнения) и не требует изменения кода RAG-пайплайна.
- Любая смена модели сопровождается обновлением этого файла (увеличение версии) и заметкой в `CHANGELOG.md`.
- Несовместимая смена размерности эмбеддингов требует переиндексации [`knowledge_base/`](../../knowledge_base/) и упоминается в новой версии ADR-001.

## 6. References
- [`docs/CONCEPT.md`](../CONCEPT.md) — концепция MVP, раздел 4 (Требования → Данные).
- [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — архитектура RAG с гибридным поиском.
- [`docs/analysis/2026-05-12_review_mvp-context_v1.md`](../analysis/2026-05-12_review_mvp-context_v1.md) — открытый вопрос о целевой модели эмбеддингов в production.

## 7. История изменений
| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-05-12 | Первая версия стандарта: фиксация `BAAI/bge-m3` как модели эмбеддингов MVP и Production. |
