# Sprint 4 Parallel — BL-48 Installer PoC — Kickoff (issue #190)

## 🗂 Метаданные

- **Дата:** 2026-05-20
- **Версия:** v1
- **Тип документа:** `analysis` (Sprint Kickoff / Plan, см. [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 §3.2)
- **Статус:** `Draft → Review`
- **Автор:** konard (AI issue solver, по [issue #190](https://github.com/G-Ivan-A/clarify-engine-ai/issues/190))
- **Ревьюер:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Связанный PR:** [#191](https://github.com/G-Ivan-A/clarify-engine-ai/pull/191)
- **Бэклог-источник:** [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §7 «План реализации» → строка **Sprint 4 (parallel)**
- **Research-источник:** [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md) §2.1, §3.1, §6, §8.3
- **Основной реестр статусов:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.5.md) §0.6 (строка BL-48)
- **Связанные issues:** [#180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180) (installer research), [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (ARM pilot testing report), [#186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186) (Hot-fix Sprint BL-52/BL-56), [#187](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187) (Sprint 4 BL-50/BL-51/BL-54 kickoff)

---

## 1. Понимание контекста

### 1.1. Verbatim formulation of the task

> **Sprint 4 (параллельный)** ([issue #190](https://github.com/G-Ivan-A/clarify-engine-ai/issues/190), автор PO — Ivan Gulienko):
>
> Сформировать issue на Hot-fix-релиз в соответствии с
> [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
> — раздел 7 — **Sprint 4 (parallel)**.

### 1.2. Интерпретация задачи

Формулировка наследует шаблон «issue на Hot-fix-релиз», но явная ссылка на
§7 бэклога указывает не на Hot-fix Sprint (BL-52, BL-56) и не на основной
Sprint 4 (BL-50, BL-51, BL-54), а на отдельную строку:

| Sprint | Задачи | Артефакт |
|--------|--------|----------|
| **Sprint 4 (parallel)** | BL-48 (installer PoC) использует BL-50..BL-52 как зависимости | PoC `clarify-setup.cmd` ([BL-47 §6](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md#6-proof-of-concept-plan)) |

Настоящий документ формализует параллельный поток **BL-48 — ARM Installer
PoC** и содержит готовую формулировку GitHub issue для Product Owner (§4).
Кодовые изменения (`scripts/install/clarify-setup.py`, `clarify-setup.cmd`,
тесты и runbook updates) не входят в этот PR и стартуют только после
Accepted-ревью PO, как зафиксировано в backlog §7.

### 1.3. Цель Sprint 4 (parallel)

Снизить барьер первого запуска на АРМ Windows 10/11 для бизнес-аналитика:
заменить ручное выполнение 12+ команд из [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md)
на тонкий, читаемый и тестируемый bootstrapper:

- `scripts/install/clarify-setup.py` — Python wizard для First-Run;
- `scripts/install/clarify-setup.cmd` — CMD wrapper для двойного клика из
  «Проводника»;
- `scripts/install/migrations/.gitkeep` — заглушка будущего migration-layer;
- `tests/test_install_first_run.py` — smoke на временной директории с моками
  Ollama и тяжёлых внешних команд.

Минимальный PoC должен пройти шаги [1/8]..[8/8] из BL-47 research §3.1:
проверка среды → структура директорий → venv/pip → `.env` → Ollama/model
→ smoke import → ярлыки → итоговое сообщение с URL `http://localhost:8501`.

### 1.4. Границы параллельности

BL-48 **зависит от контрактов** BL-50..BL-52, но не обязан ждать полного
закрытия всех реализаций для подготовки issue:

- **BL-52** уже закрывает синхронизацию `OLLAMA_MODEL=qwen2.5:7b` в
  `.env.example` (Hot-fix Sprint, PR #189).
- **BL-50** задаёт runtime guard `.env` / `.env.txt`; installer wizard должен
  создавать `.env` из `.env.example` и не делать silent rename `.env.txt`.
- **BL-51** задаёт Ollama path contract; installer wizard должен использовать
  тот же порядок поиска `ollama`: `PATH` → `%LOCALAPPDATA%\Programs\Ollama`
  → `C:\Program Files\Ollama`.

До merge BL-50/BL-51 исполнитель BL-48 может зафиксировать интерфейс через
моки и utility-функции, но финальный PR BL-48 должен синхронизироваться с
реальными runtime guards, чтобы не создать второй источник истины.

---

## 2. Анализ текущего состояния

### 2.1. Что изучено

- [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §6.2 и §7 — BL-48 как параллельный поток, использующий BL-50..BL-52.
- [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md)
  §2.1 — рекомендован двухслойный подход; Sprint 4 MUST = Python
  bootstrapper + CMD wrapper, Inno Setup отложен.
- BL-47 research §2.2 — контракт `.gitignore`-артефактов: `.env`, `venv/`,
  `chroma_data/`, `logs/`, `data/incoming/`, `data/output/`, `configs/`.
- BL-47 research §3.1 — целевой First-Run wizard [1/8]..[8/8].
- BL-47 research §6 — PoC plan: PoC-1 `clarify-setup.cmd`, PoC-2 KB Update UI,
  PoC-3 TZ upload tab.
- BL-47 research §7 — installer risks R-INST-01..05.
- [`docs/analysis/2026-05-20_sprint-4-kickoff_v1.md`](2026-05-20_sprint-4-kickoff_v1.md)
  §1.4 — основной Sprint 4 явно выносит BL-48 в отдельную параллельную ветку.
- [`docs/standards/naming-convention.md`](../standards/naming-convention.md)
  v1.1 §3.2 — тип `analysis` валиден для sprint kickoff/plan-документов.

### 2.2. Scope Sprint 4 (parallel)

| ID | Задача | Приоритет | Effort | depends_on | Артефакт после Accepted |
|----|--------|-----------|--------|-----------|--------------------------|
| **BL-48** | ARM Installer L1: `clarify-setup.cmd` + `clarify-setup.py` First-Run wizard | P1 | M (≤ 8 ч) | BL-50, BL-51, BL-52 | PR с `scripts/install/clarify-setup.py`, `scripts/install/clarify-setup.cmd`, `scripts/install/migrations/.gitkeep`, `tests/test_install_first_run.py`, runbook quick-start note |

Дополнительные PoC-направления из BL-47 research §6 (**BL-48.1** KB Update UI,
**BL-48.2** TZ upload tab, **BL-48.3** ADR-011 draft) остаются рекомендациями
для последующих отдельных issues. Их не следует автоматически включать в
первый BL-48 PR, чтобы не смешивать installer wizard с UI-функциями и не
конфликтовать с BL-54 (restore file uploader).

### 2.3. Ограничения анализа

- Документ **не открывает** GitHub issue автоматически — готовая формулировка
  приведена в §4 для копирования Product Owner'ом или создания через `gh issue create`
  после Accepted-ревью.
- Документ **не реализует** installer code; это соответствует backlog §7, где
  старт любой задачи требует Accepted PO.
- Inno Setup, WebDAV/S3/cloud adapters, keyring и полный config-migration
  framework остаются out-of-scope первого BL-48 PoC.

---

## 3. Definition of Ready и Definition of Done

### 3.1. Definition of Ready — старт BL-48 implementation

- [ ] [PR #191](https://github.com/G-Ivan-A/clarify-engine-ai/pull/191) (этот kickoff) → `Accepted` PO.
- [ ] [PR #189](https://github.com/G-Ivan-A/clarify-engine-ai/pull/189) / issue #186 (BL-52, BL-56) merged в `main`; `.env.example` содержит `OLLAMA_MODEL=qwen2.5:7b`.
- [ ] BL-50 и BL-51 имеют утверждённые issue-контракты из [PR #188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188), даже если реализация ещё идёт параллельно.
- [ ] PO подтверждает, что первый PR BL-48 ограничен Installer L1 / First-Run wizard, а BL-48.1/BL-48.2/BL-48.3 выносятся отдельно.
- [ ] Backlog v1.5 §0.6 строка BL-48 переведена `📝 New → 🟡 In Progress` отдельным docs-only PR после Accepted PO.

### 3.2. Definition of Done — закрытие BL-48

- [ ] `scripts/install/clarify-setup.py` реализует First-Run wizard [1/8]..[8/8] из BL-47 research §3.1.
- [ ] `scripts/install/clarify-setup.cmd` запускает Python bootstrapper из корня проекта и корректно пробрасывает аргументы.
- [ ] Wizard создаёт runtime-директории (`chroma_data/`, `logs/`, `data/incoming/`, `data/output/`, `knowledge_base/vector_store/`) без перезаписи пользовательских данных.
- [ ] Wizard создаёт `.env` из `.env.example`, не делает silent rename `.env.txt`, не логирует секреты и совместим с BL-50 guard.
- [ ] Wizard проверяет Ollama через общий с BL-51 контракт поиска binary и модель `qwen2.5:7b`; скачивание модели требует явного подтверждения.
- [ ] `tests/test_install_first_run.py` мокает внешние команды и проверяет создание ожидаемых файлов/директорий, `.env`, install-log events и idempotent rerun.
- [ ] Smoke import `python -c "import src"` выполняется внутри wizard как отдельный шаг с понятной ошибкой при fail.
- [ ] Runbook [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) получает короткий раздел «Quick-start через `clarify-setup.cmd`»; ручной runbook остаётся как fallback.
- [ ] CHANGELOG.md содержит запись `CODE: BL-48 ARM Installer L1 clarify-setup.cmd`.
- [ ] Backlog v1.5 §0.6 строка BL-48 → `✅ Closed` со ссылкой на merged PR.

---

## 4. Готовая формулировка issue BL-48 (для PO)

> Текст ниже готов для копирования в GitHub UI. Структура соответствует
> прецедентам [issue #178 / BL-46](https://github.com/G-Ivan-A/clarify-engine-ai/issues/178),
> [issue #180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180)
> и Sprint 4 kickoff [PR #188](https://github.com/G-Ivan-A/clarify-engine-ai/pull/188).

### 4.1. BL-48 — ARM Installer L1 (`clarify-setup.cmd` First-Run wizard)

**Suggested title:**
```
BL-48: ARM Installer L1 — clarify-setup.cmd First-Run wizard
```

**Suggested body:**

```markdown
**Labels:** `code`, `priority:P1`, `sprint:4`, `pilot-readiness`, `area:installer`, `windows`
**Milestone:** `Sprint 4 — Pilot Readiness & Automation`
**Linked Backlog:** `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` §6.2 + §7; `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` §0.6 BL-48
**Research Source:** `docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md` §2.1, §2.2, §3.1, §6
**Depends On:** BL-50 (`.env` startup validation), BL-51 (Ollama path autodetect), BL-52 (`OLLAMA_MODEL=qwen2.5:7b` sync)
**Source of problem:** [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) ARM pilot test report; [issue #180](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180) BL-47 research

### 🎯 Цель

Реализовать Installer L1 PoC для АРМ Windows 10/11: `scripts/install/clarify-setup.cmd` + `scripts/install/clarify-setup.py`, который проводит бизнес-аналитика через First-Run setup без ручного выполнения 12+ команд из runbook.

### 👤 User Story

**Как** Бизнес-Аналитик, устанавливающий `clarify-engine-ai` на свой АРМ впервые,
**Я хочу** запустить `clarify-setup.cmd` двойным кликом и получить готовую локальную Streamlit-среду,
**Чтобы** не выполнять вручную venv/pip/.env/Ollama/smoke steps и снизить риск ошибок вроде `.env.txt`, wrong `OLLAMA_MODEL` или отсутствующего PATH для Ollama.

### 🛡 Контракт и Ограничения

| Параметр | Требование |
|----------|------------|
| **Entrypoints** | `scripts/install/clarify-setup.py` — основная логика; `scripts/install/clarify-setup.cmd` — thin wrapper из корня проекта, аргументы пробрасываются в Python. |
| **First-Run steps** | Wizard проходит шаги [1/8]..[8/8] из BL-47 research §3.1: environment → directories → venv/pip → `.env` → Ollama/model → smoke import → shortcuts → final URL/log summary. |
| **Idempotency** | Повторный запуск не перезаписывает `.env`, пользовательские файлы, `logs/`, `chroma_data/`, `data/incoming/`, `data/output/`; существующие директории помечаются `OK/EXISTS`. |
| **`.env` contract** | Если `.env` отсутствует — копировать `.env.example → .env`. Если `.env.txt` найден без `.env` — показывать ошибку с `ren .env.txt .env`; silent rename запрещён. Секреты не логируются. |
| **Ollama contract** | Поиск binary: `PATH` → `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` → `C:\Program Files\Ollama\ollama.exe`. Модель по умолчанию: `qwen2.5:7b`. `ollama pull` требует явного подтверждения. |
| **Logging** | `logs/install.jsonl` содержит structured events по шагам, duration, status, error code. Содержимое `.env` и API keys не пишутся. |
| **External commands** | Все тяжёлые команды (`venv`, `pip install`, `ollama pull`, shortcut creation) обёрнуты в testable functions, чтобы `tests/test_install_first_run.py` мог мокать их без реального pip/Ollama. |
| **Windows-first** | Основной target — Windows CMD. На Linux/macOS тестируется только pure-Python contract через mocks. |
| **Out of scope** | Inno Setup `.exe`, `--silent`, `--update`, WebDAV/S3/cloud, keyring, full config migrations, KB Update UI, TZ upload tab. |

### 📋 Рекомендации к реализации

1. Создать модуль `scripts/install/clarify-setup.py` с явными функциями:
   `check_environment()`, `ensure_directories()`, `ensure_venv()`,
   `ensure_env_file()`, `check_ollama()`, `run_smoke_import()`,
   `create_shortcuts()`, `write_install_event()`.
2. Команды выполнять через общий helper `run_step(command, *, dry_run=False)`,
   чтобы тесты могли подменить runner.
3. Для PoC shortcut creation можно сделать best-effort: на не-Windows вернуть
   `SKIPPED`, на Windows использовать PowerShell COM (`WScript.Shell`).
4. Добавить `scripts/install/migrations/.gitkeep`, но не реализовывать migration runner.
5. Добавить `tests/test_install_first_run.py`:
   - fresh tmp project → создаются директории, `.env`, log file;
   - `.env` already exists → не перезаписывается;
   - `.env.txt` without `.env` → deterministic error с подсказкой `ren`;
   - mocked Ollama missing model → фиксируется prompt branch без реального download;
   - rerun idempotent.
6. Обновить `docs/runbooks/arm-deployment-ivan.md`: в начале добавить Quick-start через `scripts\install\clarify-setup.cmd`; ручные шаги оставить как fallback/debug path.
7. В PR description приложить transcript wizard-run на mock/dry-run и указать, что full Windows VM smoke остаётся manual verification gate.

### ✅ DoD

- [ ] `scripts/install/clarify-setup.py` и `scripts/install/clarify-setup.cmd` добавлены.
- [ ] `scripts/install/migrations/.gitkeep` добавлен.
- [ ] First-Run wizard реализует шаги [1/8]..[8/8] из BL-47 research §3.1.
- [ ] `.env` создаётся из `.env.example`; `.env.txt` даёт actionable error; secrets не логируются.
- [ ] Ollama binary/model checks используют контракт BL-51 и default model BL-52 (`qwen2.5:7b`).
- [ ] `tests/test_install_first_run.py` зелёный локально и в CI.
- [ ] `pytest tests/test_install_first_run.py tests/test_env_example_runbook_sync.py tests/test_arm_deployment_runbook.py` зелёный.
- [ ] Runbook содержит Quick-start section для `clarify-setup.cmd`.
- [ ] CHANGELOG-запись `CODE: BL-48 ARM Installer L1 clarify-setup.cmd` добавлена.
- [ ] Backlog v1.5 §0.6 строка BL-48 → `✅ Closed` со ссылкой на PR.

### 📦 Scope Note

🟢 **Installer L1 only:** этот issue закрывает PoC-1 из BL-47 research §6.
🟡 **Dependencies:** BL-50/BL-51 contracts должны быть переиспользованы, чтобы не появился второй источник истины для `.env` и Ollama path.
🔴 **Не смешивать с BL-54:** восстановление file uploader в режиме «📊 Анализ ТЗ» делается в основном Sprint 4, не в installer PR.
⚪ **Follow-ups:** BL-48.1 (KB Update UI), BL-48.2 (TZ upload tab), BL-48.3 (ADR-011) открывать отдельными issues после PO-согласования.
```

---

## 5. Изменения в реестрах после Accepted PO

### 5.1. Sync `docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md` §0.6

После Accepted PO в §0.6 v1.5 строка **BL-48** обновляется:

| ID | Задача | Приоритет | Статус | Зависимости | Обоснование | DoD |
|----|--------|-----------|--------|-------------|-------------|-----|
| BL-48 | ARM Installer L1 (`clarify-setup.cmd`) | P1 | 🟡 In Progress | BL-50, BL-51, BL-52 | Sprint 4 (parallel), issue [#190](https://github.com/G-Ivan-A/clarify-engine-ai/issues/190); PoC-1 из BL-47 research §6 | `scripts/install/clarify-setup.py`, `.cmd`, `tests/test_install_first_run.py`, runbook Quick-start, CHANGELOG `CODE: BL-48` |

Обновление §0.6 v1.5 выносится в отдельный docs-only PR после Accepted PO,
чтобы текущий PR #191 оставался kickoff-документом, как PR #188 для основного
Sprint 4.

### 5.2. CHANGELOG.md

В текущий PR #191 добавляется запись в `[Unreleased]` Documentation:

```markdown
- **DOCUMENTATION: issue #190 — Sprint 4 parallel BL-48 installer PoC kickoff.**
  Сформирован kickoff-документ `docs/analysis/2026-05-20_sprint-4-parallel-kickoff_v1.md`
  по §7 «Sprint 4 (parallel)» backlog v1.0. Документ фиксирует scope BL-48
  Installer L1 (`clarify-setup.cmd` + `clarify-setup.py`), Definition of Ready /
  Definition of Done, зависимости BL-50..BL-52, риски и готовое issue-body для PO.
```

После реализации BL-48 отдельным PR добавляется запись `CODE: BL-48 ...`.

---

## 6. Риски и митигация

| # | Риск | Влияние | Митигация |
|---|------|---------|-----------|
| R1 | BL-48 стартует до стабилизации BL-50/BL-51 и дублирует `.env`/Ollama logic | Два источника истины, расхождение поведения wizard и runtime | До merge BL-50/BL-51 использовать моки и интерфейсный контракт; финальный PR синхронизировать с фактическими helpers/guards |
| R2 | Installer PR разрастается до KB Update UI + TZ upload tab | Перегрузка ревью, конфликт с BL-54 UI работой | Первый BL-48 PR ограничить Installer L1; BL-48.1/48.2/48.3 открыть отдельно |
| R3 | `pip install -r requirements.txt` тяжёлый и нестабилен в CI/Linux | Тесты медленные или flaky | Unit/smoke тесты мокают runner; реальный Windows VM smoke отмечается как manual verification в PR description |
| R4 | `.env` или пользовательские данные перезаписываются при rerun | Потеря секретов / артефактов пилота | Idempotency tests: existing `.env`, `logs/`, `data/incoming/`, `chroma_data/` не меняются |
| R5 | Windows shortcuts сложно тестировать на CI | Ложные падения на Linux runner | Shortcut step best-effort: на non-Windows `SKIPPED`; Windows-specific behavior покрыть unit-тестом генерации PowerShell-команды |
| R6 | Runbook и wizard расходятся | БА следует устаревшей инструкции | В BL-48 PR обновить runbook Quick-start и явно оставить ручные шаги как fallback/debug path |

---

## 7. Рекомендации (priority MUST / SHOULD / MAY)

### 7.1. MUST

| # | Действие | Кому | Триггер |
|---|----------|------|---------|
| M1 | Approve PR [#191](https://github.com/G-Ivan-A/clarify-engine-ai/pull/191) (этот kickoff) | PO | После проверки scope BL-48 |
| M2 | Создать issue BL-48 по формулировке §4 | PO / konard после согласования | После Accepted PR #191 |
| M3 | Держать первый BL-48 PR в scope Installer L1 only | Исполнитель BL-48 | При старте implementation |
| M4 | Синхронизировать BL-48 с BL-50/BL-51 helpers перед merge | Исполнитель BL-48 | После появления соответствующих PR |

### 7.2. SHOULD

| # | Действие | Обоснование |
|---|----------|-------------|
| S1 | Реализовать `--dry-run` / mocked-runner режим сразу | Ускоряет тестирование и даёт PR transcript без реального pip/Ollama |
| S2 | Вынести install logging в маленький helper | Потом переиспользуется BL-48.1 rollback / KB update flow |
| S3 | Добавить runbook Quick-start в начало, а не в конец | БА видит простой путь первым; ручной путь остаётся для debug |
| S4 | После merge BL-48 оставить комментарий в issue #182 | Тестировщик увидит, что problem class «ручная установка слишком сложна» закрывается отдельным потоком |

### 7.3. MAY

| # | Действие | Когда |
|---|----------|-------|
| Y1 | Добавить `clarify-setup.cmd --repair` | Sprint 5, после первого demo feedback |
| Y2 | Добавить `clarify-setup.cmd --silent --env-from=...` | Когда IT-отделу понадобится multi-ARM rollout |
| Y3 | Создать ADR-011 до кода BL-48 | Если PO хочет архитектурный review до implementation |

---

## 8. Открытые вопросы для PO

1. **Scope BL-48.** Подтверждаем, что issue #190 формирует только BL-48 Installer L1 / PoC-1, а BL-48.1 (KB Update UI), BL-48.2 (TZ upload tab) и BL-48.3 (ADR-011) будут отдельными issues?
2. **Ordering vs BL-50/BL-51.** Можно ли стартовать реализацию BL-48 на моках до merge BL-50/BL-51, если финальный PR перед merge синхронизирует общий `.env`/Ollama contract?
3. **Windows VM smoke.** Нужен ли обязательный ручной smoke на чистой Windows 10/11 VM до merge BL-48, или достаточно CI tests + dry-run transcript для первого PoC?
4. **Issue creation owner.** Создаёт ли PO issue BL-48 вручную по §4, или konard должен открыть его через `gh issue create` после Accepted PR #191?

---

## 9. Ссылки

- **Issue:** [#190 — Sprint 4 (параллельный)](https://github.com/G-Ivan-A/clarify-engine-ai/issues/190)
- **PR:** [#191 (этот kickoff)](https://github.com/G-Ivan-A/clarify-engine-ai/pull/191)
- **Бэклог-источник:** [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](../backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md) §6.2 / §7
- **Research:** [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md) §2 / §3 / §6 / §8
- **Основной Sprint 4 kickoff:** [`docs/analysis/2026-05-20_sprint-4-kickoff_v1.md`](2026-05-20_sprint-4-kickoff_v1.md)
- **Hot-fix Sprint:** [issue #186](https://github.com/G-Ivan-A/clarify-engine-ai/issues/186), [PR #189](https://github.com/G-Ivan-A/clarify-engine-ai/pull/189)
- **ARM runbook:** [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md)
- **Стандарт именования:** [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1
- **Прецедентные issues:** [#178 / BL-46](https://github.com/G-Ivan-A/clarify-engine-ai/issues/178), [#180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180), [#187 / Sprint 4 kickoff](https://github.com/G-Ivan-A/clarify-engine-ai/issues/187)

---

## 10. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-20 | Первая версия Sprint 4 parallel kickoff (issue [#190](https://github.com/G-Ivan-A/clarify-engine-ai/issues/190), PR [#191](https://github.com/G-Ivan-A/clarify-engine-ai/pull/191)). Фиксирует scope BL-48 Installer L1, зависимости BL-50..BL-52, Definition of Ready / Definition of Done, готовую формулировку issue, риски и открытые вопросы для PO. Документ — docs-only, статус `Draft → Review`. |
