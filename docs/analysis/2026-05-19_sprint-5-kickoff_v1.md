# Sprint 5 — UX Polish & Documentation Sync — Kickoff (issue #192)

## 🗂 Метаданные

- **Дата:** 2026-05-19
- **Версия:** v1
- **Тип документа:** `analysis` (Sprint Kickoff / Plan, см. [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 §3.2)
- **Статус:** `Draft → Review`
- **Автор:** konard (AI issue solver, по [issue #192](https://github.com/G-Ivan-A/clarify-engine-ai/issues/192))
- **Ревьюер:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Связанный PR:** [#193](https://github.com/G-Ivan-A/clarify-engine-ai/pull/193)
- **Бэклог-источник:** [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §7 «План реализации» → строка **Sprint 5**
- **Основной реестр статусов:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md) §0.6 (строки BL-53, BL-55)
- **Период:** 2026-06-05 → 2026-06-19 (ориентировочно — после закрытия Sprint 4, утверждается PO)
- **Связанные issues:**
  - [#192 — Sprint 5 - 200526](https://github.com/G-Ivan-A/clarify-engine-ai/issues/192) (этот kickoff)
  - [#198 — `BL-53` Document Streamlit `.env`/`configs/*.yaml` cache behaviour](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) (создан этим PR)
  - [#199 — `BL-55` First-response UX — spinner text + warmup button](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199) (создан этим PR)
  - [#182 — Testing report](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (источник BL-53, BL-55)
  - [#187 — Sprint 4 kickoff](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187) / [PR #188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188) (предшественник, прецедент-шаблон kickoff)
  - [#186 — Hot-fix Sprint (BL-52, BL-56)](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186) (параллельный поток)

---

## 1. Понимание контекста

### 1.1. Verbatim formulation of the task

> **Sprint 5 - 200526** ([issue #192](https://github.com/G-Ivan-A/clarify-engine-ai/issues/192), автор PO — Ivan Gulienko):
>
> Создать issue в разделе <https://github.com/G-Ivan-A/clarify-engine-ai/issues/new>
> по каждой задаче в соответствии с Sprint 5 смотри
> [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
> — раздел 7 — **Sprint 5**.

### 1.2. Интерпретация задачи

Формулировка ясная: открыть GitHub issue **на каждую задачу из Sprint 5**
по §7 «План реализации» бэклога v1.0. Эта формулировка явнее, чем
прецедент issue #187 (Sprint 4), где аналогичная просьба сначала
прошла через kickoff-документ с готовыми «формулировками для копирования
PO». В Sprint 5 PO явно делегирует создание sub-issues solver-у, поэтому
issues открываются сразу в этом же потоке.

§7 backlog v1.0 определяет Sprint 5 как:

| Sprint | Задачи | Артефакт |
|--------|--------|----------|
| **Sprint 5** | **BL-53, BL-55** (UX-polish) | PR с обновлённым user guide и опциональной кнопкой «Перезагрузить конфиги» |

Таким образом Sprint 5 — это **два P2-issue** (BL-53 и BL-55), не P0/P1.
Создание Sprint 5 issues **не блокировано** Hot-fix Sprint / Sprint 4 —
обе задачи UX-polish и могут стартовать после закрытия pilot blocker
BL-54 (Sprint 4).

### 1.3. Цель Sprint 5

Закрыть последние две оставшиеся P2-проблемы пилотного тестирования на
АРМ ([issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)):

- **BL-53 (P2)** — Документировать поведение Streamlit `.env`/`configs/*.yaml`
  кэша (Streamlit hot-reload работает только для `src/`); опционально —
  кнопка «🔄 Перезагрузить конфиги» в сайдбаре под `ui.debug_mode: true`
  для graceful-restart процесса.
- **BL-55 (P2)** — UX первого ответа на холодном CPU-only Ollama: обновить
  текст спиннера ("⏱ Первый ответ на CPU может занять 60–90 сек"),
  добавить опциональную кнопку «🔥 Прогреть модель» в сайдбаре (под
  `ui.debug_mode: true` ИЛИ при локальном `OLLAMA_BASE_URL`), обновить
  user guide §1 / §4.

Совокупный effort: **1.5 человеко-дня** (S + S). Обе задачи изолированы
от RAG-пайплайна, ADR-001/003/007, fallback-цепочки LLM — минимальный
риск регрессии.

### 1.4. Предпосылки и ограничения

- Sprint 5 стартует **после закрытия Sprint 4** ([issue #187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187) → BL-50, BL-51, BL-54): UX-polish осмысленен только если pilot blocker BL-54 уже устранён и
  основной use-case «📊 Анализ ТЗ» восстановлен.
- Sprint 5 **независим** от BL-48 (installer PoC, параллельный поток):
  BL-53 / BL-55 — UX внутри Streamlit, не пересекаются с CLI-инсталлятором.
- Сквозная нумерация **V-10** сохранена; ни одна из задач Sprint 5 не
  меняет ADR-001 / ADR-003 / ADR-007 / CONCEPT.
- Кодовые изменения по BL-53 / BL-55 стартуют **только после
  Accepted-ревью PO** на каждый из созданных sub-issues (#198, #199), как
  зафиксировано в §7 backlog v1.0 и §11.1 v1.5.

---

## 2. Анализ текущего состояния

### 2.1. Что изучено

- [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §4.5 (BL-53), §4.7 (BL-55), §6.1 (target status в v1.5), §7 (план реализации).
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md)
  §0.6 — текущий статус BL-53/BL-55 = `📝 New`; целевой статус
  после старта Sprint 5 = `🟡 In Progress`.
- [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 §3.2 — тип `analysis` валиден для sprint kickoff/plan-документов в `docs/analysis/`.
- Прецедентные issues [#194 / BL-50](https://github.com/G-Ivan-A/clarify-engine-ai/issues/194), [#195 / BL-51](https://github.com/G-Ivan-A/clarify-engine-ai/issues/195), [#196 / BL-54](https://github.com/G-Ivan-A/clarify-engine-ai/issues/196) — шаблон формулировки BL-issue: `Labels`, `Milestone`, `Linked Backlog`, `Depends On`, `🎯 Цель`, `👤 User Story`, `🛡 Контракт`, `📋 Рекомендации`, `✅ DoD`, `📦 Scope Note`.
- Прецедентный kickoff [`docs/analysis/2026-05-20_sprint-4-kickoff_v1.md`](2026-05-20_sprint-4-kickoff_v1.md) — структура и §-нумерация sprint-документа.
- Прецедентный PR [#188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188) — docs-only PR со статусом `Draft → Review` до Accepted PO; CHANGELOG-запись в формате `DOCUMENTATION: ...`.

### 2.2. Scope Sprint 5

| ID | Задача | Приоритет | Effort | depends_on | Sub-issue | Артефакт после Accepted |
|----|--------|-----------|--------|-----------|-----------|--------------------------|
| **BL-53** | Document Streamlit `.env`/`configs/*.yaml` cache behaviour + optional «🔄 Reload Config» debug button | P2 | S (0.5 д) | — | [#198](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) | PR с правками `docs/runbooks/arm-deployment-ivan.md` §2/§6, `docs/user_guide/04_troubleshooting.md`, опционально — `src/ui/components/sidebar.py` (кнопка под `debug_mode: true`) + smoke в `tests/test_arm_deployment_runbook.py` |
| **BL-55** | First-response UX — spinner text + optional «🔥 Прогреть модель» button | P2 | S (1 д) | — | [#199](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199) | PR с обновлением `src/ui/constants.py::LABELS.spinner_llm`, кнопкой warmup в `src/ui/components/sidebar.py`, обновлениями `docs/user_guide/01_intro_modes.md` / `04_troubleshooting.md`, runbook §1.8 sync, тестами `test_ui_constants.py` / `test_ui_components.py` |

**Суммарный effort:** 1.5 человеко-дня. **Параллелизация:** BL-53 и BL-55
полностью независимы — могут вестись одним исполнителем последовательно
или параллельно двумя без конфликтов (общие файлы: `src/ui/components/sidebar.py`
и `docs/user_guide/04_troubleshooting.md` — изменения дополняющие, не пересекающиеся).

### 2.3. Ограничения анализа

- В этом документе **не приводятся** полные acceptance-критерии и
  «Решение» — они уже зафиксированы в backlog §4.5 / §4.7 и в телах
  созданных sub-issues [#198](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) / [#199](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199).
  Документ ссылается на них, а не дублирует, чтобы избежать рассинхрона
  при правках.
- Документ **не изменяет** §0.6 v1.5 — это сохраняет docs-only-инвариант
  backlog v1.5 (артефакт PR #183). Sync статусов `📝 New → 🟡 In Progress`
  — отдельным PR после Accepted PO (см. §5.1).

---

## 3. Definition of Ready (entry criteria) и Definition of Done (exit criteria)

### 3.1. Definition of Ready — старт Sprint 5

- [ ] Sprint 4 ([issue #187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)) — `Closed`: BL-50, BL-51, BL-54 merged в `main`, pilot blocker устранён.
- [ ] [PR #193](https://github.com/G-Ivan-A/clarify-engine-ai/pull/193) (этот kickoff) → `Accepted` PO.
- [x] Sub-issues [#198 / BL-53](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) и [#199 / BL-55](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199) — созданы (этот PR).
- [ ] Backlog v1.5 §0.6: статусы **BL-53, BL-55** переведены `📝 New → 🟡 In Progress` (см. §5).

### 3.2. Definition of Done — закрытие Sprint 5

- [ ] BL-53, BL-55 — каждая в статусе `✅ Closed`:
  - тесты, перечисленные в backlog §4.5 / §4.7 и в issue-телах #198/#199 — зелёные локально и в CI;
  - каждой задаче соответствует **отдельный merged PR**.
- [ ] Повторный smoke-прогон [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §2, §6, §1.8 на чистой Windows 11 — предупреждения про Streamlit cache (BL-53) и про 60–90 сек первого ответа (BL-55) присутствуют; spinner-text обновлён.
- [ ] Тестировщик ([@G-Ivan-A](https://github.com/G-Ivan-A)) подтверждает закрытие проблем #4 («Streamlit кэширует `.env`») и #6 («Долгий первый ответ») из отчёта пилота ([issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)) — комментарием в каждом merged PR или в issue #182.
- [ ] Backlog v1.5 §0.6: BL-53, BL-55 → `✅ Closed` с ссылками на merged PR.
- [ ] Sprint-5 Execution Report (по шаблону [`docs/analysis/sprint-execution-report_template.md`](sprint-execution-report_template.md)) опубликован в `docs/analysis/<YYYY-MM-DD>_sprint-5-execution-report_v1.md` после закрытия второго PR.
- [ ] CHANGELOG.md — записи `CODE+DOCS: BL-53 ...` и `CODE+DOCS: BL-55 ...` (или `DOCS: BL-53 ...` если опциональная кнопка не внедрена) под `[Unreleased]`.

---

## 4. Созданные sub-issues

> ⚠️ В отличие от Sprint 4 kickoff (PR #188), где формулировки sub-issues
> приводились **для копирования PO**, в Sprint 5 issues уже **созданы**
> AI issue solver-ом в соответствии с прямой формулировкой issue #192.
> Полные тела доступны по ссылкам ниже; ниже — только сводная таблица.

### 4.1. BL-53 — Document Streamlit cache + Reload Config (P2)

| Поле | Значение |
|------|----------|
| **Issue** | [#198](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) |
| **Title** | `` `BL-53`: Document Streamlit `.env`/`configs/*.yaml` cache behaviour + optional «Reload Config» debug button `` |
| **Labels (по конвенции)** | `code`, `priority:P2`, `sprint:5`, `pilot-readiness`, `area:ui`, `area:docs` |
| **Milestone** | `Sprint 5 — UX Polish & Documentation Sync` |
| **Linked Backlog** | `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` §4.5 + v1.5 §0.6 BL-53 |
| **Depends On** | — (parallel-safe с BL-55) |
| **Source of problem** | Отчёт тестировщика §1.6 / Проблема #4 |
| **Effort** | S (0.5 д) |

### 4.2. BL-55 — First-response UX (spinner + warmup) (P2)

| Поле | Значение |
|------|----------|
| **Issue** | [#199](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199) |
| **Title** | `` `BL-55`: First-response UX — spinner text update + optional «Прогреть модель» warmup button `` |
| **Labels (по конвенции)** | `code`, `priority:P2`, `sprint:5`, `pilot-readiness`, `area:ui`, `ux` |
| **Milestone** | `Sprint 5 — UX Polish & Documentation Sync` |
| **Linked Backlog** | `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` §4.7 + v1.5 §0.6 BL-55 |
| **Depends On** | — (parallel-safe с BL-53) |
| **Source of problem** | Отчёт тестировщика §2 / Проблема #6 (60–90 сек первого ответа на CPU-only) |
| **Effort** | S (1 д) |

---

## 5. План изменений в реестрах после Accepted PO

### 5.1. Backlog v1.5 §0.6 sync (отдельный PR)

После Accepted PR #193 — отдельный docs-only PR обновляет
[`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md)
§0.6 строки BL-53 / BL-55:

| ID | Статус (новый) | Линк sub-issue |
|----|----------------|----------------|
| BL-53 | `🟡 In Progress` | [#198](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) |
| BL-55 | `🟡 In Progress` | [#199](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199) |

> §0.6 v1.5 НЕ модифицируется в этом PR — это сохраняет docs-only-инвариант
> backlog v1.5 (артефакт PR #183) до явного согласия PO.

### 5.2. CHANGELOG.md

В текущий PR #193 добавляется запись в `[Unreleased]` Documentation
(см. §7 ниже / реальный текст в [`CHANGELOG.md`](../../CHANGELOG.md)):

- `DOCUMENTATION: issue #192 — Sprint 5 kickoff (BL-53, BL-55)` с
  ссылками на созданные sub-issues #198 / #199 и kickoff-документ.

После Sprint 5 (отдельным PR за каждую BL): записи `CODE+DOCS: BL-53 / BL-55 ...` под `[Unreleased]`.

---

## 6. Риски и митигация

| # | Риск | Влияние | Митигация |
|---|------|---------|-----------|
| R1 | Опциональная часть BL-53 (кнопка «🔄 Перезагрузить конфиги») и BL-55 (кнопка «🔥 Прогреть модель») может оказаться вне scope Sprint 5 при недостатке времени | Sprint не закрывается, PO просит выделить core/optional | Контракт sub-issue #198 / #199 явно делит scope: **обязательная часть** — документация, **опциональная** — UI-кнопки; PR может ограничиться обязательной частью без блокировки DoD |
| R2 | Изменение `LABELS.spinner_llm` (BL-55) может сломать существующие unit-тесты UI, если они проверяют точную строку | Регрессия в `tests/test_ui_*.py` | Сначала запустить полный набор `pytest tests/test_ui_*.py` до изменения; в PR обновить ассерты вместе с константой; добавить тест на наличие подстроки «60–90 сек» вместо точной строки |
| R3 | `os.execv(sys.executable, sys.argv)` (BL-53 опциональная кнопка) может потерять активные сессии Streamlit | UX-регрессия для multi-tab | Перед перезапуском — `st.warning("Перезапуск процесса через 2 сек…")` + sleep; кнопка скрыта в production-режиме (`debug_mode: false`, default) |
| R4 | Warmup-запрос (BL-55) к удалённому `OLLAMA_BASE_URL` может флудить чужой сервис | NFR-04 (резидентность) / репутация | Контракт sub-issue #199: кнопка видна только при `debug_mode: true` ИЛИ localhost `OLLAMA_BASE_URL`; явное условие тестируется в `test_ui_components.py` |
| R5 | Параллельные PR BL-53 / BL-55 могут конфликтовать в `src/ui/components/sidebar.py` и `docs/user_guide/04_troubleshooting.md` | Merge-конфликт | Каждый PR изолирует свой блок в sidebar (отдельная функция / условный блок) и в troubleshooting (отдельный раздел с заголовком); конфликт ловится тривиально |
| R6 | Sprint 5 может стартовать раньше закрытия Sprint 4 (BL-54 не закрыт) | Часть DoD BL-55 (smoke по «📊 Анализ ТЗ») не выполнима | DoR §3.1 явно требует Sprint 4 closed; PO утверждает старт Sprint 5 только после merge BL-54 |

---

## 7. Рекомендации (priority MUST / SHOULD / MAY)

### 7.1. MUST (необходимое условие старта Sprint 5)

| # | Действие | Кому | Триггер |
|---|----------|------|---------|
| M1 | Approve PR [#193](https://github.com/G-Ivan-A/clarify-engine-ai/pull/193) (этот kickoff) | PO ([@G-Ivan-A](https://github.com/G-Ivan-A)) | После ознакомления с §4 и проверки sub-issues #198 / #199 |
| M2 | Подтвердить, что sub-issues #198 / #199 соответствуют ожиданиям; при необходимости — попросить корректировки в комментариях | PO | Сразу после approve PR #193 |
| M3 | Открыть два отдельных feature-branches `issue-198-...`, `issue-199-...` | Code Agent / Developer | После M2 и закрытия Sprint 4 |
| M4 | В отдельном docs-only PR обновить v1.5 §0.6 (статусы → `🟡 In Progress`, ссылки на #198 / #199) | konard / Code Agent | После M2 |

### 7.2. SHOULD

| # | Действие | Обоснование |
|---|----------|-------------|
| S1 | Назначить BL-53 и BL-55 одному developer'у | Близкая природа задач (UI / docs), общие точки изменения — `src/ui/components/sidebar.py` |
| S2 | Стартовать BL-55 первым (текст спиннера) — минимальное изменение, быстрая retest-обратная связь | BL-53 опциональная кнопка может потребовать ревью архитектуры graceful-restart, что увеличивает effort |
| S3 | После merge BL-53 → опубликовать комментарий в [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) с подтверждением закрытия Проблемы #4; аналогично BL-55 → Проблема #6 | Прозрачность для тестировщика, who initiated the testing report |
| S4 | Перед закрытием Sprint 5 — заполнить `docs/analysis/<YYYY-MM-DD>_sprint-5-execution-report_v1.md` по [шаблону](sprint-execution-report_template.md) | Прецедент Sprint 1 (`2026-05-17_sprint-1-execution-report_v1.md`); Sprint 4 завершит свой Execution Report ранее |

### 7.3. MAY

| # | Действие | Когда |
|---|----------|-------|
| Y1 | Расширить кнопку «🔥 Прогреть модель» (BL-55) на прогрев `bge-m3` embedding-модели через тестовый embedding-запрос | Sprint 6+, если пилот выделит embedding cold-start как отдельный pain-point |
| Y2 | Подвесить кнопку «🔄 Перезагрузить конфиги» (BL-53) под общий `--debug` CLI-флаг Streamlit, не только `configs/ui_config.yaml::debug_mode` | Sprint 6+, если developer-flow выявит частую правку конфигов |
| Y3 | Унифицировать sidebar debug-режим: одна «Debug zone» с обеими кнопками + индикаторами состояния (LLM-провайдер, последний reload-time) | После закрытия BL-53 и BL-55, отдельный refactor PR (BL-57+) |

---

## 8. Открытые вопросы для PO

1. **Опциональные кнопки vs только документация.** Включаем ли мы опциональные UI-кнопки («🔄 Перезагрузить конфиги», «🔥 Прогреть модель») в DoD Sprint 5, или достаточно документации (runbook + user guide)? Контракт sub-issues #198 / #199 поддерживает оба варианта.
2. **`debug_mode` default.** Подтверждаете `ui.debug_mode: false` как default в `configs/ui_config.yaml`? Если pilot операторам нужно постоянно видеть debug-кнопки — можно задать `true` для ARM-конфигурации и `false` для production / cloud.
3. **Sprint 5 milestone.** Создавать ли GitHub Milestone «Sprint 5 — UX Polish & Documentation Sync» с due date 2026-06-19 для группировки sub-issues #198 / #199 + retest comment в #182? (Сейчас milestone указан только в Labels-блоке issue body, реального GitHub Milestone-объекта нет — см. результат `gh api repos/.../milestones` в момент создания PR.)
4. **Параллельный старт с Sprint 4.** Если Sprint 4 задерживается на BL-54 (M+ effort), допустим ли частичный старт Sprint 5 (только BL-55 текст спиннера — изменение в одну строку) для разгрузки очереди?

---

## 9. Ссылки

- **Issue:** [#192 — Sprint 5 - 200526](https://github.com/G-Ivan-A/clarify-engine-ai/issues/192)
- **PR:** [#193 (этот kickoff)](https://github.com/G-Ivan-A/clarify-engine-ai/pull/193)
- **Sub-issues:** [#198 / BL-53](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198), [#199 / BL-55](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199)
- **Бэклог-источник:** [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.5 / §4.7 / §7
- **Основной реестр:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md) §0.6
- **Testing report:** [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (источник BL-50..BL-56)
- **Sprint 4 kickoff (прецедент):** [`docs/analysis/2026-05-20_sprint-4-kickoff_v1.md`](2026-05-20_sprint-4-kickoff_v1.md), [PR #188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188), [issue #187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)
- **Hot-fix Sprint (параллельный поток):** [issue #186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186) (BL-52, BL-56)
- **User guide:** [`docs/user_guide/01_intro_modes.md`](../user_guide/01_intro_modes.md), [`docs/user_guide/04_troubleshooting.md`](../user_guide/04_troubleshooting.md) (BL-44)
- **ARM runbook:** [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1.8, §2, §6 (BL-45)
- **Стандарт именования:** [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1
- **Прецедентные issues:** [#194 / BL-50](https://github.com/G-Ivan-A/clarify-engine-ai/issues/194), [#195 / BL-51](https://github.com/G-Ivan-A/clarify-engine-ai/issues/195), [#196 / BL-54](https://github.com/G-Ivan-A/clarify-engine-ai/issues/196)
- **Шаблон execution report:** [`docs/analysis/sprint-execution-report_template.md`](sprint-execution-report_template.md)

---

## 10. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-19 | Первая версия Sprint 5 kickoff (issue [#192](https://github.com/G-Ivan-A/clarify-engine-ai/issues/192), PR [#193](https://github.com/G-Ivan-A/clarify-engine-ai/pull/193)). Фиксирует scope (BL-53, BL-55), Definition of Ready / Definition of Done, риски и открытые вопросы для PO. Sub-issues [#198 / BL-53](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198) и [#199 / BL-55](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199) созданы в рамках этого PR согласно прямой формулировке issue #192 («Создать issue в разделе issues/new по каждой задаче Sprint 5»). Документ — docs-only, статус `Draft → Review`. |
