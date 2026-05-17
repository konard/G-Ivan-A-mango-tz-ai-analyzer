# Sprint-1 P0 — Execution Report (issue #87)

## 🗂 Метаданные
- **Дата:** 2026-05-17
- **Версия:** v1
- **Автор:** konard (AI issue solver)
- **Статус:** Draft
- **Связанные документы:**
  - [`docs/backlog/2026-05-17_rag-optimization-backlog_v1.md`](../backlog/2026-05-17_rag-optimization-backlog_v1.md) — backlog v1.2 (§3 Sprint-1)
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — ADR-001 (BM25+Dense+RRF)
  - [`docs/ADR/003-data-masking.md`](../ADR/003-data-masking.md) — ADR-003 v1.1 (PII masking)
  - GitHub issue [#87](https://github.com/G-Ivan-A/clarify-engine-ai/issues/87), draft PR [#88](https://github.com/G-Ivan-A/clarify-engine-ai/pull/88)

---

## 1. Понимание контекста

- **Цель проекта / MVP:** перевести RAG-пайплайн МАНГО ОФИС из стадии MVP в Pilot-ready состояние, закрыв десять P0-задач из Sprint-1 backlog v1.2 §3.
- **Анализируемая проблема:** до этого спринта продакшен-UI запускал базовый Chroma-ретривер без BM25/RRF, чанки несли минимальный набор метаданных, температура и PII-маскирование не были закреплены, а CI не содержал автоматической проверки retrieval-качества. Это блокировало пилот по детерминизму, аудиту и измеримому качеству.
- **Предпосылки и ограничения:**
  - Все изменения собраны в одной ветке `issue-87-01835e968b5a` и одном PR #88 (DoD спринта).
  - Запрещено вводить новые внешние сервисы; Chroma остаётся персистентной (`./chroma_data`).
  - Сохранён single-user MVP-режим UI (Streamlit) и существующая fallback-цепочка LLM (GigaChat → OpenRouter → Ollama).
  - PII-маскирование выполняется на одной библиотеке `src/llm/masking.py` (ADR-003 §4).

## 2. Анализ текущего состояния и выполненные работы

### 2.1. Сводка по задачам Sprint-1

| BL | Заголовок | Статус | Коммит | Ключевые артефакты |
|----|-----------|--------|--------|---------------------|
| BL-16a | Sync standards | ✅ done | `c06acf5` | `docs/ADR/001-rag-architecture.md`, `docs/standards/embedding-model.md`, `docs/audit/data-masking_v1.md` |
| BL-22 | Temperature lock | ✅ done | `6dec421` | `configs/llm_config.yaml` (`temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024`), `src/llm/client.py`, `tests/test_decoding_lock.py` |
| BL-04 | Mask RAG context | ✅ done | `6dec421` | `src/llm/masking.py::mask_text`, `src/llm/client.py::generate_rag_response(mask=True)`, `tests/test_rag_masking.py` |
| BL-03 | STRICT_MODE | ✅ done | `6dec421` | `src/llm/client.py` (deterministic fallback без вызова LLM), `tests/test_strict_mode.py` |
| BL-23 | Log sanitization | ✅ done | `587f7dd` | `src/llm/masking.py::sanitize_log_record`, `src/pipeline.py::_JsonFormatter/_SanitizingFilter`, `tests/test_masking.py::TestLogSanitization` |
| BL-01 | HybridRetriever в UI | ✅ done | `3f2549a` | `src/rag/retriever.py::HybridChromaRetriever`, `src/ui/app.py::get_retriever`, `tests/test_hybrid_chroma_retriever.py` |
| BL-02 | Расширение метаданных чанков | ✅ done | `0b1b592` | `knowledge_base/indexing/build_index.py` (6 ключей: `source, chunk_idx, page_number, section_title, section_number, product`), `tests/test_metadata_extraction.py` |
| BL-05 / BL-05.1 | Golden Set + evaluator + CI smoke | ✅ done | `0327367` | `test_data/rag_golden_set.json` (32 элемента, ≥5 в `smoke`), `scripts/evaluate/evaluate_rag.py`, `.github/workflows/rag-eval-smoke.yml`, `tests/test_evaluate_rag.py` |
| BL-09 | Кликабельные цитаты в UI | ✅ done | `fb9c3af` | `src/ui/app.py::build_citation_link / linkify_citations`, `tests/test_citation_links.py` |

### 2.2. Что изучено

- Концепция и backlog: `docs/backlog/2026-05-17_rag-optimization-backlog_v1.md` v1.2 §3 — список из десяти P0-задач Sprint-1.
- Архитектура: `docs/ADR/001-rag-architecture.md` — BM25+Dense+RRF, k=60, embedder `BAAI/bge-m3`.
- Стандарты: `docs/standards/embedding-model.md` (chunk-метаданные), `docs/standards/citation-format.md` (формат BL-09 цитат), `docs/audit/data-masking_v1.md` (PII-режим).
- Код: `src/llm/client.py`, `src/rag/retriever.py`, `src/ui/app.py`, `knowledge_base/indexing/build_index.py`, `scripts/evaluate/evaluate_rag.py`.

### 2.3. Ключевые наблюдения

- **Детерминизм декодирования (BL-22).** `LLMClient.generate_rag_response` теперь читает `decoding` из `configs/llm_config.yaml` и отдаёт его в payload GigaChat/OpenRouter/Ollama. Закреплены `temperature=0.1`, `top_p=0.9`, `seed=42`, `max_tokens=1024`. Тест `tests/test_decoding_lock.py` проверяет, что декодинг-параметры реально доезжают до HTTP-payload каждого провайдера.
- **PII end-to-end (BL-04 + BL-23).** Все шаги, на которых данные пользователя приближаются к LLM или к диску, проходят через `sanitize_log_record` (логи) либо `mask_text` (контекст и ответ). 4 регэкса (`email`, `phone_ru`, `ip_address`, `internal_domain`) совпадают с ADR-003 §4. Eval-репорт также санитизируется (`scripts/evaluate/evaluate_rag.py::write_report`).
- **STRICT_MODE (BL-03).** Если ретривер вернул пустой или out-of-domain контекст, `generate_rag_response` отдаёт детерминированный fallback **без сетевого вызова к LLM**. Это закрывает риск «уверенных галлюцинаций» в Pilot.
- **HybridChromaRetriever (BL-01).** Новый класс инкапсулирует BM25 (rank-bm25) и dense (Chroma+bge-m3) поиск, сливает результаты через RRF (k=60). Корпус BM25 лениво загружается из Chroma при первом запросе — повторного эмбеддинга нет. `src/ui/app.py::get_retriever` использует именно его.
- **Метаданные (BL-02).** `build_index.py` теперь делает per-page чанкинг (pypdf), извлекает `section_title/section_number` тремя регэксами и матчит `product` longest-prefix по `configs/products.yaml` (с дефолтным словарём в коде). Покрытие 6 ключей логируется на каждой пересборке.
- **Golden Set + CI smoke (BL-05/BL-05.1).** Golden Set: 32 пары вопрос–источник; 5 элементов в подвыборке `smoke`. CI-workflow `rag-eval-smoke.yml` запускает `evaluate_rag.py --retriever stub --subset smoke --min-hit-rate 1.0 --min-mrr 1.0 --min-context-recall 0.5`, отрабатывает на CPU без ML-зависимостей за <2 мин и пишет артефакт `rag-eval-smoke-report`.
- **Цитаты (BL-09).** Helper `build_citation_link` и `linkify_citations` переписывают `[filename.pdf]` в LLM-ответе в кликабельные ссылки формата `[source.pdf, стр. N](file:///abs/path#page=N)`. Если источника нет в чанках — placeholder остаётся нетронутым (никогда не выдумываем страницу). Шапки чанков в UI получили `· стр. N` и кликабельную ссылку внутри expander.

### 2.4. Тесты

| Suite | Команда | Результат |
|-------|---------|-----------|
| Полный pytest | `python -m pytest` | **150 passed** (см. лог в PR) |
| BL-22 декодинг | `python -m pytest tests/test_decoding_lock.py` | 6 passed |
| BL-04 mask RAG | `python -m pytest tests/test_rag_masking.py` | 5 passed |
| BL-03 STRICT_MODE | `python -m pytest tests/test_strict_mode.py` | 5 passed |
| BL-23 log san | `python -m pytest tests/test_masking.py` | 38 passed (включая `TestLogSanitization`) |
| BL-01 hybrid | `python -m pytest tests/test_hybrid_chroma_retriever.py` | 6 passed |
| BL-02 метаданные | `python -m pytest tests/test_metadata_extraction.py` | 11 passed |
| BL-05 evaluator | `python -m pytest tests/test_evaluate_rag.py` | 8 passed |
| BL-09 цитаты | `python -m pytest tests/test_citation_links.py` | 7 passed |

### 2.5. Что НЕ входило в Sprint-1

- **BL-05.2 (LLM answer-quality channel).** Phantom-метрика «answer quality» поверх LLM-судьи запланирована в Sprint-2; пока Golden Set оценивается только retrieval-каналами (Hit Rate @K, MRR, Context Recall).
- **Реальный hybrid-прогон в CI.** Smoke-job использует deterministic stub-ретривер, чтобы вписаться в 2-минутный бюджет; production-прогон по полному Golden Set с `HybridChromaRetriever` запускается вручную (`python scripts/evaluate/evaluate_rag.py`) до миграции CI на self-hosted runner.
- **Multi-user / per-tenant изоляция в UI.** Не входило в P0 — закрывается в Sprint-3 (BL-10).

## 3. Рекомендации

### 3.1. Доработки на Sprint-2

| # | Приоритет | Рекомендация | Обоснование | Оценка |
|---|-----------|--------------|-------------|--------|
| 1 | MUST | Реализовать BL-05.2 (LLM judge) и подвесить его как nightly CI job на полном Golden Set. | Закрывает измерение answer-quality, которое в Sprint-1 не покрыто. | M |
| 2 | SHOULD | Внести производственный `hybrid`-прогон evaluator в self-hosted CI и сравнить метрики с stub-baseline. | Подтверждает, что фактический BM25+Dense+RRF превосходит lexical-only baseline. | M |
| 3 | SHOULD | Перевести `configs/products.yaml` из мягкого дефолта в обязательный артефакт релиза и расширить продуктовый словарь по фактическим источникам. | Метрика покрытия `product` должна стабильно держаться ≥95% на любой пересборке индекса. | S |
| 4 | MAY | Расширить Golden Set до 60+ элементов и пометить часть как `regression` subset. | Стабильнее отлавливать регрессии MRR/Recall между релизами. | M |
| 5 | MAY | Добавить юнит-тест на сценарий BL-09, где LLM возвращает несколько одинаковых имён источников с разными страницами. | Сейчас linkifier берёт страницу первого совпадения, что для повторов даёт consistent (но не page-by-mention) поведение. Документировать. | S |

### 3.2. Условия пересмотра

- Спринт пересматривается, если на полном Golden Set retrieval-метрики падают ниже целевых порогов backlog v1.2 §3 (Hit Rate @5 ≥ 0.85, MRR ≥ 0.65, Context Recall ≥ 0.70).
- При появлении нового embedder/ретривера в ADR-001 v2 — повторно прогонять весь Sprint-1 контрактный набор тестов.

## 4. Открытые вопросы

- Нужно ли в Sprint-2 заменить deterministic stub-ретривер CI на on-disk fixture с предсобранной Chroma-коллекцией (компромисс «скорость vs. реалистичность»)?
- Какой LLM выбрать судьёй для BL-05.2 — GigaChat-Pro (платный, in-domain), OpenRouter-Gemini (дешевле, OOS) или Ollama (free, локально)?
- Должны ли `file:///`-ссылки BL-09 трансформироваться во внешние URL, когда UI разворачивается за reverse-proxy (Pilot)? Сейчас ссылки рассчитаны на single-user локальный запуск Streamlit.

## 5. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-17 | Первая версия: фиксирует завершение всех 10 P0-задач Sprint-1 (issue #87, PR #88). |
