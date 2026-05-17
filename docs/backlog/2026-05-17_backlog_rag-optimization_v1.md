# 📦 Бэклог оптимизации RAG-пайплайна (P0–P2)

> Согласованный реестр задач перехода от MVP-реализации RAG к Pilot-ready
> архитектуре по результатам [RAG_OPTIMIZATION_ANALYSIS.md](../RAG_OPTIMIZATION_ANALYSIS.md)
> (issue [#76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76)).
>
> Документ не модифицирует код. Кодовые изменения и обновления связанной
> документации стартуют **только после статуса Accepted** и утверждения
> Product Owner.

## 🗂 Метаданные
- **Дата:** 2026-05-17
- **Версия:** v1
- **Автор:** konard (AI issue solver)
- **Статус:** Draft → Review
- **Владелец ревью:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Связанные документы:**
  - [`docs/RAG_OPTIMIZATION_ANALYSIS.md`](../RAG_OPTIMIZATION_ANALYSIS.md) — источник рекомендаций (issue [#76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76)).
  - [`docs/CONCEPT.md`](../CONCEPT.md) §§ 4–6 (FR/НФТ, архитектура), §6.2 (компоненты), §8.1.2 (Пилот).
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — гибридный поиск BM25 + Dense + RRF.
  - [`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md) — стратегический контекст (Concept).
  - [`docs/standards/embedding-model.md`](../standards/embedding-model.md), [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) — параметры чанкинга и vector store.
  - [`docs/standards/naming-convention.md`](../standards/naming-convention.md) — стандарт именования (тип `backlog`, v1.1).
- **Связанный Issue:** [#77](https://github.com/G-Ivan-A/clarify-engine-ai/issues/77).

---

## 1. Контекст и цель

Текущий RAG-путь `similarity_search → concat → LLM` (см. `src/ui/app.py:97-107`)
обеспечивает базовый MVP, но не покрывает требования к точности, цитируемости
и устойчивости к кросс-документным зависимостям, зафиксированные в
`docs/CONCEPT.md` §§4–6 и [ADR-001](../ADR/001-rag-architecture.md).

**Цель бэклога:** формализовать дорожную карту перехода MVP → Pilot-ready
без переписывания архитектурного фундамента, в три волны приоритетов
(P0 → P1 → P2) с явной привязкой каждой задачи к источнику требований.

**Что меняется относительно НФТ MVP:**
- Целевая планка цитируемости на MVP-окончании временно снижается с
  `≥ 95 %` до `≥ 80 %` (см. NFR-02), чтобы не блокировать ранний выпуск
  Pilot. Возврат к `≥ 95 %` — Exit Criterion Пилота (см. CONCEPT §8.1.2).
- Целевые F1 и резидентность не меняются.
- **Мы не понижаем приоритет качества поиска** — наоборот, P0-блок целиком
  адресует hybrid retrieval, метаданные, STRICT_MODE и маскирование, что
  даёт измеримый рост recall и контроль галлюцинаций.

**Соответствие стандарту наименования:** имя файла —
`docs/backlog/2026-05-17_backlog_rag-optimization_v1.md` (см.
[`docs/standards/naming-convention.md`](../standards/naming-convention.md)
v1.1, §3.2).

---

## 2. Валидация против RAG_OPTIMIZATION_ANALYSIS.md

| Срез анализа (§§) | Наша задача | Закрывает |
|------------------|-------------|-----------|
| §2.2 Фрагментация контекста | BL-06 (chunker L1), BL-10 (Parent L2), BL-16 (синхронизация стандартов) | Проблема P1 |
| §2.3 Минимальные метаданные | BL-02 (page/section/product), BL-09 (кликабельные цитаты) | Проблема P2 |
| §2.4 Pure-dense в UI | BL-01 (HybridRetriever в production) | Проблема P3 |
| §2.5 Нет multi-hop | BL-11 (флаг `MULTIHOP_ENABLED=false`), BL-12 (Query Expansion) | Проблема P4 |
| §2.6 Stateless UI | BL-07 (`st.session_state` + Last-6 + summarization) | Проблема P5 |
| §2.7 Слабое grounding | BL-03 (STRICT_MODE), BL-04 (маскирование), BL-08 (prompt library) | Проблема P6 |
| §2.8 Нет RAG-метрик | BL-05 (Golden Set + `evaluate_rag.py`) | Проблема P7 |
| §9 Ollama-оптимизация | BL-15 (квантование, `keep_alive`, ThreadPool) | Locality |
| §3.1 Идея Canonical Cache | BL-13 (гипотеза → отдельный ADR), BL-14 (Offline Dependency Extraction) | Стратегия |

**Покрытие:** 16/16 рекомендаций §12.1 анализа уложены в P0–P2 без потерь.
Не вошедшие в анализ блоки (например, cross-encoder reranker, GraphRAG,
fine-tuning bge-m3) явно вынесены в §14 анализа как Out of Scope и
**не добавляются** в этот бэклог.

---

## 3. Бэклог P0 (MUST для подготовки Pilot)

| ID | Задача | Контекст | Проблема | Решение | Усилия | Триггеры готовности |
|----|--------|----------|----------|---------|--------|---------------------|
| **BL-01** | Подключение HybridRetriever в production-путь UI | [ADR-001](../ADR/001-rag-architecture.md) требует BM25 + Dense + RRF | `src/ui/app.py:99` использует pure-dense `ChromaRetriever`, BM25-канал мёртв в живом пути | Переключить UI на `HybridRetriever` (`src/rag/retriever.py:364-510`), RRF `k=60`, top_k = 5 | S (1 д) | Smoke-прогон Golden Set (BL-05) показывает Hit Rate@5 ≥ baseline |
| **BL-02** | Расширение метаданных чанков: `page_number`, `section_title`, `section_number`, `product` | НФТ цитируемости (CONCEPT §5, NFR-02) | `knowledge_base/indexing/build_index.py:238` сохраняет только `{source, chunk_idx}` — нет привязки к страницам и разделам | Page-aware парсинг (`pypdf.PdfReader().pages`) + regex-извлечение заголовков (`\d+\.\d+\.\d+`, CAPS) + product mapping по `source_file` | M (2–3 д) | После reindex `≥ 95 %` чанков имеют непустые `page_number` и `section_title` |
| **BL-03** | STRICT_MODE при пустом / нерелевантном контексте | CONCEPT §7, R-01 (защита от галлюцинаций) | При `top_k`-выдаче без совпадений или `max_score < threshold` LLM «дорисовывает» из весов | Блокировать LLM-вызов при `len(context)==0` или `max_score < STRICT_MIN_SCORE`; возвращать детерминированный fallback. Переменная `STRICT_RAG_MODE=true` в проде | S (0.5 д) | Регрессионный тест: запрос вне домена возвращает «не найдено» без LLM-вызова |
| **BL-04** | Маскирование RAG-контекста перед LLM (`mask=True` в `generate_rag_response`) | NFR-04/NFR-05 (резидентность, 0 утечек), R-03 | `LLMClient.generate_rag_response` сейчас НЕ применяет `mask_text()` — RAG-канал течёт | Внедрить `mask=True` по умолчанию; покрыть `tests/test_masking.py` сценарием RAG-вызова | S (0.5 д) | Аудит исходящего HTTP-трафика тестов — 0 совпадений regex чувствительных данных |
| **BL-05** | Создание `test_data/rag_golden_set.json` (≥ 30 Q/A) + `scripts/evaluate/evaluate_rag.py` | NFR-01, отсутствие RAG-метрик | Нет способа количественно валидировать улучшения; `evaluate_quality.py` покрывает только классификацию | 10 ручных кейсов (БА) + 20 LLM-черновиков (валидация PO). Метрики `Hit Rate@K`, `MRR`, `Context Recall` чистым Python — без RAGAS-зависимости | M (2 д) | `evaluate_rag.py` отдаёт JSON-отчёт; CI smoke-job укладывается в `< 2 мин` |
| **BL-16** | Синхронизация документации и конфигов под новые стандарты L1-чанкинга | CONCEPT §6.2 фиксирует 200–300 ток., анализ §3.1 предлагает 512 | Стандарт расходится с целевой схемой — нельзя катить BL-06 без согласования | Обновить `docs/CONCEPT.md` §6.2, `docs/standards/embedding-model.md`, `docs/ADR/001-rag-architecture.md` (Consequences + Triggers), `configs/embedding_config.yaml` | S (1 д) | Все четыре файла увеличивают версию; reindex-окно согласовано с PO |

**Совокупная нагрузка P0:** ≈ 7–8 человеко-дней, укладывается в один Sprint
(см. §6).

---

## 4. Бэклог P1 (SHOULD для Pilot UX/качества)

| ID | Задача | Контекст | Проблема | Решение | Усилия | Триггеры готовности |
|----|--------|----------|----------|---------|--------|---------------------|
| **BL-06** | Chunker L1: `chunk_size = 512`, `overlap = 64`, section-aware split | Структура SaaS-мануалов MANGO OFFICE; рекомендация анализа §3.1 | Фиксированное окно 250 разрывает разделы вида «7.3.6 Настройка SSO» посередине | Увеличить окно, добавить эвристики разреза (`\n#{1,6} `, нумерованные разделы, CAPS-заголовки). Полный reindex | S (1 д) | Hit Rate@5 на Golden Set +10–15 % относительно baseline |
| **BL-07** | Память диалога: `st.session_state` + Last-6 + auto-summarization | UX пилотных БА | Stateless UI: «уточни ответ» / «а что если AD внешний?» вынуждают повторять контекст | Сессионное хранилище в `src/ui/app.py`, триггер LLM-summary после 12 пар | S (1 д) | E2E-сценарий «3 уточнения подряд» сохраняет историю до перезапуска приложения |
| **BL-08** | Prompt Library: `prompts/system_rag_v1.md`, `system_rag_reflection_v1.md`, `system_rag_query_expansion_v1.md` | CONCEPT §6.5 (промпт-менеджмент) | Промпты в UI захардкожены, версионирование промптов невозможно | Вынести шаблоны в `prompts/`, обновить `prompts/prompt_changelog.md` | S (1 д) | PR с промптами проходит код-ревью PO; имена соответствуют `*_v<N>.md` |
| **BL-09** | Кликабельные цитаты `[source.pdf, стр. N, §X.Y]` в UI | NFR-02 (цитируемость), CONCEPT §7 | UI рендерит только имя файла — БА не может перейти к источнику | Markdown-ссылки через `static/kb/` (или `file://` локально) + рендер из метаданных BL-02. На Pilot — S3/Streamlit static serve | S (0.5 д) | Минимум 1 из 3 тест-цитат на каждом ответе кликабельна и открывает PDF на нужной странице |
| **BL-10** | Parent Document Retrieval (L2): двухслойная индексация | Фрагментация зависимостей, рекомендация анализа §3.2 | Child-чанки точны, но LLM не хватает родительского контекста | Две коллекции: `children` (256/32) и `parents` (~512). Поиск по children → возврат parents | L (3–4 д) | Hit Rate@5 +15–25 % к L1; объём индекса не превышает baseline × 1.4 |

**Совокупная нагрузка P1:** ≈ 6–7 человеко-дней (один Sprint).

---

## 5. Бэклог P2 (MAY — оптимизации и эксперименты)

| ID | Задача | Контекст | Проблема | Решение | Усилия | Триггеры готовности |
|----|--------|----------|----------|---------|--------|---------------------|
| **BL-11** | Multi-hop iterative retrieval (`max_hops=2`) под флагом `MULTIHOP_ENABLED=false` | Cross-doc зависимости («SSO + AD», «лимиты + тариф») | Один проход не достаёт второй раздел; reflection-loop отсутствует | Reflection-LLM (`system_rag_reflection_v1.md`); выключен по умолчанию из-за `+latency`/`+cost` | M (2 д) | A/B на Golden Set категории `cross_doc`: +Context Recall ≥ 10 %, p95 latency ≤ +50 % |
| **BL-12** | Query Expansion (3 переформулировки) | Терминологические вариации (ВАТС / VPBX) | Разные формулировки дают разный dense-результат | LLM-синонимы параллельно основному запросу, фьюж выдачи через RRF | S (1 д) | На запросах с синонимами Hit Rate@5 не падает, MRR не ухудшается |
| **BL-13** | Canonical Query Cache & Clustering (гипотеза) | Снижение `cost` / `latency` на повторяющихся запросах | Повторяющиеся ТЗ-вопросы каждый раз грузят LLM | Кэш канонических ответов (cosine ≥ 0.95) + валидация `sha256` источников. Детализация в отдельном ADR | M (2–3 д) | ADR-проект готов; PoC показывает hit-rate кэша ≥ 30 % на корпусе ТЗ |
| **BL-14** | Offline Dependency Extraction (regex + local LLM) | Cross-ссылки в документации MANGO OFFICE | Runtime multi-hop дорог; зависимости можно «препроцессить» | Один offline-прогон Ollama для извлечения `prerequisites`, `see_also`, `related_sections` в метаданные чанков | M (2–3 д) | После прогона `≥ 70 %` чанков с маркерами «см. раздел» получают непустой `related_sections` |
| **BL-15** | Ollama: квантование `q4_K_M`, `keep_alive`, ThreadPool batch | Локальный инференс, рекомендация анализа §9 | Синхронные вызовы блокируют eval-прогоны (50 Q × ~10 с) | Явное `q4_K_M`, `num_ctx=4096`, `keep_alive=10m`, `ThreadPoolExecutor(max_workers=4)` для скриптов | S (1 д) | `evaluate_rag.py` на 50 Q укладывается в ≤ 50 % текущего wall-clock |

**Совокупная нагрузка P2:** ≈ 8–10 человеко-дней (план — Sprint 3 + бэклог).

---

## 6. Предполагаемый порядок раскатки (для согласования)

| Sprint | Содержимое | Обязательный артефакт |
|--------|-----------|------------------------|
| Sprint 1 (1 нед) | BL-01, BL-02, BL-03, BL-04, BL-05, BL-16 | UI на hybrid + базовые метаданные + Golden Set + синхронизация стандартов |
| Sprint 2 (1 нед) | BL-06, BL-07, BL-08, BL-09, BL-10 | L1+L2 chunker, диалог, prompt library, кликабельные цитаты |
| Sprint 3 (1 нед) | BL-11, BL-12, BL-15 | Multi-hop, query expansion, Ollama-tuning |
| Backlog | BL-13, BL-14 | Гипотеза Canonical Cache → отдельный ADR (см. §7) |

> Порядок — рекомендация, не обязательство. Финальная очерёдность
> утверждается PO на Sprint Planning.

---

## 7. 🧠 Архитектурная гипотеза: Canonical Query Cache & Offline Dependency Graph

> **Вынесено отдельным разделом** по требованию issue #77: гипотеза имеет
> межсистемный масштаб (KB + кеш + офлайн-пайплайн) и подлежит
> формализации **в отдельном ADR** после валидации базовых метрик
> (Hit Rate@K, F1) на спринтах 1–2.

### 7.1 Переформулировка предложения PO

| Подсистема | Что предлагается |
|-----------|-------------------|
| **Corpus-Driven Query Canonicalization** | На корпусе исторических ТЗ и новых запросов, валидированных через Human-in-the-Loop, выполнить семантическую кластеризацию (эмбеддинги + density-based clustering, DBSCAN/HDBSCAN). Каждому кластеру — канонический запрос, эталонный ответ, индекс цитат. |
| **Pre-computed Q&A Store + Freshness Validation** | При входящем запросе: проверка близости к канону (cosine ≥ 0.95) → возврат кэшированного ответа после проверки `sha256` / `version` в `source_registry.csv` (см. CONCEPT §6.6). Изменился источник — инвалидируем запись и катим полный RAG-пайплайн. |
| **Offline KB Dependency Graph Generation** | Однократный offline-прогон через Ollama для явного извлечения зависимостей: `prerequisites`, `compatibility`, `see_also`, `version_constraints`. Результат — расширенные метаданные чанков. Cross-doc вопросы решаются предвычисленным lookup, а не runtime multi-hop. |

### 7.2 Почему отдельный ADR

- Меняет контракт хранения метаданных и добавляет offline-этап в индексацию.
- Влияет на `source_registry.csv` (NFR-07) и semantics инвалидации.
- Требует переоценки рисков (R-02 «Устаревание KB», R-09 «Prompt-injection из KB»).
- На статусе BL-13 / BL-14 — гипотеза. Перевод в Decision требует:
  - PoC по BL-12 (Query Expansion) и BL-11 (multi-hop) — баенчмарк показывает,
    что offline-граф даёт лучший trade-off `cost × latency × recall`.
  - Утверждённый Golden Set (BL-05) с категорией `cross_doc`.

### 7.3 Ожидаемые KPI (для будущего ADR)

| Метрика | Baseline (после P0) | Цель гипотезы | Источник |
|---------|---------------------|----------------|----------|
| Cache hit rate | 0 % | ≥ 30 % на ТЗ-корпусе | BL-13 PoC |
| Cross-doc Context Recall | ~baseline | +20 % к multi-hop | BL-14 PoC |
| p95 latency на cache-hit | — | ≤ 1 с | BL-13 KPI |
| Инвалидация при обновлении KB | n/a | ≤ 24 ч (NFR-07) | `source_registry.csv` |

> Гипотеза признана перспективной для снижения latency/cost и повышения
> консистентности. **Условие старта PoC** — наличие зелёного спринта 1
> (BL-01..BL-05, BL-16) и согласия PO на бюджет offline-прогона Ollama.

---

## 8. 📄 Связанная документация для обновления

Перечень файлов, которые **обязаны быть синхронизированы** при переходе
бэклога в статус `Accepted`. До этого момента файлы не модифицируются.

| Файл | Что обновить | Обоснование | Связанный BL |
|------|--------------|-------------|--------------|
| [`docs/CONCEPT.md`](../CONCEPT.md) §6.2 «Компоненты», п. 2 | Параметры чанкинга `200–300 / 50` → `512 / 64` с диапазоном `[384, 768]` | Секционная структура SaaS-мануалов (`docs/RAG_OPTIMIZATION_ANALYSIS.md` §3.1); 512 — sweet spot bge-m3 | BL-06, BL-16 |
| [`docs/CONCEPT.md`](../CONCEPT.md) §5 НФТ (NFR-02) | Цитируемость на MVP временно `≥ 80 %`, на Pilot `≥ 95 %` (cм. §1) | Снижение барьера для запуска Pilot без потери конечной цели | BL-02, BL-09 |
| [`docs/CONCEPT.md`](../CONCEPT.md) §6.2, п. 4 | Уточнить, что HybridRetriever используется в production-пути UI (не только в CLI) | Закрывает Проблему №3 анализа | BL-01 |
| [`docs/CONCEPT.md`](../CONCEPT.md) §8.1.2 | Добавить ссылку на [`ADR-003 (Concept)`](../ADR/003-multi-agent-orchestration-draft.md) и триггеры перехода к мультиагентной схеме | Стратегическое расширение из issue #77 | BL-13, BL-14, ADR-003 |
| [`docs/standards/embedding-model.md`](../standards/embedding-model.md) §5 | Добавить `DEFAULT_CHUNK_SIZE = 512`, `DEFAULT_CHUNK_OVERLAP = 64`, `MIN_CHUNK_SIZE = 384`, `MAX_CHUNK_SIZE = 768` | Параметры, упомянутые в анализе §3.1 как guardrails | BL-06, BL-16 |
| [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) Consequences + Triggers for Revision | Дополнить раздел Consequences (Metadata Enrichment) и Triggers (включение `MULTIHOP_ENABLED=true`) | Прозрачное отражение изменений в архитектурном решении | BL-02, BL-10, BL-11 |
| [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) | `chunk_size: 512`, `chunk_overlap: 64`; добавить `min_chunk_size`, `max_chunk_size`, опциональные `expand_neighbors`, `multihop_enabled`, `strict_rag_mode` | Привести конфиг к целевым значениям L1; флаги для BL-03 / BL-11 / L3 | BL-03, BL-06, BL-11, BL-16 |
| [`prompts/prompt_changelog.md`](../../prompts/prompt_changelog.md) | Запись о добавлении `system_rag_v1.md`, `system_rag_reflection_v1.md`, `system_rag_query_expansion_v1.md` | Прозрачное версионирование промптов (CONCEPT §6.5) | BL-08 |
| [`CHANGELOG.md`](../../CHANGELOG.md) | Запись `BREAKING (KB schema)`: переиндексация под новые `chunk_size`, схему метаданных | KB-схема меняется не обратно-совместимо | BL-02, BL-06 |

---

## 9. ✅ Критерии приёмки (Definition of Done)

- [ ] Файл `docs/backlog/2026-05-17_backlog_rag-optimization_v1.md` создан и соответствует [`naming-convention.md`](../standards/naming-convention.md) v1.1 (тип `backlog`).
- [ ] Бэклог содержит **все** задачи P0–P2 без дубликатов и внутренних противоречий (см. §§3–5).
- [ ] Каждая задача имеет: контекст, проблему, решение, оценку усилий и триггеры готовности.
- [ ] Архитектурная гипотеза (Canonical Cache + Offline Dependency Graph) вынесена отдельным разделом §7 для последующего ADR.
- [ ] Раздел §8 явно перечисляет файлы, требующие синхронизации, с обоснованием расхождений.
- [ ] Статус документа `Draft → Review`, владелец ревью — Product Owner.
- [ ] Файл готов к ревью PO **перед стартом Sprint 1**. Кодовые изменения не выполняются до `Accepted`.
- [ ] Создан черновик [`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md) (Status: Concept) — см. §10.

---

## 10. Связь со стратегическим расширением (Pilot → Enterprise)

Бэклог P0–P2 — **фундамент**. Стратегические направления, упомянутые в
issue #77 (мультиагентная оркестрация, анализ рыночного спроса через ТЗ),
**не модифицируют** этот бэклог и **не блокируют** Sprint 1–2. Они
зафиксированы черновиком в [`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md)
со статусом `Concept`.

**Триггер перехода к мультиагентной схеме** (зеркалится в CONCEPT §8.1.2):
- F1 ≥ 0.85 на Golden Set (см. NFR-01, BL-05),
- Цитируемость ≥ 95 % (NFR-02, после BL-02 + BL-09),
- Готовность веб-шлюза вместо Streamlit,
- Утверждение PO бюджета на оркестратор и offline-агентов.

---

## 11. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-17 | Первая версия согласованного бэклога: P0 (BL-01..BL-05, BL-16), P1 (BL-06..BL-10), P2 (BL-11..BL-15). Архитектурная гипотеза Canonical Cache + Offline Dependency Graph вынесена в §7 для последующего ADR. Привязка к [issue #76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76), CONCEPT §§4–6 и §8.1.2, ADR-001, ADR-003 (Concept). |
