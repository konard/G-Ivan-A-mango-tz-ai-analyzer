# Sprint 4 — Pilot Readiness & Automation — Kickoff (issue #187)

## 🗂 Метаданные

- **Дата:** 2026-05-20
- **Версия:** v1
- **Тип документа:** `analysis` (Sprint Kickoff / Plan, см. [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 §3.2)
- **Статус:** `Draft → Review`
- **Автор:** konard (AI issue solver, по [issue #187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187))
- **Ревьюер:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Связанный PR:** [#188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188)
- **Бэклог-источник:** [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §7 «План реализации» → строка **Sprint 4**
- **Основной реестр статусов:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md) §0.6 (строки BL-50, BL-51, BL-54)
- **Период:** 2026-05-26 → 2026-06-05 (ориентировочно, утверждается PO)
- **Связанные issues:** [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (testing report, источник BL-50..BL-56); [#168 / BL-41](https://github.com/G-Ivan-A/clarify-engine-ai/issues/168) (UI refactor — источник регрессии BL-54); [#173 / BL-44](https://github.com/G-Ivan-A/clarify-engine-ai/issues/173) (user guide); [#176 / BL-45](https://github.com/G-Ivan-A/clarify-engine-ai/issues/176) (ARM runbook); [#180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180) (installer research)

---

## 1. Понимание контекста

### 1.1. Verbatim formulation of the task

> **Sprint 4 start 200526** ([issue #187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187), автор PO — Ivan Gulienko):
>
> Сформировать issue на Hot-fix-релиз в соответствии с
> [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
> — раздел 7 — **Sprint 4**.

### 1.2. Интерпретация задачи

Формулировка совмещает «issue на Hot-fix-релиз» (шаблонный текст,
параллельный [issue #186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186))
и явную ссылку «раздел 7 — Sprint 4». Поскольку §7 бэклога чётко
разводит **Hot-fix Sprint** (BL-52, BL-56) и **Sprint 4** (BL-50, BL-51,
BL-54), приоритет отдаётся явной ссылке: настоящий документ формализует
**Sprint 4** и формулирует **по одному GitHub issue на каждую из трёх
BL-задач Sprint 4** в готовом для копирования виде (§4).

Документ остаётся в статусе `Draft → Review` до явного согласия PO в
комментариях [PR #188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188).
Кодовые изменения и сами GitHub issues создаются **только после
Accepted-ревью PO**, как зафиксировано в §7 backlog v1.0 и §11.1 v1.5.

### 1.3. Цель Sprint 4

Закрыть оставшиеся P0/P1 проблемы пилотного тестирования на АРМ
([issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)),
которые не решаются hot-fix-релизом BL-52/BL-56:

- **BL-50 (P0)** — устранить silent fail при `.env.txt` / отсутствующем
  `.env` через runtime guard на старте Streamlit.
- **BL-51 (P1)** — снять зависимость от ручной правки PATH через
  автодетект пути к Ollama в `src/llm/client.py` + явный шаг `setx PATH`
  в runbook §1.
- **BL-54 (P0, 🔴 PILOT BLOCKER)** — восстановить `st.file_uploader` в
  режиме «📊 Анализ ТЗ» (`src/ui/app.py::_run_analysis_mode`),
  потерянный в BL-41 UI refactor; согласовать с user guide §2 и runbook
  §1.8.

Совокупный effort: **3.5–4.5 человеко-дней** (S+S+M). Основной риск —
BL-54 (2–3 д, зависит от глубины интеграции с `ExportRouter` после
BL-41).

### 1.4. Параллельная активность

В §7 backlog v1.0 также упоминается **Sprint 4 (parallel) — BL-48
(installer PoC)**. BL-48 использует BL-50..BL-52 как зависимости
(см. §6.2 backlog v1.0). В текущем kickoff BL-48 **выделен в отдельную
параллельную ветку** и не входит в DoD Sprint 4 — это сохраняет фокус
на pilot blocker BL-54 и снижает риск переноса PoC clarify-setup.cmd
на Sprint 5.

### 1.5. Предпосылки и ограничения

- Sprint 4 стартует **только после Accepted-ревью PO** по
  [PR #183](https://github.com/G-Ivan-A/clarify-engine-ai/pull/183)
  (artefact: [`2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md))
  и закрытия Hot-fix Sprint (issue #186, BL-52 + BL-56).
- Каждая BL-задача Sprint 4 — отдельный GitHub issue → отдельный PR
  → отдельный merge. Это даёт прозрачность ревью и облегчает rollback
  для BL-54 при регрессии.
- Сквозная нумерация **V-10** сохранена; ни одна из задач Sprint 4 не
  меняет ADR-001 / ADR-003 / CONCEPT.

---

## 2. Анализ текущего состояния

### 2.1. Что изучено

- [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §4.2 (BL-50), §4.3 (BL-51), §4.6 (BL-54), §6.1 (taget status в v1.5),
  §7 (план реализации).
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md)
  §0.6 — текущий статус BL-50/BL-51/BL-54 = `📝 New`; целевой статус
  после старта Sprint 4 = `🟡 In Progress`.
- [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 §3.2 — тип `analysis` валиден для sprint kickoff/plan-документов в `docs/analysis/`.
- Прецедентные issues [#178 / BL-46](https://github.com/G-Ivan-A/clarify-engine-ai/issues/178), [#180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180) — шаблон формулировки BL-issue: `Labels`, `Milestone`, `Linked Backlog`, `Depends On`, `🎯 Цель`, `👤 User Story`, `🛡 Контракт`, `📋 Рекомендации`, `✅ DoD`, `📦 Scope Note`.
- Прецедентный отчёт [`docs/analysis/2026-05-17_sprint-1-execution-report_v1.md`](2026-05-17_sprint-1-execution-report_v1.md) — структура sprint-документа в `docs/analysis/`.
- Прецедентный PR [#183](https://github.com/G-Ivan-A/clarify-engine-ai/pull/183) — docs-only PR со статусом `Draft → Review` до Accepted PO; CHANGELOG-запись в формате `DOCUMENTATION: ...`.

### 2.2. Scope Sprint 4

| ID | Задача | Приоритет | Effort | depends_on | Артефакт после Accepted |
|----|--------|-----------|--------|-----------|--------------------------|
| **BL-50** | Startup-валидация `.env` (detect `.env.txt` + автокопирование `.env.example`) | **P0** | S (0.5 д) | — | PR с `src/config_loader.py` (или эквивалентом в `src/pipeline.py`) + `tests/test_env_validation.py` + runbook §1.4 cross-ref |
| **BL-51** | Автодетект пути к Ollama + PATH guidance в runbook | P1 | S (0.5 д) | — | PR с `src/llm/client.py::_resolve_ollama_executable()` + `tests/test_ollama_resolution.py` + runbook §1 (новый шаг `setx PATH`) |
| **🔴 BL-54** | **Восстановить file uploader в режиме «📊 Анализ ТЗ»** | **P0** | M (2–3 д) | BL-28, BL-29, BL-41 (все ✅ Closed) | PR с `src/ui/components/analysis_uploader.py` + `src/ui/app.py::_run_analysis_mode` rewrite + `tests/test_ui_modes.py` + `tests/test_ui_components.py` + smoke на runbook §1.8 |

**Суммарный effort:** 3.0–4.0 человеко-дня. **Параллелизация:**
BL-50 и BL-51 — независимы, могут быть в работе одновременно. BL-54
блокирует Sprint 4 DoD по pilot readiness — рекомендуется стартовать
первым.

### 2.3. Ограничения анализа

- В этом документе **не приводятся** полные acceptance-критерии и
  «Решение» — они уже зафиксированы в backlog §4.2/§4.3/§4.6.
  Документ ссылается на них, а не дублирует, чтобы избежать рассинхрона
  при правках backlog v1.0 → v1.1.
- Документ **не открывает** GitHub issues — это право Product Owner.
  Готовые формулировки приведены в §4 для копирования.

---

## 3. Definition of Ready (entry criteria) и Definition of Done (exit criteria)

### 3.1. Definition of Ready — старт Sprint 4

- [ ] [PR #183](https://github.com/G-Ivan-A/clarify-engine-ai/pull/183) → `Accepted` (артефакт backlog v1.0 утверждён PO).
- [ ] Hot-fix Sprint ([issue #186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186), BL-52 + BL-56) — merged в `main`.
- [ ] [PR #188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188) (этот kickoff) → `Accepted` PO.
- [ ] Backlog v1.5 §0.6: статусы **BL-50, BL-51, BL-54** переведены `📝 New → 🟡 In Progress` (см. §5).
- [ ] Sub-issues для BL-50/BL-51/BL-54 созданы PO с заголовками и телами из §4 (или эквивалентным контентом).

### 3.2. Definition of Done — закрытие Sprint 4

- [ ] BL-50, BL-51, BL-54 — каждая в статусе `✅ Closed`:
  - тесты, перечисленные в backlog §4 / в issue-теле §4 ниже — зелёные локально и в CI;
  - каждой задаче соответствует **отдельный merged PR**;
- [ ] Повторный smoke-прогон [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1.4, §1.5, §1.8 на чистой Windows 11 — без ручных вмешательств в `.env.txt`/PATH; file uploader в режиме «📊 Анализ ТЗ» виден и работает.
- [ ] Тестировщик ([@G-Ivan-A](https://github.com/G-Ivan-A)) подтверждает закрытие проблем #1, #2, #5 из отчёта пилота ([issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)) — комментарием в каждом merged PR или в issue #182.
- [ ] BL-43 E2E повторно зелёный **с дополнительным сценарием** «UI upload → analyse → download» (триггер `(e)` в backlog §4.6).
- [ ] Backlog v1.5 §0.6: BL-50, BL-51, BL-54 → `✅ Closed` с ссылками на merged PR.
- [ ] Sprint-4 Execution Report (по шаблону [`docs/analysis/sprint-execution-report_template.md`](sprint-execution-report_template.md)) опубликован в `docs/analysis/2026-06-05_sprint-4-execution-report_v1.md` (или ближайшая фактическая дата).
- [ ] CHANGELOG.md — записи `CODE: BL-50 / BL-51 / BL-54 ...` под `[Unreleased]` для каждой задачи.

---

## 4. Готовые формулировки sub-issues (для PO)

> Готовые тексты для копирования в GitHub UI. Структура соответствует
> прецеденту [issue #178 / BL-46](https://github.com/G-Ivan-A/clarify-engine-ai/issues/178)
> и [issue #180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180):
> блок мета (Labels / Milestone / Linked Backlog / Depends On) →
> §🎯 Цель → §👤 User Story → §🛡 Контракт → §📋 Рекомендации → §✅ DoD → §📦 Scope Note.

### 4.1. BL-50 — Startup-валидация `.env` (P0)

**Suggested title:**
```
`BL-50`: Startup `.env` validation (detect `.env.txt` + auto-copy `.env.example`)
```

**Suggested body:**

```markdown
**Labels:** `code`, `priority:P0`, `sprint:4`, `pilot-readiness`, `area:config`
**Milestone:** `Sprint 4 — Pilot Readiness & Automation`
**Linked Backlog:** `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` §4.2 + `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` §0.6 BL-50
**Depends On:** — (parallel-safe c BL-51, BL-54)
**Source of problem:** [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), отчёт тестировщика §1.4 / Проблема #1

### 🎯 Цель
Гарантировать, что на любом АРМ запуск `streamlit run src/ui/app.py` / `python -m src.pipeline` детерминированно ловит ситуацию «`.env` отсутствует или скрытый `.env.txt` рядом» и даёт пользователю actionable-ошибку с понятной подсказкой, либо автоматически копирует `.env.example → .env`.

### 👤 User Story
**Как** Бизнес-Аналитик, ставящий `clarify-engine-ai` на свой АРМ впервые,
**Я хочу** при запуске UI сразу получать ясную ошибку или auto-fix, если файл `.env` не создан / создан как `.env.txt`,
**Чтобы** не тратить 10+ минут на slient HTTP 404 от Ollama и ложную диагностику «всё сломалось».

### 🛡 Контракт и Ограничения

| Параметр | Требование |
|----------|------------|
| **Точка входа** | Runtime guard выполняется **до** первого вызова `os.environ.get(...)` в `src/pipeline.py` и `src/ui/app.py`. |
| **Обработка `.env.txt`** | Если `.env` отсутствует И `.env.txt` существует → `logger.error` + остановка с подсказкой `ren .env.txt .env`. Никакого silent rename. |
| **Auto-copy `.env.example`** | Если `.env` отсутствует И `.env.txt` отсутствует И `.env.example` существует → `logger.info("Создан .env из .env.example")` + копия. Дальше — обычная валидация. |
| **Валидация переменных** | После загрузки `.env`: `OLLAMA_MODEL` и `OLLAMA_BASE_URL` — непустые строки. При пустых значениях — детерминированная ошибка. |
| **Backward compat** | Существующие deployment-ы с корректным `.env` — без изменений в поведении. |
| **PII / маскирование** | Логи проходят `sanitize_log_record` (BL-23). В сообщениях об ошибке указываются только имена файлов, без содержимого. |

### 📋 Рекомендации к реализации (свобода исполнителя)

> 💡 Структура и точка размещения guard — на усмотрение исполнителя. Ниже — минимальный контракт.

1. **Куда положить guard.** Один из вариантов: новый `src/config_loader.py` (предпочтительно, изолирует ответственность), либо функция `_validate_env()` в `src/pipeline.py` + вызов из `src/ui/app.py`. Импорт guard должен происходить **до** любого использования env-переменных.
2. **Сообщения.** Используйте русскоязычные сообщения из backlog §4.2 «Решение» (1–3) как baseline. Допустима ремарка «См. также: docs/user_guide/04_troubleshooting.md».
3. **Тесты.** `tests/test_env_validation.py` — три сценария:
   - (a) `.env.txt` без `.env` → `SystemExit` / явное исключение с упоминанием `ren`.
   - (b) только `.env.example` → файл `.env` создан, переменные доступны.
   - (c) `.env` существует, но `OLLAMA_MODEL` пустой → fail с подсказкой.
4. **Smoke-update.** `tests/test_arm_deployment_runbook.py` — добавить кейс «после удаления `.env` запуск guard создаёт его из `.env.example`».
5. **Runbook.** В [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md) §1.4 добавить ссылку «BL-50 startup-guard скажет вам об этом автоматически».

### ✅ DoD

- [ ] Guard реализован, импортируется до использования env-переменных.
- [ ] `tests/test_env_validation.py` — три сценария зелёные.
- [ ] Smoke `tests/test_arm_deployment_runbook.py` зелёный с новым кейсом.
- [ ] Runbook §1.4 содержит ссылку на BL-50.
- [ ] [`docs/user_guide/04_troubleshooting.md`](docs/user_guide/04_troubleshooting.md) — раздел «`.env` не найден» обновлён.
- [ ] CHANGELOG-запись `CODE: BL-50 .env startup validation`.
- [ ] PR согласован Product Owner и смёржен в `main`.
- [ ] Backlog v1.5 §0.6 строка BL-50 → `✅ Closed` со ссылкой на PR.

### 📦 Scope Note
🟢 **Изолированная задача** — `src/config_loader.py` (или эквивалент) + `tests/test_env_validation.py` + 2–3 строки в runbook/user guide. Не трогает RAG-пайплайн, ADR-001, LLM-провайдеры.
🔒 **Никакого silent rename `.env.txt → .env`** — пользователь должен явно подтвердить (через сообщение об ошибке + ручной `ren`). Auto-copy разрешён только из `.env.example` (там нет секретов).
```

---

### 4.2. BL-51 — Автодетект пути к Ollama (P1)

**Suggested title:**
```
`BL-51`: Auto-detect Ollama installation path + PATH guidance for ARM (Windows)
```

**Suggested body:**

```markdown
**Labels:** `code`, `priority:P1`, `sprint:4`, `pilot-readiness`, `area:llm`, `os:windows`
**Milestone:** `Sprint 4 — Pilot Readiness & Automation`
**Linked Backlog:** `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` §4.3 + `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` §0.6 BL-51
**Depends On:** — (parallel-safe c BL-50, BL-54)
**Source of problem:** [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), отчёт тестировщика §1.5 / Проблема #2

### 🎯 Цель
Снять зависимость от ручной правки PATH на каждом новом АРМ через автодетект пути к `ollama.exe` (`shutil.which` + fallback на стандартные Windows-пути) + явный шаг `setx PATH` в runbook §1.

### 👤 User Story
**Как** Бизнес-Аналитик с разным `%USERNAME%` на своём АРМ,
**Я хочу** не подставлять полный путь `C:\Users\<me>\AppData\Local\Programs\Ollama\ollama.exe` в каждую команду runbook,
**Чтобы** runbook был воспроизводим без правки под каждого пользователя и без ручного вмешательства в системный PATH.

### 🛡 Контракт и Ограничения

| Параметр | Требование |
|----------|------------|
| **Поиск исполняемого файла** | Порядок: `shutil.which("ollama")` → `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` → `C:\Program Files\Ollama\ollama.exe`. Если ничего не найдено — детерминированная ошибка с инструкцией. |
| **Логирование** | Найденный путь логируется один раз на старте `OllamaProvider`, после `sanitize_log_record` (BL-23). |
| **OS-агностичность** | Linux/macOS fallback-paths оставить как комментарий-TODO; критично только Windows-цепочка для АРМ. |
| **Runbook** | §1 содержит шаг «Добавьте Ollama в PATH» с `setx PATH "%PATH%;%LOCALAPPDATA%\Programs\Ollama"` и предупреждением о необходимости перезапустить CMD. |

### 📋 Рекомендации к реализации

1. **Точка изменения.** В [`src/llm/client.py`](src/llm/client.py) `OllamaProvider.__init__` или равноценная фабричная функция — вспомогательный `_resolve_ollama_executable()`.
2. **Тесты.** `tests/test_ollama_resolution.py`:
   - mock `shutil.which("ollama") -> None` + наличие файла по стандартному пути → возвращается стандартный путь;
   - mock `shutil.which("ollama") -> "/usr/bin/ollama"` → возвращается значение from PATH;
   - оба источника пустые → исключение с инструкцией.
3. **Runbook.** Перед текущим §1.5 добавить шаг §1.4a «Добавьте Ollama в PATH (`setx PATH ...`)» + предупреждение «перезапустите CMD, чтобы изменение вступило в силу».
4. **Связь с runbook §6.** Обновить строку «Connection refused» с указанием на BL-51 guard.

### ✅ DoD

- [ ] `_resolve_ollama_executable()` реализован в `src/llm/client.py`.
- [ ] `tests/test_ollama_resolution.py` зелёный (3 сценария).
- [ ] Runbook §1 содержит шаг «setx PATH» c явным предупреждением о перезапуске CMD.
- [ ] Smoke-прогон runbook на чистой Windows 11 без ручной правки PATH успешно выполняет `ollama serve` / `ollama pull qwen2.5:7b`.
- [ ] CHANGELOG-запись `CODE: BL-51 auto-detect Ollama path`.
- [ ] PR согласован Product Owner и смёржен в `main`.
- [ ] Backlog v1.5 §0.6 строка BL-51 → `✅ Closed` со ссылкой на PR.

### 📦 Scope Note
🟢 **Лёгкая задача** — одна функция + тесты + 1 параграф в runbook. Не затрагивает GigaChat / OpenRouter / fallback-цепочку.
🟡 **Зависимость от пилота:** триггер успеха — smoke на чистой Windows 11 без manual PATH edit; PO утверждает после ARM retest.
```

---

### 4.3. BL-54 — 🔴 Восстановить file uploader в режиме «📊 Анализ ТЗ» (P0, PILOT BLOCKER)

**Suggested title:**
```
`BL-54`: 🔴 Restore file uploader in «📊 Анализ ТЗ» mode (pilot blocker — regress BL-41)
```

**Suggested body:**

```markdown
**Labels:** `code`, `priority:P0`, `sprint:4`, `pilot-blocker`, `area:ui`, `regression`
**Milestone:** `Sprint 4 — Pilot Readiness & Automation`
**Linked Backlog:** `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` §4.6 + `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` §0.6 BL-54
**Depends On:** `BL-28` (ExportRouter, ✅ Closed), `BL-29` (UI export selector, ✅ Closed), `BL-41` (UI refactor, ✅ Closed — источник регрессии)
**Source of problem:** [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182), отчёт тестировщика §1.8 / Проблема #5; скриншоты «ожидаемый vs фактический UI».

### 🎯 Цель
Восстановить основной use-case пилота «массовая проверка тендерного ТЗ» — file upload (`.xlsx`/`.docx`, ≤ 10 МБ) → выбор формата отчёта → запуск анализа → скачивание результата — потерянный в BL-41 UI refactor; согласовать поведение `src/ui/app.py::_run_analysis_mode` с [`docs/user_guide/02_interface_elements.md`](docs/user_guide/02_interface_elements.md) §2 и [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md) §1.8.

### 👤 User Story
**Как** Бизнес-Аналитик, готовящий ответ на тендерное ТЗ,
**Я хочу** в режиме «📊 Анализ ТЗ» загрузить `.xlsx`/`.docx`-файл с требованиями, выбрать формат отчёта и скачать результат,
**Чтобы** массово проверить десятки/сотни требований за один прогон, как описано в user guide §2 и runbook §1.8.

### 🛡 Контракт и Ограничения

| Параметр | Требование |
|----------|------------|
| **Соответствие user guide** | UI в режиме «📊 Анализ ТЗ» точно отражает [`docs/user_guide/02_interface_elements.md`](docs/user_guide/02_interface_elements.md) §2 («📎 Файл тендерного ТЗ» + format selector + «Скачать отчет»). |
| **Поддерживаемые форматы in** | `.xlsx`, `.docx` (см. CONCEPT §4 FR-01). Лимит 10 МБ (NFR-09). |
| **Поддерживаемые форматы out** | `xlsx`, `docx`, `md` через существующий `ExportRouter` (BL-28). |
| **NFR-03 (Latency)** | Запуск анализа на типичном тестовом файле — ≤ 15 мин на CPU-only. |
| **Архитектура** | Сохраняется BL-41 паттерн компонентов (`src/ui/components/`). Текущий query-style flow либо удаляется, либо переносится под флаг `ui.analysis_query_mode: true` (default `false`) в [`configs/ui_config.yaml`](configs/ui_config.yaml). |
| **Label** | `«📊 Анализ ТЗ»` в [`src/ui/constants.py`](src/ui/constants.py) — **без изменений** (соответствует user guide §2). |
| **PII** | Имена загружаемых файлов проходят `sanitize_log_record` перед логированием. |

### 📋 Рекомендации к реализации

> 💡 **Архитектурное решение** — см. backlog §4.6 «Решение» (пункты 1–6). Ниже — выжимка.

1. **Новый компонент.** `src/ui/components/analysis_uploader.py` — `st.file_uploader` + валидация расширения + лимит 10 МБ (NFR-09). Возвращает path / handle.
2. **Перепись `_run_analysis_mode`.** В [`src/ui/app.py`](src/ui/app.py) (lines 996-1027 backlog reference) — заменить текущий `st.text_area`-flow на: `uploaded_file = analysis_uploader.render()` → `st.radio` для формата (через `EXPORT_FORMAT_LABELS` из `src/ui/constants.py:46-50`) → кнопка «🚀 Запустить анализ» → `src.pipeline.run_pipeline(file_path, output_format)` → `ExportRouter` (BL-28) → `st.download_button`.
3. **Подсохранение query-style.** Под опциональным флагом `ui.analysis_query_mode: true` в [`configs/ui_config.yaml`](configs/ui_config.yaml) (default `false`). Это снимает риск ломать BL-43 E2E, которые могли опираться на текущий путь.
4. **Тесты.**
   - `tests/test_ui_modes.py` — кейсы upload + format + download (mock pipeline + mock Streamlit context).
   - `tests/test_ui_components.py` — кейсы для `analysis_uploader.render()` (валидация расширения, лимит размера).
5. **Smoke-update.** `tests/test_arm_deployment_runbook.py` — кейс «runbook §1.8 выполняется автоматически» (file uploader виден + download активен).
6. **E2E retest.** BL-43 audit ([`docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md`](docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md)) повторно зелёный **с дополнительным сценарием** «UI upload → analyse → download».
7. **Скриншоты в PR.** «До» (фактический UI на ARM testing) + «После» (восстановленный uploader). Загрузить в `docs/screenshots/bl-54/` или приложить в PR.

### ✅ DoD

- [ ] При запуске `streamlit run src/ui/app.py` и выборе «📊 Анализ ТЗ» отображается file uploader с подписью из user guide §2 («📎 Файл тендерного ТЗ»).
- [ ] Загрузка `test_data/sample_tz.xlsx` → выбор формата `.xlsx` → клик «🚀 Запустить анализ» → за ≤ 15 мин генерируется отчёт; кнопка «Скачать отчёт» активна.
- [ ] `tests/test_ui_modes.py` и `tests/test_ui_components.py` зелёные локально и в CI.
- [ ] Smoke `tests/test_arm_deployment_runbook.py` (BL-45) подтверждает выполнимость runbook §1.8 без модификаций.
- [ ] E2E BL-43 повторно зелёный, с дополнительным сценарием «UI upload → analyse → download».
- [ ] Скриншот «после» в PR соответствует ожидаемому UI из [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182).
- [ ] Тестировщик [@G-Ivan-A](https://github.com/G-Ivan-A) подтверждает закрытие проблемы #5 пилотного тестирования.
- [ ] CHANGELOG-запись `CODE: BL-54 restore file uploader in «📊 Анализ ТЗ»` под `[Unreleased]`.
- [ ] Backlog v1.5 §0.6 строка BL-54 → `✅ Closed` со ссылкой на PR.
- [ ] PR согласован Product Owner и смёржен в `main`.

### 📦 Scope Note
🔴 **PILOT BLOCKER** — без BL-54 основной use-case пилота недоступен.
🟡 **Effort uncertainty:** 2 дня — если переиспользуется старый путь из `src/app.py` (M); 3 дня — при полной интеграции с BL-41 рефакторингом (M+).
🟢 **Label не меняется:** «📊 Анализ ТЗ» в `src/ui/constants.py` соответствует user guide §2 → не трогаем.
🟢 **CONCEPT / ADR не меняются:** FR-01 (Парсинг входных файлов) уже описывает целевое поведение; BL-54 — восстановление, не новое требование.
```

---

## 5. Изменения в реестрах после Accepted PO

### 5.1. Sync `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` §0.6

После Accepted PO в §0.6 v1.5 строки **BL-50, BL-51, BL-54** обновляются:

| ID | Задача | Приоритет | Статус | Зависимости | Обоснование | DoD |
|----|--------|-----------|--------|-------------|-------------|-----|
| BL-50 | `.env` startup validation | P0 | 🟡 In Progress | — | Sprint 4 (issue [#187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)); sub-issue TBD после Accepted PO | `tests/test_env_validation.py` зелёный, runbook §1.4 ссылается на BL-50, CHANGELOG-запись `CODE: BL-50` |
| BL-51 | Auto-detect Ollama installation path | P1 | 🟡 In Progress | — | Sprint 4 (issue [#187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)); parallel-safe c BL-50 | `tests/test_ollama_resolution.py` зелёный, runbook §1 содержит `setx PATH` шаг |
| **BL-54** | **🔴 Restore file uploader in «📊 Анализ ТЗ» mode** | **P0** | 🟡 In Progress | BL-28, BL-29, BL-41 (все ✅ Closed) | **Pilot blocker** (issue [#187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)); регресс BL-41, src/ui/app.py | `tests/test_ui_modes.py`, `tests/test_ui_components.py` зелёные; E2E BL-43 повторно зелёный с upload-сценарием |

> **Замечание:** обновление §0.6 v1.5 выносится в **отдельный
> docs-only PR после Accepted PO этого kickoff**. В текущем PR #188
> §0.6 v1.5 НЕ модифицируется — это сохраняет docs-only-инвариант
> backlog v1.5 (артефакт PR #183) до явного согласия PO.

### 5.2. CHANGELOG.md

В текущий PR #188 добавляется запись в `[Unreleased]` Documentation:

```markdown
- **DOCUMENTATION: issue #187 — Sprint 4 (BL-50, BL-51, BL-54) kickoff document**
  - Sprint 4 kickoff plan: `docs/analysis/2026-05-20_sprint-4-kickoff_v1.md`
  - Готовые формулировки sub-issues для BL-50, BL-51, BL-54 (см. kickoff §4).
  - Definition of Ready / Definition of Done зафиксированы; entry-критерий — Accepted ревью PR #183 + закрытие Hot-fix Sprint (#186).
  - Документ остаётся `Draft → Review`; код и GitHub sub-issues — после Accepted PO.
```

После Sprint 4 (отдельным PR за каждую BL): записи `CODE: BL-50 / BL-51 / BL-54` под `[Unreleased]`.

---

## 6. Риски и митигация

| # | Риск | Влияние | Митигация |
|---|------|---------|-----------|
| R1 | BL-54 — недооценка effort из-за глубины BL-41 рефакторинга | Sprint 4 не закрывается в плановое окно, пилот сдвигается | Стартовать BL-54 первым; в течение первого дня выбрать вариант M (re-use legacy path) или M+ (integration); зафиксировать решение в PR description |
| R2 | BL-50 — silent rename `.env.txt → .env` мог бы быть удобнее, но опасен (потеря секретов) | Регрессия безопасности (NFR-04) | Контракт §4.1 запрещает silent rename; auto-copy разрешён только из `.env.example` |
| R3 | BL-51 — `setx PATH` требует перезапуска CMD; пользователь может пропустить шаг | UX-регрессия, false negative «Ollama не установлен» | Явное предупреждение в runbook §1; `_resolve_ollama_executable()` дополнительно ищет в стандартных путях даже без PATH |
| R4 | BL-43 E2E может покраснеть после изменения `_run_analysis_mode` (BL-54) | Smoke-gate ломается, нужна правка тестов | Под флагом `ui.analysis_query_mode: true` сохраняется legacy-flow для BL-43 совместимости (см. backlog §4.6 «Решение» п.3) |
| R5 | Параллельные PR BL-50 / BL-51 могут конфликтовать в CHANGELOG.md | Merge-конфликт | Каждый PR добавляет запись в **конец** Documentation/Code-секции `[Unreleased]`; конфликт ловится тривиально |
| R6 | BL-48 (installer PoC) может стартовать раньше времени и блокировать ревью Sprint 4 | Рассеяние фокуса | BL-48 явно вынесен в параллельную ветку (§1.4); не входит в DoD Sprint 4 |

---

## 7. Рекомендации (priority MUST / SHOULD / MAY)

### 7.1. MUST (необходимое условие старта Sprint 4)

| # | Действие | Кому | Триггер |
|---|----------|------|---------|
| M1 | Approve PR [#188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188) (этот kickoff) | PO ([@G-Ivan-A](https://github.com/G-Ivan-A)) | После ознакомления с §4 формулировками |
| M2 | Создать sub-issues для BL-50, BL-51, BL-54 по формулировкам §4 | PO | Сразу после approve PR #188 |
| M3 | Открыть три отдельных feature-branches `issue-<bl-50-num>-...`, `issue-<bl-51-num>-...`, `issue-<bl-54-num>-...` | Code Agent / Developer | После создания sub-issues |
| M4 | В отдельном docs-only PR обновить v1.5 §0.6 (статусы → `🟡 In Progress`, ссылки на sub-issues) | konard / Code Agent | После M2 |

### 7.2. SHOULD

| # | Действие | Обоснование |
|---|----------|-------------|
| S1 | Стартовать BL-54 первым (даже до BL-50/BL-51) | Pilot blocker; ранний старт даёт буфер на M+ путь (3 дня) |
| S2 | Назначить BL-50 и BL-51 одному developer'у | Близкая природа задач (config / env), легче переиспользовать `tests/test_arm_deployment_runbook.py` baseline |
| S3 | После merge BL-50 → опубликовать комментарий в [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) с подтверждением закрытия Проблемы #1 | Прозрачность для тестировщика, who initiated the testing report |
| S4 | Перед закрытием Sprint 4 — заполнить [`docs/analysis/2026-06-05_sprint-4-execution-report_v1.md`](2026-06-05_sprint-4-execution-report_v1.md) по [шаблону](sprint-execution-report_template.md) | Прецедент Sprint 1 (`2026-05-17_sprint-1-execution-report_v1.md`) |

### 7.3. MAY

| # | Действие | Когда |
|---|----------|-------|
| Y1 | Расширить `analysis_uploader` поддержкой `.pdf`-ТЗ (out-of-scope MVP, но логичное расширение) | Sprint 5+, если есть запрос пилота |
| Y2 | Унифицировать `tests/test_env_validation.py` и `tests/test_ollama_resolution.py` в общий runbook-fixture | После закрытия BL-50 + BL-51, отдельный refactor PR |
| Y3 | Подвесить BL-50/BL-51 guards под общий `--strict-startup` CLI-флаг | Sprint 5+, если появится pre-flight CI job |

---

## 8. Открытые вопросы для PO

1. **Hot-fix vs Sprint 4 переплетение.** Если Hot-fix Sprint ([issue #186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186)) задерживается, допустимо ли стартовать BL-50 (P0) параллельно с BL-52 (P0 hot-fix) — оба правят `.env`-цепочку, но не пересекаются по файлам?
2. **BL-54 fallback под флагом.** Согласовываем ли мы вариант «оставить legacy query-mode под флагом `ui.analysis_query_mode: true`» (см. backlog §4.6 «Решение» п.3), или переходим на upload-only flow без backward compat?
3. **Sub-issue creation owner.** Подтверждаете, что готовые формулировки §4.1/4.2/4.3 копируете в GitHub UI лично, или предпочитаете, чтобы konard открыл их через `gh issue create` после Accepted PO?
4. **Sprint 4 milestone label.** Создавать ли GitHub Milestone «Sprint 4 — Pilot Readiness & Automation» с due date 2026-06-05 для группировки трёх sub-issues + retest comment в #182?

---

## 9. Ссылки

- **Issue:** [#187 — Sprint 4 start 200526](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)
- **PR:** [#188 (этот kickoff)](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188)
- **Бэклог-источник:** [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §4.2 / §4.3 / §4.6 / §7
- **Основной реестр:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md) §0.6
- **Testing report:** [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (источник BL-50..BL-56)
- **Hot-fix Sprint:** [issue #186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186) (BL-52, BL-56)
- **Source regression:** [issue #168 / BL-41](https://github.com/G-Ivan-A/clarify-engine-ai/issues/168) (UI refactor)
- **User guide:** [`docs/user_guide/02_interface_elements.md`](../user_guide/02_interface_elements.md) §2 (BL-44)
- **ARM runbook:** [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1.4 / §1.5 / §1.8 (BL-45)
- **BL-43 E2E baseline:** [`docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md`](../audit/2026-05-20_bl-43-smoke-e2e-report_v1.md)
- **Стандарт именования:** [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1
- **Прецедентные issues:** [#178 / BL-46](https://github.com/G-Ivan-A/clarify-engine-ai/issues/178), [#180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180)
- **Прецедентный Sprint Report:** [`docs/analysis/2026-05-17_sprint-1-execution-report_v1.md`](2026-05-17_sprint-1-execution-report_v1.md)
- **Шаблон execution report:** [`docs/analysis/sprint-execution-report_template.md`](sprint-execution-report_template.md)

---

## 10. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-20 | Первая версия Sprint 4 kickoff (issue [#187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187), PR [#188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188)). Фиксирует scope (BL-50, BL-51, BL-54), Definition of Ready / Definition of Done, готовые формулировки sub-issues, риски и открытые вопросы для PO. Документ — docs-only, статус `Draft → Review`. |
