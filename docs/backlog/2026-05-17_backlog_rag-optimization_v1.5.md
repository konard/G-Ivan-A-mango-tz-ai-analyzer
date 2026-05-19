# 📦 Бэклог оптимизации RAG-пайплайна (P0–P2) — v1.5

> Версионируемый реестр задач перехода от MVP-реализации RAG к Pilot-ready
> архитектуре по результатам [RAG_OPTIMIZATION_ANALYSIS.md](../RAG_OPTIMIZATION_ANALYSIS.md)
> (issue [#76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76))
> и параллельной правки команды (issue [#83](https://github.com/G-Ivan-A/clarify-engine-ai/issues/83)).
>
> Документ не модифицирует код. Кодовые изменения и обновления связанной
> документации стартуют **только после статуса Accepted** и утверждения
> Product Owner.

## 🗂 Метаданные
- **Дата:** 2026-05-20
- **Версия:** v1.5
- **Предыдущая версия:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md`](2026-05-17_backlog_rag-optimization_v1.4.md).
- **Автор:** konard (AI issue solver, по [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182))
- **Статус:** Draft → Review
- **Владелец ревью:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Связанные документы:**
  - [`docs/RAG_OPTIMIZATION_ANALYSIS.md`](../RAG_OPTIMIZATION_ANALYSIS.md) — источник рекомендаций (issue [#76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76)).
  - [`docs/CONCEPT.md`](../CONCEPT.md) v2.3 §§ 4–6 (FR/НФТ, архитектура), §6.2 (компоненты), §6.7 (обработка ошибок LLM), §7 (риски), §8.1.2 (Пилот), §10 (открытые вопросы).
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — гибридный поиск BM25 + Dense + RRF, Triggers for Revision.
  - [`docs/ADR/002-export-schema-extension.md`](../ADR/002-export-schema-extension.md) — расширение схемы экспорта (пост-пилот, multi-format compatibility).
  - [`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md) v1.1 §4 (Security & Compliance — §4.1 prompt-injection mitigation, §4.3 log sanitization), §5 (Границы / Non-scope), §6 Negative (R-09 prompt-injection из KB) — стратегический контекст и поверхность атаки.
  - [`docs/standards/embedding-model.md`](../standards/embedding-model.md), [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) — параметры чанкинга и vector store.
  - [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 — стандарт именования (тип `backlog`, версия `v1.5`).
  - [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) — отдельная ветка бэклога BL-50..BL-56 по результатам пилотного тестирования на АРМ (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)).
  - [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md) — результаты BL-47, резервирует BL-48 (installer) и BL-49 (cloud).
  - [`docs/standards/export-markup.md`](../standards/export-markup.md) — единая схема разметки результата (§12 / BL-27).
  - [`docs/analysis/2026-05-17_analysis_tz-structure_samples.md`](../analysis/2026-05-17_analysis_tz-structure_samples.md) — анализ структуры **Корпуса требований** и матрица изменений под `.docx`-поддержку (issue [#79](https://github.com/G-Ivan-A/clarify-engine-ai/issues/79)).
- **Связанные Issues:** [#76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76), [#77](https://github.com/G-Ivan-A/clarify-engine-ai/issues/77), [#79](https://github.com/G-Ivan-A/clarify-engine-ai/issues/79), [#83](https://github.com/G-Ivan-A/clarify-engine-ai/issues/83), [#178](https://github.com/G-Ivan-A/clarify-engine-ai/issues/178), [#180](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180), [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182).

### Терминология (договорённость PO, действует с v1.3)
- **Корпус требований** — устоявшийся в проекте «ТЗ» (тендерное техническое задание) как входной артефакт. В этом документе используется термин **Корпус требований** при описании задач, артефактов и метрик; при цитировании внешних документов (`CONCEPT.md`, `RAG_OPTIMIZATION_ANALYSIS.md`, ADR) сохраняется исходный термин «ТЗ» во избежание расхождения цитат.
- **Чанкинг** — целевая схема `chunk_size = 512`, `overlap = 64` c guardrails `min=384`, `max=768` (см. [`docs/standards/embedding-model.md`](../standards/embedding-model.md), [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml), backlog BL-06, BL-32). Старое окно «200–300 / 50» сохраняется в [CONCEPT §6.2](../CONCEPT.md) до синхронизации BL-32 — это **признанный временный рассинхрон**, явно зафиксированный в §8 настоящего документа.

---

## 0. Validation Report (по [issue #83](https://github.com/G-Ivan-A/clarify-engine-ai/issues/83))

> Раздел добавлен в v1.3. Подтверждает закрытие всех 8 пунктов чек-листа из issue #83 и фиксирует diff относительно v1.1.

### 0.1. Закрытие чек-листа валидации (8/8)

| # | Проблема v1.1 | Действие в v1.3 | Где в документе |
|---|----------------|------------------|------------------|
| 1 | BL-02 и BL-06 требуют раздельного reindex | BL-06 получил `depends_on: [BL-02]`; §6 Sprint Planning явно объединяет шаги в «Reindex & Metadata Enrichment Window» (один reindex после BL-02 → инкрементальный reindex после BL-06 с проверкой инварианта схемы метаданных) | §3 (BL-02), §4 (BL-06), §6 |
| 2 | BL-16 меняет стандарты раньше, чем BL-06 меняет код | BL-16 расщеплён на **BL-16a** (P0: метаданные + STRICT_MODE + маскирование, обновление CONCEPT §5/§7 и `embedding-model.md` §5 в части flags) и **BL-32** (P1: синхронизация `chunk_size=512`, `overlap=64`, guardrails — выходит **после** BL-06) | §3 (BL-16a), §4 (BL-32) |
| 3 | Отсутствует `depends_on` у BL-10 (Parent Retrieval) | BL-10 получил `depends_on: [BL-02, BL-06]`. Добавлено runtime-условие приёмки: schema-check метаданных перед стартом коллекции `parents`/`children` | §4 (BL-10) |
| 4 | Отсутствует CI для Golden Set | Добавлена подзадача **BL-05.1** «CI smoke-job `rag-eval-smoke` ≤ 2 мин, GitHub Action на 5-Q подвыборке + stub-LLM» | §3 (BL-05, BL-05.1) |
| 5 | BL-09 отложен в P1, но NFR-02 требует ≥ 80 % на MVP | Базовый рендер `file://` + `#page=` перенесён в **P0** как BL-09. S3 / Streamlit static-serve остаётся в P1 как **BL-09.1** | §3 (BL-09), §4 (BL-09.1) |
| 6 | Не отражены рекомендации параллельной команды | Добавлены три новые задачи: **BL-22** (Temperature lock + decoding parameters), **BL-23** (Log sanitization), **BL-24** (Lightweight faithfulness gate) | §3 (BL-22, BL-23), §5 (BL-24) |
| 7 | Трассировка к ADR-003 §4 (Security) | §8 содержит явную строку «ADR-003 §4 — Security & Compliance»; BL-23 ссылается на ADR-003 §4.1 (prompt-injection mitigation) и §4.3 (log sanitization, `sanitize_for_log()`) как на собственный архитектурный контекст; §5 (Non-scope) фиксирует границу R-09 на offline-агентов | §8 |
| 8 | Проверка покрытия FR/НФТ | Добавлен §11 «Матрица покрытия FR/НФТ ↔ BL» с явной строкой на каждую FR-01..FR-08 и NFR-01..NFR-09 | §11 |

### 0.2. Добавленные / удалённые / переименованные BL

| Действие | Старый ID | Новый ID | Обоснование |
|---|---|---|---|
| Переименование | `BL-16` | `BL-16a` | Часть P0: синхронизация стандартов метаданных, STRICT_MODE, маскирования (закрывает чек-лист #2, часть 1). |
| Добавление | — | `BL-32` | Часть P1: синхронизация `chunk_size = 512`, `overlap = 64`, guardrails в `CONCEPT §6.2`, `embedding-model.md` §5, `embedding_config.yaml` (закрывает чек-лист #2, часть 2). |
| Добавление | — | `BL-05.1` | CI Golden Set smoke-job (чек-лист #4). |
| Перенос | `BL-09` (P1) | `BL-09` (P0, базовый рендер) | Перенос базового рендера цитат в P0 для NFR-02 ≥ 80 % на MVP (чек-лист #5). |
| Добавление | — | `BL-09.1` (P1) | S3 / Streamlit-static-serve как Pilot-ready вариант (чек-лист #5). |
| Добавление | — | `BL-22` | Temperature lock + decoding parameters (`temperature=0.1`, `top_p=0.9`, `seed`) — рекомендация параллельной команды (чек-лист #6). |
| Добавление | — | `BL-23` | Log sanitization: маскирование чувствительных данных в JSON-логах FR-08 + редактирование PII в `rag_eval`-отчётах (чек-лист #6, ADR-003 §4.3 Log sanitization, §5 Non-scope offline-агентов). |
| Добавление | — | `BL-24` | Lightweight faithfulness gate в `evaluate_rag.py` (n-gram-overlap, без RAGAS) — рекомендация параллельной команды (чек-лист #6). |
| Перенумерация | `BL-19` | `BL-27` | Единая схема разметки результата (`export-markup.md`) остаётся P0 Pending. |
| Перенумерация | `BL-20` | `BL-28` | Multi-format Export (`ExportRouter`) остаётся P0 Pending и зависит от BL-27. |
| Перенумерация | `BL-21` | `BL-29` | UI-селекторы экспорта остаются P0 Pending и зависят от BL-28. |
| Перенос / отложено | `BL-13` (old) | `BL-30` | Canonical Query Cache переведён в On Hold до ADR и проверки на Golden Set. |
| Добавление | — | `BL-31` | LLM-нормализация структуры DOCX, Research; зависит от результатов BL-28. |
| Перенос / отложено | `BL-16b` | `BL-32` | Синхронизация конфигов выделена как tech debt, не блокирующий BL-27..BL-29. |

> **Сквозная нумерация (V-10) сохранена.** Следующий свободный ID после v1.3 — **BL-33**.

### 0.3. Карта зависимостей (depends_on graph, текстовая нотация)

```
BL-27 (export-markup) ──► BL-28 (ExportRouter) ──► BL-29 (UI selectors)
                                            │
                                            └──► BL-31 (LLM-normalization, optional)

BL-30 (Canonical Cache) — независима, требует отдельного ADR
BL-32 (Config Sync) — независима, tech debt
```

Граф **ацикличен**, «висячих» зависимостей нет (по результатам валидации §10 этого документа).

### 0.4. Подтверждение покрытия

- **FR/НФТ:** каждая FR-01..FR-08 и NFR-01..NFR-09 имеет ≥ 1 связанную BL — см. §11 «Матрица покрытия».
- **RAG_OPTIMIZATION_ANALYSIS.md §12.1:** все 16 рекомендаций §12.1 покрыты задачами P0–P2 (включая Faithfulness `#15` → BL-24, Semantic Metadata `#13` через BL-14, Neighbour expansion `#14` отслеживается как Out-of-Scope MVP с явной отметкой в §5).
- **Рекомендации параллельной команды:** Temperature lock → BL-22, Log sanitization → BL-23, Lightweight faithfulness gate → BL-24 (все три явно перечислены в §3/§5).
- **ADR-003 §4 (Security & Compliance):** §8 содержит строку с явной привязкой BL-23 → ADR-003 §4.3 (Log sanitization); §5 (Non-scope) фиксирует, что выход за границу offline-агентов (R-09 prompt-injection из KB) остаётся вне MVP.

### 0.5. Дифф-сводка относительно v1.1

| Раздел документа | До (v1.1) | После (v1.3) |
|---|---|---|
| Шапка | Версия v1.1, без отдельного Validation Report | Версия v1.2; §0 Validation Report; терминология «Корпус требований» |
| §3 P0 | BL-01, BL-02, BL-03, BL-04, BL-05, BL-16 | + **BL-05.1**, **BL-09** (базовый рендер), **BL-16a** (вместо BL-16), **BL-22**, **BL-23** |
| §4 P1 | BL-06, BL-07, BL-08, BL-09, BL-10 | BL-06 (с `depends_on`), BL-07, BL-08, BL-09.1 (бывший BL-09 «S3»), BL-10 (с `depends_on`), **BL-32** |
| §5 P2 | BL-11, BL-12, BL-13, BL-14, BL-15 | + **BL-24** (faithfulness gate); явная отметка Neighbour expansion (`#14` анализа) как Out-of-Scope MVP; Canonical Cache перенесён в BL-30 |
| §6 Sprint порядок | Без unified reindex-окна | Введено «Reindex & Metadata Enrichment Window» (объединение reindex-этапов BL-02 → BL-06) |
| §8 Связанная документация | Без ADR-003 §4 | + строка «ADR-003 v1.1 §4 (Security & Compliance)» с привязкой BL-23 → §4.3 (Log sanitization, `sanitize_for_log()`); + строка `configs/llm_config.yaml` (BL-22, BL-23); + явный flag о временном рассинхроне CONCEPT §6.2 vs BL-06 до закрытия BL-32 |
| §9 DoD | Без CI Golden Set, без ADR-003 §4 | Дополнен пунктами CI smoke-gate (BL-05.1), §11 FR/НФТ-матрицы, ADR-003 §4 трассировки, явных `depends_on/priority/effort` у каждой задачи |
| §11 (новый) | — | **Матрица покрытия FR/НФТ ↔ BL** |
| §12 (бывший §12 #79) | BL-18..BL-21 | BL-18 сохранён; BL-19..BL-21 перенумерованы в BL-27..BL-29 |
| §11 (бывший «История изменений») | — | Переименован в §13 «История изменений», добавлена строка v1.3 |

### 0.6. Актуальный статус задач (v1.5)

| ID | Задача | Приоритет | Статус | Зависимости | Обоснование | DoD |
|----|--------|-----------|--------|-------------|-------------|-----|
| BL-30 | Canonical Query Cache | P2 | ⏸ DEFERRED | BL-05 | Требует отдельного ADR и изолированного Track 2 backlog | PoC и Gate 0 выполнены в [`2026-05-19_track2-cache-validation_v2.md`](2026-05-19_track2-cache-validation_v2.md) |
| BL-31 | LLM-нормализация DOCX | P2 | ⏳ Waiting | BL-28 | Исследование атомарности DOCX после стабилизации multi-format export | Решение о старте принято после проверки BL-28 на реальных `.docx` |
| BL-32 | Config Sync | P1 | ⏳ Waiting | BL-06 | Tech debt по синхронизации chunking-стандартов и конфигов | CONCEPT, ADR-001, `embedding-model.md`, `embedding_config.yaml` синхронизированы |
| BL-46 | Backlog branch update to v1.4 | P1 | ✅ Closed | BL-34..BL-45 | Заархивировать завершённые задачи Sprint 3 и добавить BL-47 | Файл v1.4 создан, архив Sprint 3 добавлен, CHANGELOG обновлён ([PR #179](https://github.com/G-Ivan-A/clarify-engine-ai/pull/179)) |
| BL-47 | Research: ARM Installer, Cloud TZ Access & Documentation Update Flow | P1 | ✅ Closed | BL-43, BL-45 | Исследование упрощённой установки, облачного доступа к ТЗ и обновления КБ для не-технических пользователей (пилот) | Research note [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md) с вариантами installer/cloud/update-flow, рисками NFR-04/NFR-05 и рекомендацией PO ([PR #181](https://github.com/G-Ivan-A/clarify-engine-ai/pull/181)) |
| BL-50 | `.env` startup validation | P0 | 📝 New | — | Невалидный/отсутствующий `.env` приводит к падению Streamlit без понятного сообщения (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §1) | Описание и Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.1 |
| BL-51 | Auto-detect Ollama installation path | P1 | 📝 New | BL-50 | На АРМ Windows установка Ollama по умолчанию в `%LOCALAPPDATA%\Programs\Ollama`, текущий код ожидает PATH (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §2) | Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.2 |
| BL-52 | Sync `.env.example` ↔ runbook (OLLAMA_MODEL) | P0 | 📝 New | — | Рассинхрон: `.env.example` указывает `qwen2.5:7b-instruct-q4_K_M`, runbook §1.4 — `qwen2.5:7b` (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §3) | Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.3 |
| BL-53 | Streamlit `.env` cache documentation | P2 | 📝 New | BL-50 | После правки `.env` нужен явный рестарт Streamlit; в runbook это не зафиксировано (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §4) | Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.4 |
| BL-54 | Restore file uploader in «📊 Анализ ТЗ» mode | P0 | 📝 New | BL-29, BL-41 | Регресс BL-41: `src/ui/app.py` не содержит `st.file_uploader`, что блокирует user guide §2 и пилотный сценарий (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §5) | Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.5 |
| BL-55 | First-response UX (queue / progress messaging) | P2 | 📝 New | BL-54 | Первый запрос на холодном Ollama занимает 30–60 с без визуального прогресса, БА воспринимает как зависание (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §6) | Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.6 |
| BL-56 | `datetime.utcnow()` → timezone-aware (Python 3.14) | P2 | 📝 New | — | `DeprecationWarning` в `knowledge_base/indexing/build_index.py:116`, дополнительно затрагивает логи `pipeline.py` (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), §7) | Acceptance — в [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.7 |

> **Сквозная нумерация (V-10) сохранена.** Следующий свободный ID после v1.5 — **BL-57**.

---

## 1. Контекст и цель

Текущий RAG-путь `similarity_search → concat → LLM` (см. `src/ui/app.py:97-107`)
обеспечивает базовый MVP, но не покрывает требования к точности, цитируемости
и устойчивости к кросс-документным зависимостям, зафиксированные в
[`docs/CONCEPT.md`](../CONCEPT.md) §§4–6 и [ADR-001](../ADR/001-rag-architecture.md).

**Цель бэклога:** формализовать дорожную карту перехода MVP → Pilot-ready
без переписывания архитектурного фундамента, в три волны приоритетов
(P0 → P1 → P2) с явной привязкой каждой задачи к источнику требований и с
понятным графом `depends_on` (см. §0.3).

**Что меняется относительно НФТ MVP:**
- Целевая планка цитируемости на MVP-окончании временно снижается с
  `≥ 95 %` до `≥ 80 %` (см. NFR-02), чтобы не блокировать ранний выпуск
  Pilot. **Базовый рендер кликабельных цитат `file://` + `#page=` подключается
  на MVP (BL-09, P0)** для соответствия NFR-02 ≥ 80 % на MVP; S3 /
  Streamlit-static-serve откладывается в P1 как BL-09.1. Возврат к `≥ 95 %`
  — Exit Criterion Пилота (см. [CONCEPT §8.1.2](../CONCEPT.md#812-пилот-3–5-недель)).
- Целевые F1 и резидентность не меняются.
- **Мы не понижаем приоритет качества поиска** — наоборот, P0-блок целиком
  адресует hybrid retrieval, метаданные, STRICT_MODE, маскирование,
  temperature lock и log sanitization, что даёт измеримый рост recall и
  контроль галлюцинаций.

**Соответствие стандарту наименования:** имя файла —
`docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md` (см.
[`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1,
§3.2). Дата файла = дате первой публикации (`2026-05-17`, см. §3.1
naming-convention.md); MINOR-версия `v1.4` отражает BL-46-актуализацию по
issue #178 без изменения архитектурных выводов.

---

## 2. Валидация против RAG_OPTIMIZATION_ANALYSIS.md

| Срез анализа (§§) | Наша задача | Закрывает |
|------------------|-------------|-----------|
| §2.2 Фрагментация контекста | BL-06 (chunker L1), BL-10 (Parent L2), BL-32 (синхронизация стандартов) | Проблема P1 |
| §2.3 Минимальные метаданные | BL-02 (page/section/product), BL-09 (кликабельные цитаты, базовый рендер), BL-09.1 (S3 / static-serve) | Проблема P2 |
| §2.4 Pure-dense в UI | BL-01 (HybridRetriever в production) | Проблема P3 |
| §2.5 Нет multi-hop | BL-11 (флаг `MULTIHOP_ENABLED=false`), BL-12 (Query Expansion) | Проблема P4 |
| §2.6 Stateless UI | BL-07 (`st.session_state` + Last-6 + summarization) | Проблема P5 |
| §2.7 Слабое grounding | BL-03 (STRICT_MODE), BL-04 (маскирование RAG-канала), BL-08 (prompt library), BL-22 (temperature lock), BL-24 (faithfulness gate) | Проблема P6 |
| §2.8 Нет RAG-метрик | BL-05 (Golden Set + `evaluate_rag.py`), BL-05.1 (CI smoke-job ≤ 2 мин) | Проблема P7 |
| §7.3 Faithfulness check | BL-24 (lightweight n-gram-overlap gate в `evaluate_rag.py`) | Рекомендация анализа #15 (P2) |
| §9 Ollama-оптимизация | BL-15 (квантование, `keep_alive`, ThreadPool) | Locality |
| §3.1 Идея Canonical Cache | BL-30 (гипотеза → отдельный ADR), BL-14 (Offline Dependency Extraction) | Стратегия |

**Покрытие:** 16/16 рекомендаций §12.1 анализа уложены в P0–P2 без потерь
(включая faithfulness `#15` → BL-24 и semantic metadata `#13` → BL-14).
Рекомендация `#14` (Neighbour expansion / L3) явно сохраняется как
**Out-of-Scope MVP** (см. §5 примечание) и переоценивается после BL-10.
Не вошедшие в анализ блоки (cross-encoder reranker, GraphRAG, fine-tuning
bge-m3) явно вынесены в §14 анализа как Out of Scope и **не добавляются**
в этот бэклог.

---

## 3. Бэклог P0 (MUST для подготовки Pilot)

| ID | Задача | depends_on | priority | effort | Контекст | Проблема | Решение | Триггеры готовности |
|----|--------|-----------|----------|--------|----------|----------|---------|----------------------|
| **BL-01** | Подключение HybridRetriever в production-путь UI | — | P0 | S (1 д) | [ADR-001](../ADR/001-rag-architecture.md) требует BM25 + Dense + RRF | `src/ui/app.py:99` использует pure-dense `ChromaRetriever`, BM25-канал мёртв в живом пути | Переключить UI на `HybridRetriever` (`src/rag/retriever.py:364-510`), RRF `k=60`, top_k = 5 | Smoke-прогон Golden Set (BL-05) показывает Hit Rate@5 ≥ baseline; CI smoke-job (BL-05.1) зелёный |
| **BL-02** | Расширение метаданных чанков: `page_number`, `section_title`, `section_number`, `product` | BL-16a | P0 | M (2–3 д) | НФТ цитируемости ([CONCEPT §5 NFR-02](../CONCEPT.md#5-нефункциональные-требования-нфт)) | `knowledge_base/indexing/build_index.py:238` сохраняет только `{source, chunk_idx}` — нет привязки к страницам и разделам | Page-aware парсинг (`pypdf.PdfReader().pages`) + regex-извлечение заголовков (`\d+\.\d+\.\d+`, CAPS) + product mapping по `source_file`. **Reindex объединяется с reindex после BL-06** в окне «Reindex & Metadata Enrichment» (см. §6) | После reindex `≥ 95 %` чанков имеют непустые `page_number` и `section_title`; schema-check метаданных проходит без warning |
| **BL-03** | STRICT_MODE при пустом / нерелевантном контексте | — | P0 | S (0.5 д) | [CONCEPT §7 R-01](../CONCEPT.md#7-управление-рисками) (защита от галлюцинаций) | При `top_k`-выдаче без совпадений или `max_score < threshold` LLM «дорисовывает» из весов | Блокировать LLM-вызов при `len(context)==0` или `max_score < STRICT_MIN_SCORE`; возвращать детерминированный fallback. Переменная `STRICT_RAG_MODE=true` в проде | Регрессионный тест: запрос вне домена возвращает «не найдено» без LLM-вызова |
| **BL-04** | Маскирование RAG-контекста перед LLM (`mask=True` в `generate_rag_response`) | — | P0 | S (0.5 д) | [NFR-04/NFR-05](../CONCEPT.md#5-нефункциональные-требования-нфт) (резидентность, 0 утечек), R-03 | `LLMClient.generate_rag_response` сейчас НЕ применяет `mask_text()` — RAG-канал течёт | Внедрить `mask=True` по умолчанию; покрыть `tests/test_masking.py` сценарием RAG-вызова | Аудит исходящего HTTP-трафика тестов — 0 совпадений regex чувствительных данных |
| **BL-05** | Создание `test_data/rag_golden_set.json` (≥ 30 Q/A) + `scripts/evaluate/evaluate_rag.py` | — | P0 | M (2 д) | [NFR-01](../CONCEPT.md#5-нефункциональные-требования-нфт), отсутствие RAG-метрик | Нет способа количественно валидировать улучшения; `evaluate_quality.py` покрывает только классификацию | 10 ручных кейсов (БА) + 20 LLM-черновиков (валидация PO). Метрики `Hit Rate@K`, `MRR`, `Context Recall` чистым Python — без RAGAS-зависимости. Конструкция отчёта совместима с BL-24 (faithfulness gate) | `evaluate_rag.py` отдаёт JSON-отчёт; локальный прогон укладывается в `< 5 мин` для 50 Q |
| **BL-05.1** | CI smoke-job `rag-eval-smoke` (GitHub Action, ≤ 2 мин) | BL-05 | P0 | S (0.5 д) | Анализ §8.4 / [`docs/analysis`](../analysis/) (CI gates); чек-лист валидации #4 | Без CI Golden Set регрессии в retrieval-цепочке не ловятся между PR | Workflow `.github/workflows/rag-eval-smoke.yml`: запуск `python scripts/evaluate/evaluate_rag.py --golden test_data/rag_golden_set.json --subset 5 --top-k 5 --llm stub --report reports/rag-smoke.json`. Время выполнения ≤ 2 мин; падение CI при отсутствии `expected_sources` в top-5 ≥ 80 % случаев; артефакт `rag-smoke.json` сохраняется как build artifact | Workflow зелёный на PR в `main`; время выполнения ≤ 2 мин; артефакт публикуется |
| **BL-09** | Кликабельные цитаты `[source.pdf, стр. N, §X.Y]` в UI — **базовый рендер `file://` + `#page=`** | BL-02 | P0 | S (0.5 д) | [NFR-02](../CONCEPT.md#5-нефункциональные-требования-нфт) (цитируемость ≥ 80 % на MVP), [CONCEPT §7](../CONCEPT.md#7-управление-рисками) | UI рендерит только имя файла — БА не может перейти к источнику; перенос в P1 нарушает NFR-02 ≥ 80 % на MVP | Markdown-ссылки `[source.pdf, стр. N](file:///abs/path/to/kb/<source>#page=N)` + рендер из метаданных BL-02. Локальный путь работает в Streamlit-сценарии single-user MVP. Pilot-режим (S3 / Streamlit-static-serve) выносится в BL-09.1 (P1) | Минимум 1 из 3 тест-цитат на каждом ответе кликабельна и открывает PDF на нужной странице (local Streamlit); NFR-02 ≥ 80 % на Golden Set |
| **BL-16a** | Синхронизация документации под стандарты метаданных, STRICT_MODE, маскирования | — | P0 | S (1 д) | Чек-лист валидации #2 (часть 1); зависимости BL-02/BL-03/BL-04 нуждаются в синхронизированных стандартах ДО изменения кода | Стандарты должны быть готовы **раньше** кода: формат `page_number`/`section_title` в `embedding-model.md` §5, флаг `STRICT_RAG_MODE` в `embedding_config.yaml`, обязательное маскирование RAG-канала в [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md) | Обновить [`docs/standards/embedding-model.md`](../standards/embedding-model.md) §5 (метаданные), [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) Consequences (Metadata Enrichment) и Triggers, [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) (флаги `strict_rag_mode`, схема метаданных). **НЕ меняет `chunk_size`** — это делается в BL-32 после BL-06 | Все три файла увеличивают версию; schema-check `embedding_config.yaml` проходит локально; PR-ревью BL-02/BL-03/BL-04 ссылается на новые версии стандартов |
| **BL-22** | Temperature lock + decoding parameters | — | P0 | S (0.5 д) | Рекомендация параллельной команды (см. issue #83 чек-лист #6); ADR-001 не фиксирует параметры декодирования | LLMClient не закрепляет детерминированные параметры декодирования → нестабильность ответов на регрессионных прогонах (BL-05), плавающий `Confidence`, ложные расхождения F1 | В [`configs/llm_config.yaml`](../../configs/llm_config.yaml) добавить блок `decoding:` с `temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024` (override per-provider при необходимости). `LLMClient` читает блок при каждом вызове и **запрещает** override параметров на стороне промптов. Покрыть `tests/test_llm_client.py` сценарием «одинаковый запрос → ≥ 99 % совпадение по нормализованному ответу» | На Golden Set (BL-05) разброс F1 между двумя последовательными прогонами ≤ 1 %; параметры залогированы в FR-08 (`temperature`, `seed`, `provider_version`) |
| **BL-23** | Log sanitization (FR-08 + RAG-eval отчёты) | — | P0 | S (1 д) | Чек-лист валидации #6/#7; [CONCEPT §7 R-03](../CONCEPT.md#7-управление-рисками), NFR-05 (0 утечек); [ADR-003 v1.1 §4.3 Log sanitization](../ADR/003-multi-agent-orchestration-draft.md#43-log-sanitization-manage) (контракт `sanitize_for_log()`) и §5 Non-scope offline-агентов; §6 Negative (R-09 prompt-injection) — surface attack для логов | JSON-логи FR-08 и отчёты `evaluate_rag.py` сохраняют **исходные** тексты требований и чанков → потенциальная утечка PII / commercial-sensitive данных через файловую систему и build-artifacts CI | (1) Расширить `src/llm/masking.py` функцией `sanitize_log_record(record: dict) -> dict` (alias к контракту ADR-003 §4.3 `sanitize_for_log()`), применяющей regex-маскирование к полям `payload`, `context`, `answer`, `question`, `chunks[*].text` + замену секретов из `.env` на `***REDACTED***` + усечение `payload` до `N` КБ. (2) Подключить sanitizer как Python-`logging.Filter` в `src/pipeline.py` (`run_id`-aware). (3) Покрыть `tests/test_masking.py::test_log_sanitization_applies_to_evaluate_rag_report`. (4) Обновить [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md) разделом «Log sanitization (FR-08 + RAG-eval)» и зафиксировать ссылку на [ADR-003 §4.3](../ADR/003-multi-agent-orchestration-draft.md#43-log-sanitization-manage) | 0 совпадений regex чувствительных данных в `reports/rag-*.json` и в логах CI; тест `test_log_sanitization_applies_to_evaluate_rag_report` зелёный; контракт `sanitize_for_log()` соответствует ADR-003 §4.3 |

**Совокупная нагрузка P0:** ≈ 9–11 человеко-дней (расширена с 7–8 из v1.1
за счёт BL-05.1, BL-09 базовый рендер, BL-22, BL-23 и расщепления BL-16).
План на один Sprint с возможным переносом BL-22/BL-23 на начало Sprint 2
при дефиците ёмкости (см. §6).

---

## 4. Бэклог P1 (SHOULD для Pilot UX/качества)

| ID | Задача | depends_on | priority | effort | Контекст | Проблема | Решение | Триггеры готовности |
|----|--------|-----------|----------|--------|----------|----------|---------|----------------------|
| **BL-06** | Chunker L1: `chunk_size = 512`, `overlap = 64`, section-aware split | BL-02 | P1 | S (1 д) | Структура SaaS-мануалов MANGO OFFICE; рекомендация анализа §3.1 | Фиксированное окно 250 разрывает разделы вида «7.3.6 Настройка SSO» посередине | Увеличить окно, добавить эвристики разреза (`\n#{1,6} `, нумерованные разделы, CAPS-заголовки). **Инкрементальный reindex** объединяется с BL-02 в окне «Reindex & Metadata Enrichment» (§6). Файлы конфигов меняются только после BL-32 | Hit Rate@5 на Golden Set +10–15 % относительно baseline; schema-check метаданных не регрессирует |
| **BL-32** | Синхронизация конфигов (`512 / 64` + guardrails) | BL-06 | P1 | S (0.5 д) | Чек-лист валидации #2 (часть 2); анализ §3.1 предлагает 512; CONCEPT §6.2 фиксирует 200–300 ток. | Стандарт расходится с целевой схемой L1 — нельзя катить кодовый BL-06 без последующей синхронизации документации; синхронизация должна **следовать** за подтверждённым кодом, а не предшествовать ему (иначе расхождение стандартов и реализации) | Обновить [`docs/CONCEPT.md`](../CONCEPT.md) §6.2, [`docs/standards/embedding-model.md`](../standards/embedding-model.md) §5 (`DEFAULT_CHUNK_SIZE = 512`, `DEFAULT_CHUNK_OVERLAP = 64`, `MIN_CHUNK_SIZE = 384`, `MAX_CHUNK_SIZE = 768`), [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) (`chunk_size: 512`, `chunk_overlap: 64`, `min_chunk_size`, `max_chunk_size`), [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) Consequences | Все четыре файла увеличивают версию; запись в CHANGELOG `BREAKING (KB schema, chunk_size)`; reindex-окно согласовано с PO |
| **BL-07** | Память диалога: `st.session_state` + Last-6 + auto-summarization | — | P1 | S (1 д) | UX пилотных БА | Stateless UI: «уточни ответ» / «а что если AD внешний?» вынуждают повторять контекст | Сессионное хранилище в `src/ui/app.py`, триггер LLM-summary после 12 пар | E2E-сценарий «3 уточнения подряд» сохраняет историю до перезапуска приложения |
| **BL-08** | Prompt Library: `prompts/system_rag_v1.md`, `system_rag_reflection_v1.md`, `system_rag_query_expansion_v1.md` | — | P1 | S (1 д) | [CONCEPT §6.5](../CONCEPT.md#65-промпт-менеджмент) | Промпты в UI захардкожены, версионирование промптов невозможно | Вынести шаблоны в `prompts/`, обновить `prompts/prompt_changelog.md` | PR с промптами проходит код-ревью PO; имена соответствуют `*_v<N>.md` |
| **BL-09.1** | Кликабельные цитаты — Pilot-режим: S3 / Streamlit-static-serve | BL-09 | P1 | S (1 д) | Pilot-инфраструктура (issue анализа §13 п.3) | `file://` не работает, когда Streamlit развёрнут на сервере, а пользователь — в браузере на другой машине | Загрузка PDF в S3-совместимое хранилище **или** настройка `streamlit run --server.enableStaticServing true` + директория `static/kb/`. Метаданные источника содержат относительный URL; UI рендерит по схеме `{base_url}/{source}#page=N`. Конфиг `configs/citation_config.yaml` (новый) с `mode: file_local | static_serve | s3` | На Pilot-стенде клик по цитате открывает PDF с нужной страницы из браузера БА |
| **BL-10** | Parent Document Retrieval (L2): двухслойная индексация | BL-02, BL-06 | P1 | L (3–4 д) | Фрагментация зависимостей, рекомендация анализа §3.2 | Child-чанки точны, но LLM не хватает родительского контекста | Две коллекции: `children` (256/32) и `parents` (~512). Поиск по children → возврат parents. **Schema-check метаданных перед стартом** (исключает KeyError в рантайме при отсутствии `parent_id`) | Hit Rate@5 +15–25 % к L1; объём индекса не превышает baseline × 1.4; schema-check метаданных проходит |

**Совокупная нагрузка P1:** ≈ 7–8 человеко-дней (один Sprint).

---

## 5. Бэклог P2 (MAY — оптимизации и эксперименты)

| ID | Задача | depends_on | priority | effort | Контекст | Проблема | Решение | Триггеры готовности |
|----|--------|-----------|----------|--------|----------|----------|---------|----------------------|
| **BL-11** | Multi-hop iterative retrieval (`max_hops=2`) под флагом `MULTIHOP_ENABLED=false` | BL-01, BL-05 | P2 | M (2 д) | Cross-doc зависимости («SSO + AD», «лимиты + тариф») | Один проход не достаёт второй раздел; reflection-loop отсутствует | Reflection-LLM (`system_rag_reflection_v1.md`); выключен по умолчанию из-за `+latency`/`+cost` | A/B на Golden Set категории `cross_doc`: +Context Recall ≥ 10 %, p95 latency ≤ +50 % |
| **BL-12** | Query Expansion (3 переформулировки) | BL-01 | P2 | S (1 д) | Терминологические вариации (ВАТС / VPBX) | Разные формулировки дают разный dense-результат | LLM-синонимы параллельно основному запросу, фьюж выдачи через RRF | На запросах с синонимами Hit Rate@5 не падает, MRR не ухудшается |
| **BL-30** | Canonical Query Cache & Clustering (гипотеза) | BL-05 | P2 | M (2–3 д) | Снижение `cost` / `latency` на повторяющихся запросах | Повторяющиеся вопросы каждый раз грузят LLM | Кэш канонических ответов (cosine ≥ 0.95) + валидация `sha256` источников. Детализация в отдельном ADR | ADR-проект готов; PoC показывает hit-rate кэша ≥ 30 % на корпусе Корпуса требований |
| **BL-14** | Offline Dependency Extraction (regex + local LLM) | BL-02 | P2 | M (2–3 д) | Cross-ссылки в документации MANGO OFFICE | Runtime multi-hop дорог; зависимости можно «препроцессить» | Один offline-прогон Ollama для извлечения `prerequisites`, `see_also`, `related_sections` в метаданные чанков | После прогона `≥ 70 %` чанков с маркерами «см. раздел» получают непустой `related_sections` |
| **BL-15** | Ollama: квантование `q4_K_M`, `keep_alive`, ThreadPool batch | — | P2 | S (1 д) | Локальный инференс, рекомендация анализа §9 | Синхронные вызовы блокируют eval-прогоны (50 Q × ~10 с) | Явное `q4_K_M`, `num_ctx=4096`, `keep_alive=10m`, `ThreadPoolExecutor(max_workers=4)` для скриптов | `evaluate_rag.py` на 50 Q укладывается в ≤ 50 % текущего wall-clock |
| **BL-24** | Lightweight faithfulness gate (n-gram overlap) в `evaluate_rag.py` | BL-05 | P2 | S (1 д) | Рекомендация параллельной команды (issue #83 чек-лист #6); [analysis §7.3 / #15](../RAG_OPTIMIZATION_ANALYSIS.md#73-faithfulness-check-post-generation) | Метрика «честности» ответа отсутствует; LLM-as-judge (RAGAS) дорогой и требует внешнего API | Реализовать `faithfulness_check(answer, chunks, min_overlap=8)` (n-gram overlap, чистый Python). Добавить отдельную колонку `faithfulness_ngram` в JSON-отчёт `evaluate_rag.py`. CI smoke-job (BL-05.1) сообщает faithfulness, **не блокируя build** на MVP; на Пилоте — gate `≥ 0.7` | На Golden Set `faithfulness_ngram` рассчитывается без внешнего API; отчёт стабильно воспроизводим |

> **Out-of-Scope MVP (явная отметка):** рекомендация анализа `#14`
> «Neighbour expansion (L3)» сохраняется как **Out-of-Scope MVP** и
> переоценивается после успеха BL-10 (Parent Retrieval). Запись
> зафиксирована в этом разделе, чтобы соответствовать чек-листу #6
> «не оставлять висячих рекомендаций анализа».

**Совокупная нагрузка P2:** ≈ 9–11 человеко-дней (план — Sprint 3 + бэклог).

---

## 6. Предполагаемый порядок раскатки (для согласования)

| Sprint | Содержимое | Обязательный артефакт |
|--------|-----------|------------------------|
| Sprint 1 (1 нед) | BL-16a → BL-01, BL-02, BL-03, BL-04, BL-05 → BL-05.1, BL-09 (P0), BL-22, BL-23 | UI на hybrid + базовые метаданные + Golden Set + CI smoke-job + базовые кликабельные цитаты + temperature lock + log sanitization |
| **Reindex & Metadata Enrichment Window** (внутри Sprint 1) | BL-02 → schema-check → инкрементальный reindex; BL-06 откладывается до Sprint 2 | Объединение reindex-этапов: после BL-02 — один full reindex с обогащением метаданных; после BL-06 (Sprint 2) — повторный reindex c новым `chunk_size` |
| Sprint 2 (1 нед) | BL-06 → BL-32, BL-07, BL-08, BL-09.1, BL-10 | L1+L2 chunker (с обновлёнными стандартами), диалог, prompt library, Pilot-режим кликабельных цитат |
| Sprint 3 (1 нед) | BL-11, BL-12, BL-15, BL-24 | Multi-hop, query expansion, Ollama-tuning, faithfulness gate в evaluate_rag.py |
| Backlog | BL-30, BL-14 | Гипотеза Canonical Cache → отдельный ADR (см. §7) |

> Порядок — рекомендация, не обязательство. Финальная очерёдность
> утверждается PO на Sprint Planning. Reindex-окно требует явного
> согласования с PO на Sprint 1 (минимизировать «slim window» простоя
> поиска до 30 минут на эталонном корпусе ≤ 20 документов).

---

## 7. 🧠 Архитектурная гипотеза: Canonical Query Cache & Offline Dependency Graph

> **Вынесено отдельным разделом** по требованию issue #77: гипотеза имеет
> межсистемный масштаб (KB + кеш + офлайн-пайплайн) и подлежит
> формализации **в отдельном ADR** после валидации базовых метрик
> (Hit Rate@K, F1) на спринтах 1–2.

### 7.1 Переформулировка предложения PO

| Подсистема | Что предлагается |
|-----------|-------------------|
| **Corpus-Driven Query Canonicalization** | На корпусе исторических Корпусов требований и новых запросов, валидированных через Human-in-the-Loop, выполнить семантическую кластеризацию (эмбеддинги + density-based clustering, DBSCAN/HDBSCAN). Каждому кластеру — канонический запрос, эталонный ответ, индекс цитат. |
| **Pre-computed Q&A Store + Freshness Validation** | При входящем запросе: проверка близости к канону (cosine ≥ 0.95) → возврат кэшированного ответа после проверки `sha256` / `version` в `source_registry.csv` (см. [CONCEPT §6.6](../CONCEPT.md#66-конфигурация-нет-хардкода)). Изменился источник — инвалидируем запись и катим полный RAG-пайплайн. |
| **Offline KB Dependency Graph Generation** | Однократный offline-прогон через Ollama для явного извлечения зависимостей: `prerequisites`, `compatibility`, `see_also`, `version_constraints`. Результат — расширенные метаданные чанков. Cross-doc вопросы решаются предвычисленным lookup, а не runtime multi-hop. |

### 7.2 Почему отдельный ADR

- Меняет контракт хранения метаданных и добавляет offline-этап в индексацию.
- Влияет на `source_registry.csv` (NFR-07) и semantics инвалидации.
- Требует переоценки рисков (R-02 «Устаревание KB», R-09 «Prompt-injection из KB», см. [ADR-003 §4.1 Prompt-injection mitigation](../ADR/003-multi-agent-orchestration-draft.md#41-prompt-injection-mitigation-govern--manage) и §6 Negative consequences).
- На статусе BL-30 / BL-14 — гипотеза. Перевод в Decision требует:
  - PoC по BL-12 (Query Expansion) и BL-11 (multi-hop) — бенчмарк показывает,
    что offline-граф даёт лучший trade-off `cost × latency × recall`.
  - Утверждённый Golden Set (BL-05) с категорией `cross_doc`.

### 7.3 Ожидаемые KPI (для будущего ADR)

| Метрика | Baseline (после P0) | Цель гипотезы | Источник |
|---------|---------------------|----------------|----------|
| Cache hit rate | 0 % | ≥ 30 % на корпусе Корпуса требований | BL-30 PoC |
| Cross-doc Context Recall | ~baseline | +20 % к multi-hop | BL-14 PoC |
| p95 latency на cache-hit | — | ≤ 1 с | BL-30 KPI |
| Инвалидация при обновлении KB | n/a | ≤ 24 ч (NFR-07) | `source_registry.csv` |

> Гипотеза признана перспективной для снижения latency/cost и повышения
> консистентности. **Условие старта PoC** — наличие зелёного спринта 1
> (BL-01..BL-05.1, BL-09 P0, BL-16a, BL-22, BL-23) и согласия PO на бюджет
> offline-прогона Ollama.

---

## 8. 📄 Связанная документация для обновления

Перечень файлов, которые **обязаны быть синхронизированы** при переходе
бэклога в статус `Accepted`. До этого момента файлы не модифицируются.

| Файл | Что обновить | Обоснование | Связанный BL |
|------|--------------|-------------|--------------|
| [`docs/CONCEPT.md`](../CONCEPT.md) §6.2 «Компоненты», п. 2 | Параметры чанкинга `200–300 / 50` → `512 / 64` с диапазоном `[384, 768]` | Секционная структура SaaS-мануалов ([`RAG_OPTIMIZATION_ANALYSIS.md` §3.1](../RAG_OPTIMIZATION_ANALYSIS.md#31-уровень-1--базовая-оптимизация-should--1–2-дня)); 512 — sweet spot bge-m3. **Временный рассинхрон CONCEPT §6.2 vs `embedding_config.yaml` сохраняется до выполнения BL-32 и закрывается в Sprint 2** | BL-06, BL-32 |
| [`docs/CONCEPT.md`](../CONCEPT.md) §5 НФТ (NFR-02) | Цитируемость на MVP временно `≥ 80 %`, на Pilot `≥ 95 %` (см. §1) | Снижение барьера для запуска Pilot без потери конечной цели; базовый рендер `file://` подключается на MVP (BL-09 P0) | BL-02, BL-09 |
| [`docs/CONCEPT.md`](../CONCEPT.md) §6.2, п. 4 | Уточнить, что HybridRetriever используется в production-пути UI (не только в CLI) | Закрывает Проблему №3 анализа | BL-01 |
| [`docs/CONCEPT.md`](../CONCEPT.md) §8.1.2 | Сохранить ссылку на [`ADR-003 (Concept)`](../ADR/003-multi-agent-orchestration-draft.md) и триггеры перехода к мультиагентной схеме | Стратегическое расширение из issue #77 | BL-30, BL-14, ADR-003 |
| [`docs/standards/embedding-model.md`](../standards/embedding-model.md) §5 | Добавить `DEFAULT_CHUNK_SIZE = 512`, `DEFAULT_CHUNK_OVERLAP = 64`, `MIN_CHUNK_SIZE = 384`, `MAX_CHUNK_SIZE = 768`; зафиксировать обязательные поля метаданных `page_number`, `section_title`, `section_number`, `product`, `parent_id` (для BL-10) | Параметры, упомянутые в анализе §3.1 как guardrails; схема метаданных синхронизирована между BL-02 и BL-10 | BL-02, BL-06, BL-10, BL-16a, BL-32 |
| [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) Consequences + Triggers for Revision | Дополнить раздел Consequences (Metadata Enrichment, Temperature lock) и Triggers (включение `MULTIHOP_ENABLED=true`, расширение fallback-цепочки) | Прозрачное отражение изменений в архитектурном решении | BL-02, BL-10, BL-11, BL-22 |
| [`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md) v1.1 §4 «Security & Compliance» (§4.1 prompt-injection mitigation, §4.3 log sanitization), §5 «Границы / Non-scope» | Сохранить трассировку: log sanitization (BL-23) **в scope MVP** через контракт §4.3 `sanitize_for_log()`; выход за границу offline-агентов (R-09 prompt-injection из KB) **остаётся** в ADR-003 §5 как non-scope MVP | Чек-лист валидации #7: явная ссылка §8 → ADR-003 §4 (Security & Compliance) | BL-23 |
| [`configs/embedding_config.yaml`](../../configs/embedding_config.yaml) | `chunk_size: 512`, `chunk_overlap: 64`; добавить `min_chunk_size`, `max_chunk_size`, опциональные `expand_neighbors`, `multihop_enabled`, `strict_rag_mode`; схема метаданных (`required: [page_number, section_title, section_number, product]`) | Привести конфиг к целевым значениям L1; флаги для BL-03 / BL-11; контракт схемы метаданных для BL-10 schema-check | BL-03, BL-06, BL-10, BL-11, BL-16a, BL-32 |
| [`configs/llm_config.yaml`](../../configs/llm_config.yaml) | Добавить блок `decoding:` (`temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024`); зафиксировать вызов `mask_text` в `generate_rag_response` через флаг `mask_rag_context: true` | Temperature lock (BL-22), маскирование RAG-канала (BL-04) | BL-04, BL-22 |
| [`configs/citation_config.yaml`](../../configs/citation_config.yaml) (новый) | `mode: file_local | static_serve | s3`, `base_url`, `kb_root` | Pilot-режим кликабельных цитат (BL-09.1) | BL-09, BL-09.1 |
| [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md) | Добавить раздел «Log sanitization (FR-08 + RAG-eval)» с явной ссылкой на [ADR-003 §4.3 (Log sanitization)](../ADR/003-multi-agent-orchestration-draft.md#43-log-sanitization-manage) и BL-23 | Контролируемое продвижение лог-санитайзера в production audit; чек-лист валидации #6/#7 | BL-23 |
| [`prompts/prompt_changelog.md`](../../prompts/prompt_changelog.md) | Запись о добавлении `system_rag_v1.md`, `system_rag_reflection_v1.md`, `system_rag_query_expansion_v1.md` | Прозрачное версионирование промптов ([CONCEPT §6.5](../CONCEPT.md#65-промпт-менеджмент)) | BL-08 |
| [`.github/workflows/rag-eval-smoke.yml`](../../.github/workflows/rag-eval-smoke.yml) (новый) | CI smoke-job ≤ 2 мин на 5-Q подвыборке Golden Set + stub-LLM | Чек-лист валидации #4 | BL-05.1 |
| [`CHANGELOG.md`](../../CHANGELOG.md) | Запись `BREAKING (KB schema)`: переиндексация под новые `chunk_size` и схему метаданных; `temperature lock`; `log sanitization` | KB-схема меняется не обратно-совместимо; декодирование закрепляется | BL-02, BL-06, BL-22, BL-23 |

---

## 9. ✅ Критерии приёмки (Definition of Done) — v1.5

- [ ] Файл `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` создан и соответствует [`naming-convention.md`](../standards/naming-convention.md) v1.1 (тип `backlog`, MINOR-версия `v1.5`).
- [ ] Бэклог содержит **все** задачи P0–P2 (включая §12 BL-18, BL-27..BL-29) без дубликатов и внутренних противоречий (см. §§3–5, §12).
- [ ] Каждая задача имеет **явные** поля `depends_on`, `priority`, `effort` в таблицах §§3–5 (и §12).
- [ ] Граф `depends_on` ацикличен и «висячих» зависимостей нет (см. §0.3, §10).
- [ ] BL-10 имеет `depends_on: [BL-02, BL-06]` и runtime schema-check метаданных (чек-лист валидации #3).
- [ ] BL-05.1 фиксирует CI smoke-job ≤ 2 мин (чек-лист валидации #4).
- [ ] BL-09 (базовый рендер `file://` + `#page=`) находится в P0; BL-09.1 (S3 / static-serve) — в P1 (чек-лист валидации #5).
- [ ] BL-22, BL-23, BL-24 добавлены и явно связаны с рекомендациями параллельной команды (чек-лист валидации #6).
- [ ] §8 содержит явную строку с ссылкой на [ADR-003 §4 (Security & Compliance)](../ADR/003-multi-agent-orchestration-draft.md#4-security--compliance-новый-раздел--закрывает-пробел-6) и привязкой BL-23 → §4.3 Log sanitization (чек-лист валидации #7).
- [ ] §11 «Матрица покрытия FR/НФТ ↔ BL» подтверждает, что каждая FR-01..FR-08 и NFR-01..NFR-09 имеет ≥ 1 связанную BL (чек-лист валидации #8).
- [ ] Архитектурная гипотеза (Canonical Cache + Offline Dependency Graph) вынесена отдельным разделом §7 для последующего ADR.
- [ ] Раздел §8 явно перечисляет файлы, требующие синхронизации, с обоснованием расхождений (включая временный рассинхрон CONCEPT §6.2 ↔ BL-32 до Sprint 2).
- [ ] Статус документа `Draft → Review`, владелец ревью — Product Owner.
- [ ] Файл готов к ревью PO **перед стартом Sprint 1**. Кодовые изменения не выполняются до `Accepted`.
- [ ] Сохранён черновик [`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md) (Status: Concept) — см. §10 «Связь со стратегическим расширением».
- [ ] Задачи BL-34..BL-45 с результатами и ссылками на артефакты перенесены в §15 «Архив (Sprint 3)».
- [ ] BL-47 добавлен в §0.6 с зависимостями `BL-43`, `BL-45` и статусом `⏳ Waiting`.
- [ ] `CHANGELOG.md` содержит запись `DOCUMENTATION: BL-46 backlog branch update to v1.4`.
- [ ] (v1.5) Зарегистрирована отдельная ветка бэклога [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) для BL-50..BL-56 (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)).
- [ ] (v1.5) BL-50..BL-56 присутствуют в §0.6 со статусом `📝 New` и ссылкой на §4.1..§4.7 отдельной ветки.
- [ ] (v1.5) §14 содержит строку `BL-50..BL-56` с триггером возврата (Accepted PO ревью отдельной ветки).
- [ ] (v1.5) `CHANGELOG.md` содержит запись `DOCUMENTATION: issue #182 — ARM pilot test fixes backlog branch + v1.5 sync`.

---

## 10. Связь со стратегическим расширением (Pilot → Enterprise)

Бэклог P0–P2 — **фундамент**. Стратегические направления, упомянутые в
issue #77 (мультиагентная оркестрация, анализ рыночного спроса по корпусу
Корпуса требований), **не модифицируют** этот бэклог и **не блокируют**
Sprint 1–2. Они зафиксированы черновиком в
[`docs/ADR/003-multi-agent-orchestration-draft.md`](../ADR/003-multi-agent-orchestration-draft.md)
со статусом `Concept`.

**Триггер перехода к мультиагентной схеме** (зеркалится в [CONCEPT §8.1.2](../CONCEPT.md#812-пилот-3–5-недель)):
- F1 ≥ 0.85 на Golden Set (см. NFR-01, BL-05, BL-05.1),
- Цитируемость ≥ 95 % (NFR-02, после BL-02 + BL-09 + BL-09.1),
- Готовность веб-шлюза вместо Streamlit,
- Утверждение PO бюджета на оркестратор и offline-агентов,
- Принятый log sanitizer (BL-23) на стороне FR-08 и evaluate_rag-отчётов как
  обязательный pre-condition для offline-агентов (ADR-003 v1.1 §4 Security & Compliance + §5 Non-scope).

---

## 11. 🧮 Матрица покрытия FR/НФТ ↔ BL (по чек-листу валидации #8)

Каждая FR из [`CONCEPT.md`](../CONCEPT.md) §4 и каждая НФТ из §5 имеет
≥ 1 явную привязку к BL-задаче (в т. ч. через §12 BL-18, BL-27..BL-29).

### 11.1 Функциональные требования (FR)

| FR | Описание (кратко) | Связанные BL | Комментарий |
|----|--------------------|--------------|-------------|
| **FR-01** | Парсинг входных файлов (`.xlsx` + `.docx`) | BL-18 (§12) | Диспетчер парсеров + `locator` |
| **FR-02** | Индексация базы знаний | BL-02 (метаданные), BL-06 (chunker L1), BL-10 (Parent), BL-14 (offline deps), BL-16a/BL-32 (стандарты) | KB-схема и reindex |
| **FR-03** | Гибридный RAG-поиск | BL-01 (Hybrid в production-пути UI), BL-11 (multi-hop), BL-12 (Query Expansion) | ADR-001 |
| **FR-04** | LLM-классификация и валидация | BL-04 (маскирование RAG-канала), BL-08 (Prompt Library), BL-22 (temperature lock), BL-24 (faithfulness gate) | JSON-вывод + детерминизм |
| **FR-05** | Маскирование чувствительных данных | BL-04 (RAG-канал), BL-23 (логи + RAG-eval отчёты) | NFR-04/NFR-05 |
| **FR-06** | Экспорт результатов (multi-format) | BL-27 (стандарт разметки), BL-28 (ExportRouter + адаптеры) | §12 |
| **FR-07** | Streamlit UI | BL-07 (память диалога), BL-09 (базовые цитаты), BL-09.1 (Pilot-режим цитат), BL-29 (UI-селекторы экспорта) | UX |
| **FR-08** | Логирование и аудируемость | BL-22 (`temperature`/`seed` в логе), BL-23 (sanitization), BL-05.1 (CI smoke сохраняет artefact) | run_id-trace |

### 11.2 Нефункциональные требования (НФТ)

| NFR | Описание | Целевое | Связанные BL | Комментарий |
|-----|----------|---------|--------------|-------------|
| **NFR-01** | Точность классификации | ≥ 75 % F1 | BL-05, BL-05.1, BL-24 | Golden Set + CI smoke + faithfulness |
| **NFR-02** | Цитируемость | ≥ 95 % (Pilot) / ≥ 80 % (MVP, см. §1) | BL-02, BL-09, BL-09.1 | Базовый рендер на MVP; Pilot-режим на Sprint 2 |
| **NFR-03** | Время обработки | ≤ 15 мин / 50 требований | BL-15 (Ollama-tuning), BL-22 (стабильность декодирования) | Замер в Пилоте |
| **NFR-04** | Резидентность данных | RU-резидентный provider в prod | BL-04 (маскирование RAG-канала), BL-23 (sanitization) | GigaChat-only в prod |
| **NFR-05** | 0 утечек чувствительных данных | 100 % замаскировано | BL-04, BL-23 | Аудит логов + sanitization |
| **NFR-06** | Аудируемость сессий | 100 % `run_id` + trace | BL-22 (`seed`/`temperature` в логах), BL-23 | FR-08-расширение |
| **NFR-07** | Актуальность KB | ≤ 24 ч | BL-02 (обогащение schema), BL-30 (cache invalidate) | `source_registry.csv` |
| **NFR-08** | Доступность сервиса | ≥ 99 % (Пилот) | BL-15 (ускорение), BL-22 (стабильность) | На Пилоте |
| **NFR-09** | Безопасность загрузки | Лимит 10 МБ | BL-29 (UI-валидация), V-04..V-07 (см. §12) | Multi-sheet `.xlsx` и legacy `.doc` |

> **Покрытие подтверждено:** 8/8 FR и 9/9 НФТ имеют ≥ 1 связанную BL.

---

## 12. Scope shift `.docx` + multi-format export → MVP (issue [#79](https://github.com/G-Ivan-A/clarify-engine-ai/issues/79))

> Раздел перенесён без содержательных изменений из v1.1.
> Сквозная нумерация BL-18, BL-27..BL-29 сохранена (V-10). Следующий свободный ID
> после v1.3 — **BL-33**.

### 12.1. Задачи P0 (MUST для MVP-release)

| ID | Задача | depends_on | priority | effort | Контекст | Проблема | Решение | Триггеры готовности |
|----|--------|-----------|----------|--------|----------|----------|---------|----------------------|
| **BL-18** | Интеграция `DocxParser` в основной пайплайн через диспетчер по расширению | — | P0 | M (2–3 д) | FR-01 заявляет `.xlsx`+`.docx`; реально подключён только `.xlsx` (`src/pipeline.py:178`) | На `.docx`-входе пайплайн падает с `NotImplementedError`/`KeyError`; парсер `src/parsers/docx_parser.py` написан, но не вызывается; `python-docx` не зафиксирован в `requirements.txt` | (1) `load_requirements_by_extension(path)` в `src/parsers/__init__.py`; (2) `DocxParser` — поле `locator` ([`analysis §4.1`](../analysis/2026-05-17_analysis_tz-structure_samples.md#41-контракт-docxparser-предложение)); (3) `excel_parser` — `sheet_name=None` + `locator`; (4) пин `python-docx`; (5) секция `docx_parser:` в [`configs/parsing_config.yaml`](../../configs/parsing_config.yaml) | E2E на `sample_tz_1.DOCX` и `sample_tz-2.xlsx`: непустой список требований с непустым `locator`; smoke-test `tests/test_docx_parser.py` зелёный |
| **BL-27** | Единая схема разметки результата (`.xlsx` / `.docx` / `.md`) | — | P0 | S (документ готов) | Без стандарта три экспортёра разъедутся в форматах вывода и сломают round-trip | `excel_exporter.py:118-127` early-return’ит на не-`xlsx` источниках; маппинг результата на элемент исходника не формализован | Принять [`docs/standards/export-markup.md`](../standards/export-markup.md) v1.0: контракт 4 MVP-колонок FR-06, локатор `Ref`, маркеры, режим `create_new` как default | PO даёт `Approved` стандарту; все экспортёры BL-28 проходят чек-лист §9 стандарта |
| **BL-28** | Multi-format export (`ExportRouter` + три адаптера) и режим сохранения | BL-27 | P0 | L (3–4 д) | Запрос PO: перенести multi-format export из Пилота в MVP | Только `excel_exporter` существует; нет общего фасада, нет `.docx`/`.md`-адаптеров, нет селектора режима | `ExportRouter` + `docx_exporter` + `md_exporter` + `configs/export_config.yaml` + тесты round-trip | Round-trip-матрица: `xlsx in → {xlsx, docx, md} out`, `docx in → {docx, md} out` — все 5 кейсов зелёные |
| **BL-29** | UI-селектор формата и режима экспорта (FR-07) | BL-28 | P0 | S (1 д) | FR-07: загрузка → анализ → скачивание; нужен выбор формата вывода для БА | UI всегда отдаёт `.xlsx`; БА вынужден конвертировать вручную; режим `append_to_original` недоступен | Radio `output_format ∈ {xlsx, docx, md}` + radio `output_mode ∈ {create_new, append_to_original}`; «≤ 3 клика» (FR-07) | E2E через Playwright/Streamlit: 3 формата × 1 файл скачиваются без 500; `append_to_original` недоступен в production-конфиге |

### 12.2. Уязвимости и критические замечания (без изменений относительно v1.1)

| # | Категория | Уязвимость / замечание | Источник | Риск | Компенсирующий механизм | Привязка |
|---|-----------|-------------------------|----------|------|--------------------------|----------|
| V-01 | Политика данных | `docx_parser.py` плоско склеивает параграфы и ячейки → утрата локаторов | `src/parsers/docx_parser.py`, [`analysis §2.2`](../analysis/2026-05-17_analysis_tz-structure_samples.md#22-распознанные-структурные-паттерны) | Утрата трассируемости (NFR-06) | Поле `locator` (BL-18) + маркер `[Ref:]` (BL-27) | BL-18, BL-27 |
| V-02 | Политика данных | `append_to_original` нарушает CONCEPT §2.3, если включён по умолчанию | CONCEPT §2.3, issue #79 | Нарушение SHA-256 версионирования KB | `output_mode = create_new` — default; `append_mode` под флагом и не в production | BL-27 §5, BL-29 |
| V-03 | PII / Маскирование | До релиза `masking_rules.yaml` v2 файл-отчёт не должен содержать копию содержимого исходника | CONCEPT §10 п.4, [`analysis §2.5`](../analysis/2026-05-17_analysis_tz-structure_samples.md#25-что-не-изучалось-граница-анализа) | Утечка PII через файл-отчёт | В `export-markup.md` §4.2/§4.3 зафиксировано: только `Ref`, не текст | BL-27, FR-05 |
| V-04 | Multi-sheet `.xlsx` | `excel_parser` читает только `sheet_name=0` → потеря требований | `analysis §2.2 / §4.3` | Снижение покрытия | `sheet_name=None` + `locator={"sheet": ..., "row": ...}` | BL-18 |
| V-05 | Merged-header `.xlsx` | Двойная шапка ломает `_detect_requirement_column` | `analysis §2.2` | Неверная атомизация | Эвристика «строка-заголовок — N-я» + warning-лог | BL-18 |
| V-06 | Зависимости | `python-docx` не закреплён в `requirements.txt` | `src/parsers/docx_parser.py`, `requirements.txt` | Сломанный E2E на чистой среде | Пин `python-docx` + CI-проверка импорта | BL-18 |
| V-07 | Legacy `.doc` (binary) | `sample_tz-3.doc` не открывается `python-docx` | `analysis §2.1` | «Не работает на реальном файле клиента» | Out-of-Scope MVP с диагностическим исключением; конвертер в P2 как `BL-18-ext` | BL-18 |
| V-08 | Логи / `RunID` | Многократный экспорт одного `run_id` должен оставаться идемпотентным | CONCEPT §4 FR-08, §6.7.3 | Расхождение `xlsx`/`docx`/`md`-отчётов | Один источник результатов в памяти; тест `tests/test_export_router.py` | BL-28 |
| V-09 | Совместимость с ADR-002 | Расширенная схема экспорта (ADR-002) и multi-format export ортогональны | [`ADR-002`](../ADR/002-export-schema-extension.md) | Post-pilot колонки «дрейфуют» | ADR-002: 4 MVP-колонки FR-06 стабильный контракт; новые поля через `schema_version` | BL-27, обновление ADR-002 |
| V-10 | Backlog-гигиена | Нумерация задач сквозная; BL-29 — последний из §12 v1.1 | этот §12 | Дубликаты BL-ID при параллельной правке | BL-18, BL-27..BL-29 — scope shift `.docx`+multi-format; следующая свободная — **BL-33** (с учётом BL-22..BL-24 из v1.3) | этот §12 + §0 v1.3 |

### 12.3. Сводка изменений документации, инициированных §12

| Файл | Что обновить | Связанный BL |
|------|--------------|---------------|
| [`docs/CONCEPT.md`](../CONCEPT.md) §2.3, §4 FR-01/FR-06/FR-07, §8.1.1, §10 п.2 | Scope shift `.docx`+multi-format export → MVP | BL-18, BL-27..BL-29 |
| [`docs/ADR/002-export-schema-extension.md`](../ADR/002-export-schema-extension.md) | Note: 4 MVP-колонки сохраняются; multi-format через `schema_version` (V-09) | BL-27, BL-28 |
| [`docs/standards/export-markup.md`](../standards/export-markup.md) | Принять v1.0 (создано в этой итерации) | BL-27 |
| [`configs/parsing_config.yaml`](../../configs/parsing_config.yaml) | Секция `docx_parser:` ([`analysis §4.4`](../analysis/2026-05-17_analysis_tz-structure_samples.md#44-предлагаемая-секция-configsparsing_configyaml)) | BL-18 |
| `configs/export_config.yaml` | Создать: `default_format`, `append_mode: false`, `report_basename_template` | BL-28 |
| `requirements.txt` | Зафиксировать `python-docx` | BL-18 |

---

## 13. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-17 | Первая версия согласованного бэклога: P0 (BL-01..BL-05, BL-16), P1 (BL-06..BL-10), P2 (BL-11..BL-15). Архитектурная гипотеза Canonical Cache + Offline Dependency Graph вынесена в §7. Привязка к [issue #76](https://github.com/G-Ivan-A/clarify-engine-ai/issues/76), CONCEPT §§4–6 и §8.1.2, ADR-001, ADR-003 (Concept). |
| v1.1 | 2026-05-17 | Добавлен §12 (scope shift `.docx`+multi-format export → MVP по [issue #79](https://github.com/G-Ivan-A/clarify-engine-ai/issues/79)): задачи BL-18..BL-21; таблица уязвимостей V-01..V-10; сводка изменений документации §12.3. Кодовых изменений нет. |
| v1.2 | 2026-05-17 | Корректировка валидации по [issue #83](https://github.com/G-Ivan-A/clarify-engine-ai/issues/83): §0 Validation Report, BL-16a/BL-16b, BL-05.1, BL-09/BL-09.1, BL-22..BL-24, ADR-003 §4 traceability, §11 «Матрица покрытия FR/НФТ ↔ BL». Документ остаётся `Draft → Review`, кодовых изменений нет. |
| **v1.3** | **2026-05-19** | **Актуализация статуса:** 14 задач закрыты, BL-26 в работе. Перенумерация BL-19..BL-21 → BL-27..BL-29. Добавлены BL-30..BL-32. Явное выделение отложенных задач (§14). |
| **v1.4** | **2026-05-20** | **BL-46:** Archive BL-34..BL-45, add BL-47 research. Добавлен архив Sprint 3 (§15), актуализирован статус BL-43/BL-44/BL-45, добавлена исследовательская задача BL-47 в основной статусный реестр. |
| **v1.5** | **2026-05-20** | **issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182):** Зарегистрирована отдельная ветка бэклога [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) (BL-50..BL-56) по итогам пилотного тестирования на АРМ. BL-46 и BL-47 переведены в `✅ Closed` (артефакты v1.4 и research note существуют). Сквозная нумерация V-10: следующий свободный ID — **BL-57**. |

---

## 14. Отложенные задачи (Backlog / Thinking)

| ID | Задача | Причина откладывания | Триггер возврата |
|----|--------|---------------------|------------------|
| BL-30 | Canonical Query Cache | Требует ADR, валидации на Golden Set; вынесен в изолированный Track 2 backlog [`2026-05-19_track2-cache-validation_v2.md`](2026-05-19_track2-cache-validation_v2.md) со статусом `🟡 DEFERRED` | После Sprint 3, наличие cross_doc категории, прохождение Gate 0 и согласование PO |
| BL-31 | LLM-нормализация DOCX | Зависит от результатов BL-28 (Export) | Если атомарность критична для экспорта |
| BL-32 | Config Sync | Tech debt, не блокирует функциональность | После стабилизации BL-27..BL-29 |
| BL-48 | ARM Installer (`clarify-setup.cmd`) | Реализация запланирована на Sprint 4, scope определён в [BL-47 research](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md). Перед стартом необходимы BL-50..BL-53 (runtime guards), на которые опирается wizard. | После закрытия BL-50..BL-53 и Accepted PO ревью ARM pilot fixes |
| BL-49 | Cloud TZ access (WebDAV + S3) | Реализация запланирована на Sprint 5, требует ADR-010 и формального соглашения с заказчиком о точке загрузки ТЗ. | После завершения Sprint 4 и согласования ADR-010 |
| BL-50..BL-56 | ARM pilot test fixes (7 задач) | Изолированы в отдельной ветке бэклога [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](2026-05-20_backlog_arm-pilot-test-fixes_v1.md) для контроля задач пилотного тестирования (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)). Статус `Draft → Review`. | После Accepted PO ревью отдельной ветки; BL-50, BL-52, BL-54 выходят hot-fix-релизом, BL-51/BL-55 — Sprint 4, BL-53/BL-56 — Sprint 5 |

---

## 15. 🗄 Архив (Sprint 3)

Завершённые задачи Sprint 3 сохранены с результатом и ссылкой на артефакт.
Задачи BL-43..BL-45 также отражены в §0.6 через зависимости BL-46/BL-47:
BL-43 и BL-45 закрыты, BL-44 завершён документально в `docs/user_guide/`.

| ID | Задача | Приоритет | Статус | Зависимости | Обоснование | DoD |
|----|--------|-----------|--------|-------------|-------------|-----|
| BL-34 | Architecture Consistency Audit | P1 | ✅ Closed | — | Проверить архитектурный дрейф перед Sprint 3 deployment gate | Отчёт [`docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md`](../audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md): P0/P1 drift = 0, деплой разрешён |
| BL-35 | Track 2 Cache Validation Backlog | P2 | ✅ Closed | BL-30 | Изолировать cache/Pivot исследования от production-периметра | Создан [`2026-05-19_track2-cache-validation_v2.md`](2026-05-19_track2-cache-validation_v2.md) со статусом `🟡 DEFERRED`, gates 0→3 и T2-BL-33..T2-BL-38 |
| BL-36 | Parent-aware retrieval stabilization | P1 | ✅ Closed | BL-10 | Закрепить parent context только для режима «Консультация» | Контракт подтверждён ADR-009, `configs/embedding_config.yaml` и тестами `tests/test_ui_modes.py`, `tests/test_retriever.py` |
| BL-37 | Export contract stabilization | P1 | ✅ Closed | BL-27, BL-28 | Зафиксировать multi-format export как стабильный MVP-контракт | ADR-002/ADR-008 и `tests/test_export_contract.py`, `tests/test_export_router.py`, `tests/test_excel_exporter.py` подтверждают schema v1.0 |
| BL-38 | Prompt drift and decoding audit | P1 | ✅ Closed | BL-08, BL-22 | Устранить недетерминированность LLM-ответов перед smoke gate | `docs/standards/llm-behavior.md`, `configs/llm_config.yaml` и `tests/test_decoding_lock.py` закрепляют `temperature=0.1`, `top_p=0.9`, `seed=42` |
| BL-39 | CONCEPT SSoT sync v2.5 | P1 | ✅ Closed | BL-34 | Синхронизировать CONCEPT с фактическими ADR, режимами UI и pre-deploy invariants | [`docs/CONCEPT.md`](../CONCEPT.md) v2.5, CHANGELOG запись `DOCS: CONCEPT.md → v2.5 SSoT sync` |
| BL-40 | ADR sync & numbering convention | P1 | ✅ Closed | BL-34, BL-39 | Синхронизировать ADR-001..009 и устранить неоднозначность ADR numbering | ADR README и ADR-001..009 обновлены; CHANGELOG запись `DOCUMENTATION: BL-40 ADR sync & numbering convention` |
| BL-41 | Streamlit UI refactor & UX polish | P1 | ✅ Closed | BL-39, BL-40 | Декомпозировать UI и централизовать user-facing copy | `src/ui/components/`, `src/ui/constants.py`, `tests/test_ui_components.py`; CHANGELOG запись `BL-41 — Streamlit UI refactor & UX polish` |
| BL-42 | Sync LLM fallback chains to production reality | P1 | ✅ Closed | BL-41 | Зафиксировать GigaChat primary и убрать DeepSeek из активных pilot chains | `configs/llm_config.yaml`, `src/llm/client.py`, ADR-001/ADR-004 и тесты `tests/test_rag_response.py` синхронизированы |
| BL-43 | Post-fix Smoke & E2E verification | P1 | ✅ Closed | BL-41, BL-42 | Проверить готовность после UI refactor и fallback-chain sync | Отчёт [`docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md`](../audit/2026-05-20_bl-43-smoke-e2e-report_v1.md): 351 passed / 0 failed, P0/P1 regressions = 0 |
| BL-44 | User Guide for Business Analysts | P1 | ✅ Closed | BL-41, BL-43 | Дать БА сценарный guide по режимам, результатам, export и troubleshooting | [`docs/user_guide/README.md`](../user_guide/README.md) + 4 главы и screenshots `docs/user_guide/screenshots/` |
| BL-45 | ARM deployment runbook | P1 | ✅ Closed | BL-43 | Зафиксировать установку на Windows ARM / CPU Ollama для пилота | [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md), [`tests/test_arm_deployment_runbook.py`](../../tests/test_arm_deployment_runbook.py), CHANGELOG запись `DOCUMENTATION: BL-45 ARM deployment runbook` |
