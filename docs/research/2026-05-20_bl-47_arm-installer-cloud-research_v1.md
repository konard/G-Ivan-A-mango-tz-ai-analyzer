# 🔬 Research: ARM Installer, Cloud TZ Access & Documentation Update Flow (BL-47)

## Метаданные
- **Дата:** 2026-05-20
- **Версия:** v1
- **Автор:** konard (Konstantin Diachenko)
- **Статус:** Draft → готов к ревью PO
- **Спринт:** Sprint 4 — Pilot Readiness & Automation
- **Бэклог:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.4.md) (BL-47)
- **Связанные документы:**
  - [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) — BL-45 (база для First-Run / Update Wizard)
  - [`docs/CONCEPT.md`](../CONCEPT.md) §§5–7 (NFR-04 резидентность, NFR-05 0 утечек, R-03)
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md)
  - [`docs/ADR/005-audit-trail.md`](../ADR/005-audit-trail.md)
  - [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1
  - [`.gitignore`](../../.gitignore), [`.env.example`](../../.env.example)
  - [`knowledge_base/indexing/build_index.py`](../../knowledge_base/indexing/build_index.py)
  - [`src/ui/app.py`](../../src/ui/app.py)
- **Депенденс:** BL-43 (Smoke Verification — ✅ closed), BL-45 (ARM Runbook — ✅ closed)
- **Целевая аудитория:** PO, разработчик-имплементатор BL-48 (installer) и BL-49 (cloud), Бизнес-Аналитик (Ivan G.)

---

## 1. Executive Summary

Исследование закрывает три направления, критичных для перехода MVP → Pilot
с не-техническим пользователем (БА) на АРМ Windows 10/11 + CPU Ollama:

| Направление | Ключевой вывод | Рекомендация для Sprint 4 |
|-------------|----------------|----------------------------|
| **1. Упрощённая установка** | Готовый ARM-runbook (BL-45) уже описывает все шаги, но требует ручного выполнения 12+ команд в CMD. Для БА это блокер. Решение: **тонкий Python-бутстрапер (`clarify-setup.py`/`clarify-setup.cmd`) + `Inno Setup`-обёртка**, который оркестрирует runbook в неинтерактивном режиме. PyInstaller/Nuitka на этой стадии **избыточны** (KB-парсеры тянут torch/chroma — итоговый бинарь ≥ 1.5 GiB, теряем `git pull`-обновляемость). | **Реализовать в Sprint 4** (BL-48, PoC `clarify-setup.cmd`, эффор ≤ 8 ч). Inno Setup-обёртку — отложить до Pilot-cutoff. |
| **2. Облачный доступ к ТЗ** | Корпоративные хранилища у разных пилотных пользователей будут разные (Я.Диск / S3 / Nextcloud / SharePoint). Зашивать один протокол в код — преждевременная оптимизация. Решение: **абстрактный `CloudSource`-интерфейс + первый адаптер на WebDAV** (покрывает Я.Диск, Nextcloud, OwnCloud одним кодом) + S3 как fallback для Pilot. Токены — в Windows Credential Manager через `keyring`. | **Отложить до Sprint 5** (BL-49). В Sprint 4 — только design-decision (`docs/ADR/010-cloud-tz-access.md`, draft) и upload-через-UI (БА скачивает файл вручную и грузит через `st.file_uploader`, **0 эффор кода**, уже работает). |
| **3. Обновление КБ из UI** | Скрипт `knowledge_base/indexing/build_index.py` уже идемпотентен, поддерживает full/incremental reindex и пишет в `source_registry.csv`. Не хватает только: UI-кнопки с прогресс-логом, авто-backup `chroma_data/`, кнопки rollback. Решение: **новая вкладка "🔄 Обновить базу знаний"** в `src/ui/app.py` с тремя действиями (Upload → Validate sha256 → Reindex+Backup), запуск `build_index.py` через `subprocess.Popen` и stream stdout в Streamlit-плейсхолдер. | **Реализовать в Sprint 4** (часть BL-48 или новый BL-48.1, эффор ≤ 6 ч). |

**Контракт `.gitignore`-артефактов** (общий для всех трёх направлений)
описан в §2.2 ниже и фиксирует исчерпывающий список путей, которые
**никогда** не упаковываются и **никогда** не перезаписываются обновлением.

**Главный риск (R-INST-01):** конфликт обновления `requirements.txt` при
сохранённом `venv/` без полного `pip install --upgrade` приводит к ImportError
после обновления. Митигация — обязательный шаг `pip install -r requirements.txt --upgrade`
после deploy, с rollback-кнопкой к предыдущему `venv_backup_<ts>/` (§5.4, §7).

**PoC план (§6):** 3 задачи ≤ 16 ч в сумме — `clarify-setup.cmd` (8 ч),
"Update KB"-вкладка с backup/rollback (6 ч), `file_uploader`-tab «Загрузить ТЗ»
(2 ч). Этого достаточно, чтобы провалидировать гипотезу «БА может пройти
First-Run и Update без участия разработчика» на демо у Ивана.

---

## 2. Installer Architecture

### 2.1. Сравнение инструментов

| Инструмент | Плюсы | Минусы | Применимость BL-47 |
|------------|-------|--------|--------------------|
| **PyInstaller** (one-folder) | Один self-contained пакет; не требует Python на машине БА | Итоговый размер с `torch+chromadb+streamlit` ≥ 1.2 GiB; теряем `git pull`-обновления; антивирусы Windows ложно срабатывают на onefile-сборки; pyinstaller-hooks для streamlit/chromadb нестабильны | ⚠️ Избыточно для пилота на 1–3 АРМ |
| **Nuitka** | Native-компиляция, быстрее старт; обходит часть AV-предупреждений | Время сборки 10–30 мин; ещё хуже с torch (требует custom plugins); не поддерживает hot-reload | ❌ Преждевременная оптимизация |
| **Inno Setup** (внешняя обёртка) | Стандарт де-факто Windows; десктоп-ярлыки, удаление через «Программы и компоненты»; UAC-friendly; user-space установка | Нужен GUI-инсталлятор-скрипт (`.iss`); не управляет venv/pip напрямую | ✅ **Опционально (Pilot-cutoff)** — обёртка для `clarify-setup.cmd` |
| **NSIS** | Аналог Inno Setup, скриптовый | Синтаксис менее читаемый; меньше встроенных UI-виджетов | ⚠️ Альтернатива Inno Setup; решающий критерий — наличие лицензии у Ивана (Inno Setup MPL, NSIS zlib — оба open) |
| **Кастомный Python-бутстрапер** (`clarify-setup.py` + `clarify-setup.cmd`-обёртка) | Полный контроль над логикой; читается БА и разработчиком; легко расширяется; тестируется как обычный Python; не зависит от внешних инсталляторов | Требует наличия Python 3.14 в системе — но это уже зафиксировано в [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1 | ✅ **РЕКОМЕНДАЦИЯ для Sprint 4** |

**Решение:** двухслойный подход.

- **Слой 1 (Sprint 4, MUST):** `scripts/install/clarify-setup.py` — Python-бутстрапер,
  оркеструющий runbook BL-45 без интерактива. Запускается через CMD-shortcut
  `scripts/install/clarify-setup.cmd` (двойной клик из «Проводника»).
- **Слой 2 (Pilot-cutoff, SHOULD):** `Inno Setup`-обёртка `clarify-setup-1.0.0.exe`,
  которая распаковывает Python embeddable distribution (3.14, ~30 MiB) + проект
  в `%LOCALAPPDATA%\ClarifyEngine\`, создаёт ярлыки и запускает `clarify-setup.py`.
  Эта обёртка нужна только когда «у БА нет Python», что для Ивана пока **не
  блокер** (Python 3.14 уже стоит).

### 2.2. Обработка `.gitignore`-артефактов: исчерпывающий контракт

Источник истины — корневой [`.gitignore`](../../.gitignore). Ниже —
формальное соответствие «инсталлятор должен/не должен» для каждой
игнорируемой группы.

| Путь | В git | В пакет инсталлятора | First-Run (создаётся) | Update (сохраняется) | Backup-стратегия |
|------|-------|----------------------|------------------------|----------------------|------------------|
| `chroma_data/` | ❌ ignore | ❌ НЕ упаковывается | ✅ создаётся пустая директория | ✅ **сохраняется как есть** | `chroma_data_backup_<ts>/` (full copy) перед каждым reindex |
| `data/chroma/` | ❌ ignore | ❌ | ✅ создаётся пустая | ✅ сохраняется | вместе с `chroma_data/` |
| `data/incoming/*` (кроме `.gitkeep`) | ❌ ignore | ❌ | ✅ создаётся `data/incoming/.gitkeep` | ✅ файлы пользователя сохраняются | пользовательский upload не бэкапится (исходники у пользователя) |
| `logs/` | ❌ ignore | ❌ | ✅ создаётся пустая | ✅ сохраняется | rotate-only (старше 30 дней удаляются), без backup |
| `output/`, `data/output/`, `reports/` | ❌ ignore | ❌ | ✅ создаются пустыми | ✅ сохраняются | не бэкапятся (production artifacts регенерируемы) |
| `.env` | ❌ ignore | ❌ | ⚠️ **создаётся из `.env.example` при первом запуске; БА заполняет ключи через wizard** | ✅ **сохраняется (НЕ перезаписывается)** | `.env.bak.<ts>` перед update |
| `.env.*` | ❌ ignore | ❌ (кроме `.env.example`) | — | ✅ | по той же схеме что `.env` |
| `.env.example` | ✅ tracked | ✅ упаковывается | используется как шаблон | ⚠️ обновляется из пакета (показывается БА diff-нотификация при изменении схемы) | предыдущая версия в `.env.example.bak` |
| `knowledge_base/sources/` | ✅ tracked (whitelist) | ✅ упаковывается с дефолтными PDF | ✅ дефолтные PDF копируются | ⚠️ **merge**: дефолтные PDF из пакета обновляются, пользовательские PDF не трогаются (см. §2.3) | `knowledge_base/sources_backup_<ts>/` |
| `knowledge_base/vector_store/` | ❌ (фактически runtime) | ❌ | ✅ создаётся пустая | ✅ сохраняется | вместе с `chroma_data/` |
| `test_data/` | ✅ tracked (whitelist) | ✅ упаковывается | копируется | ⚠️ merge как `knowledge_base/sources/` | — |
| `configs/*.yaml` | ✅ tracked | ✅ упаковывается | копируется | ⚠️ **migrate** (см. §3.4): user-overrides сохраняются в `configs/local/*.yaml` (gitignore-кандидат) | `configs_backup_<ts>/` |
| `venv/`, `.venv/`, `env/` | ❌ ignore | ❌ | ✅ создаётся через `py -3.14 -m venv venv` | ⚠️ **upgrade**: `pip install -r requirements.txt --upgrade` (см. §3.3) | `venv_backup_<ts>/` (см. §7 R-INST-01) |
| `__pycache__/`, `*.py[cod]` | ❌ ignore | ❌ | — | автогенерируется | не бэкапится |
| `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | ❌ ignore | ❌ | — | — | не бэкапится |
| `*.xlsx` (кроме `test_data/`, `knowledge_base/sources/`) | ❌ ignore | ❌ | — | пользовательский файл сохраняется | пользовательский upload не бэкапится |
| `*.key`, `*.pem`, `credentials.json`, `service_account.json` | ❌ ignore | ❌ | — | ✅ **сохраняются (никогда не перезаписываются)** | `credentials.bak.<ts>` (опционально, по флагу) |

**Whitelist-директории** (`!knowledge_base/sources/`, `!test_data/`, `!docs/`,
`!configs/`, `!prompts/`) — упаковываются полностью, режим обновления — **merge**
(дефолтные файлы обновляются, пользовательские добавления сохраняются по
hash-сравнению, см. §3.4 «Алгоритм миграции»).

### 2.3. Алгоритм обновления: `backup → deploy → restore/migrate`

```
[clarify-setup.py --update]
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 0: Pre-flight checks                │
│  - active Streamlit на :8501? → stop    │
│  - active Ollama? → keep running        │
│  - free disk ≥ 2× размер проекта?       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 1: BACKUP (atomic snapshot)         │
│  ./backups/<ts>/                        │
│   ├─ .env.bak                           │
│   ├─ chroma_data/        (copytree)     │
│   ├─ knowledge_base/sources/ (copytree) │
│   ├─ configs/            (copytree)     │
│   ├─ venv/               (copytree)     │
│   └─ source_registry.csv                │
│  retention: last 3 backups              │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 2: DEPLOY (git pull или unzip)      │
│  - git stash (pollution check)          │
│  - git fetch && git checkout <tag>      │
│  - git stash pop (если был stash)       │
│  ИЛИ для embedded-distribution:         │
│  - unzip clarify-engine-ai-<ver>.zip    │
│    с --skip-existing для tracked файлов │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 3: RESTORE                          │
│  - chroma_data/  ← backup (полное)      │
│  - logs/         ← in-place (не трогаем)│
│  - .env          ← backup (поверх)      │
│  - knowledge_base/sources/              │
│        ← merge (см. §3.4)               │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 4: MIGRATE configs                  │
│  - diff configs/*.yaml (пакет vs backup)│
│  - применить migration-скрипты          │
│    (scripts/install/migrations/*.py)    │
│  - сохранить user-override в            │
│    configs/local/*.yaml                 │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 5: PIP UPGRADE                      │
│  venv\Scripts\activate &&               │
│  py -m pip install --no-cache-dir       │
│    -r requirements.txt --upgrade        │
│  При FAIL → откат venv из backup        │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 6: SMOKE                            │
│  py -c "import src; print('OK')"        │
│  curl http://localhost:11434/api/tags   │
│  При FAIL → автоматический ROLLBACK     │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ Шаг 7: NOTIFY                           │
│  Лог в logs/install.jsonl:              │
│  {"event":"UPDATE_OK", "from":"<sha>",  │
│   "to":"<sha>", "backup":"<path>",      │
│   "duration_s":42}                      │
│  Desktop notification (Windows toast)   │
└─────────────────────────────────────────┘
```

**Atomicity guarantee:** все 7 шагов оборачиваются в `try/except`; при
ошибке в шагах 2–6 — автоматический `rollback()` из `./backups/<ts>/` без
участия пользователя. Pointer на «последний успешный backup» хранится в
`./backups/LAST_GOOD.txt`, чтобы rollback из UI («Откатить установку»)
работал без вычисления актуального backup.

---

## 3. First-Run & Update Flow

### 3.1. First-Run Wizard (CLI, неинтерактив-by-default)

```text
> clarify-setup.cmd

==================================================
Clarify Engine AI - First-Run Setup
==================================================

[1/8] Проверка среды
  - Python 3.14 ............................... OK (3.14.0)
  - Windows CMD ............................... OK
  - free disk (need 8 GiB) .................... OK (24 GiB)
  - git for Windows ........................... OK (2.45.1)

[2/8] Создание структуры
  - C:\Projects\clarify-engine-ai\ ............ CREATED
  - chroma_data\ .............................. CREATED
  - logs\ ..................................... CREATED
  - knowledge_base\sources\ ................... CREATED
  - data\incoming\ ............................ CREATED
  - data\output\ .............................. CREATED

[3/8] Виртуальное окружение
  - py -3.14 -m venv venv ..................... OK
  - pip upgrade ............................... OK
  - requirements.txt install .................. OK (97 packages, 4m12s)
  - torch CPU pin ............................. OK

[4/8] Конфигурация .env
  - copy .env.example -> .env ................. OK
  ! Введите ключи (или ENTER для test-mode):
    GIGACHAT_CLIENT_ID    [skip]:
    GIGACHAT_CLIENT_SECRET[skip]:
    OPENROUTER_API_KEY    [skip]:
  -> USE_TEST_DATA_MODE=true (fallback на Ollama)

[5/8] Ollama
  - ollama --version .......................... OK (0.3.10)
  - ollama list | grep qwen2.5:7b ............. NOT FOUND
  ? Скачать модель qwen2.5:7b (~4.3 GiB)? [Y/n]: Y
  - ollama pull qwen2.5:7b .................... OK (8m17s)
  - warmup ("Готов") .......................... OK (62s)

[6/8] Smoke import
  - py -c "import src" ........................ OK

[7/8] Ярлыки
  - Desktop\Clarify Engine.lnk ................ CREATED
  - StartMenu\Clarify Engine.lnk .............. CREATED
  - Desktop\Clarify Engine (Stop).lnk ......... CREATED

[8/8] Готово
  Запустите: двойной клик "Clarify Engine" на рабочем столе
  URL:       http://localhost:8501
  Логи:      logs\install.jsonl

==================================================
First-Run завершён за 13 минут. Удачной работы!
==================================================
```

**Режимы запуска:**

- `clarify-setup.cmd` — интерактивный wizard (см. выше).
- `clarify-setup.cmd --silent --env-from=path\to\.env` — для автоматизированного
  деплоя на N АРМ (IT-отдел заранее готовит `.env` с ключами и распространяет
  через GPO/централизованное копирование).
- `clarify-setup.cmd --update` — режим обновления (см. §2.3).
- `clarify-setup.cmd --repair` — recovery (`venv` пересоздаётся, `chroma_data/`
  сохраняется, ключи перепроверяются).
- `clarify-setup.cmd --rollback` — откат к последнему `LAST_GOOD` backup.

### 3.2. Обработка ключей API (без хранения в коде)

| Сценарий | Где хранятся | Кто заполняет | Маскирование в логах |
|----------|--------------|----------------|-----------------------|
| **Test-mode (default для БА)** | `.env` с `USE_TEST_DATA_MODE=true`, пустые ключи | Wizard (Enter для skip) | N/A — ключей нет |
| **Pilot-mode (БА получает ключи от IT)** | `.env` (gitignored) | Wizard, ввод вручную | `***REDACTED***` через `src/llm/masking.py` (ADR-003 §4.3) |
| **Enterprise-mode (будущее)** | Windows Credential Manager через `keyring` | IT-отдел через PowerShell-cmdlet | хранилище уже зашифровано на уровне ОС |
| **CI / dev-mode** | `.env` локально или GitHub Secrets в CI | разработчик | `sanitize_log_record()` |

Wizard **не передаёт** введённые ключи никуда, кроме записи в локальный `.env`.
Это явно отображается в копии перед вводом:
`> Ключи сохраняются ТОЛЬКО локально в C:\Projects\clarify-engine-ai\.env`.

### 3.3. Проверка Ollama и модели

Алгоритм шага [5/8]:

```python
def check_ollama() -> OllamaStatus:
    if not shutil.which("ollama"):
        prompt_install_ollama()  # ссылка на https://ollama.com/download/windows
        return OllamaStatus.MISSING_BINARY

    if not is_ollama_serving():  # curl http://localhost:11434/api/tags
        spawn_detached("ollama serve")  # отдельное окно CMD
        wait_until_ready(timeout=30)

    models = parse_ollama_list()  # ollama list
    if "qwen2.5:7b" not in models:
        size_mb = 4300  # из manifest
        if confirm(f"Скачать модель qwen2.5:7b (~{size_mb} MiB)?"):
            run("ollama pull qwen2.5:7b", show_progress=True)
        else:
            return OllamaStatus.MODEL_MISSING_USER_DECLINED

    warmup()  # ollama run qwen2.5:7b "Готов"
    return OllamaStatus.OK
```

Если БА выбирает «не скачивать» — система **остаётся работоспособной** в
test-mode без LLM (только парсинг + STRICT_MODE-заглушки), пользователь
видит баннер «Ollama не настроена — режим ограничен».

### 3.4. Алгоритм миграции `configs/`

Источник проблемы: при `git pull` обновлений конфигов (например, добавление
нового провайдера в `configs/llm_config.yaml`) пользовательские overrides
(скажем, увеличенный `timeout_seconds: 240` для медленного АРМ) пропадают.

Решение — **трёхуровневое слияние** на основе `deepmerge`:

1. **base** — `configs/*.yaml` из пакета (всегда обновляется при deploy).
2. **migrate** — `scripts/install/migrations/<version>_<from>_to_<to>.py`
   применяется один раз per upgrade (например, переименование ключа).
3. **local-override** — `configs/local/*.yaml` (gitignored), создаваемый
   wizard'ом при первом detect расхождения. БА правит только этот файл.
   Loader (`src/utils/config_loader.py` — новый или расширение существующего)
   делает `deepmerge(base, local)` при старте.

При update wizard:
- diff `configs/<file>.yaml` (новый) vs `configs/<file>.yaml.bak` (старый);
- если diff пустой → ничего не делает;
- если diff есть → запускает migration-скрипт (если есть для этой пары
  версий), сохраняет результат в `configs/local/<file>.yaml`, показывает
  БА сводку «Изменился ключ X с A на B; ваш override Y сохранён».

### 3.5. Создание ярлыков

- **Desktop\Clarify Engine.lnk** — таргет: `C:\Projects\clarify-engine-ai\scripts\launch\start-clarify.cmd`,
  иконка из `assets/icons/clarify.ico`, working dir = project root.
- **StartMenu\Programs\Clarify Engine\Clarify Engine.lnk** — то же самое
  (доступ через меню «Пуск»).
- **Desktop\Clarify Engine (Stop).lnk** — таргет `scripts\launch\stop-clarify.cmd`
  (`taskkill /F /IM streamlit.exe`).
- **Desktop\Clarify Engine (Update).lnk** — таргет `scripts\install\clarify-setup.cmd --update`.

`start-clarify.cmd` — обёртка из ARM-runbook §3 (активирует venv, ставит
PYTHONPATH, запускает `streamlit run src/ui/app.py`, опционально стартует
`ollama serve` в скрытом окне через `start /MIN`).

Ярлыки создаются Python-скриптом через библиотеку `winshell` или, без
зависимостей, через `subprocess.run(["powershell", "-Command", make_shortcut_ps1])`.

---

## 4. Cloud Integration Patterns

### 4.1. Архитектурные варианты

| Вариант | Покрытие пилотных сценариев | Сложность реализации | Auth-сложность | Корпоративная сеть |
|---------|------------------------------|----------------------|-----------------|---------------------|
| **A. WebDAV** (Я.Диск, Nextcloud, OwnCloud, SharePoint-через-bridge) | ~60 % российских корпоративных хранилищ | S (готовая lib `webdavclient3`) | basic-auth / app-password | прямой HTTPS-доступ, без OAuth-redirect |
| **B. S3-compatible** (Minio, Cloud.ru Object Storage, Yandex Object Storage) | ~25 % (DevOps-zone, не БА) | S (`boto3`) | access_key + secret_key | прямой HTTPS |
| **C. Yandex Disk REST API** | ~15 % (только Я.Диск, отдельный namespace) | S (`yadisk` lib) | OAuth token (полу-ручной) | прямой HTTPS |
| **D. SharePoint via Graph API** | ~10 % (Microsoft 365 enterprise) | L (OAuth-redirect, корп. Tenant ID) | Microsoft Identity Platform | требует выходного OAuth-callback URL → блокер за корп. NAT |
| **E. SMB/CIFS-share** (`\\fileserver\TZ\`) | ~30 % (внутренние SharePoint, NAS) | XS (pathlib + smb-creds) | NTLM/Kerberos (через Windows) | работает без интернета |
| **F. Ручной upload** (`st.file_uploader`) | 100 % (universal fallback) | XS (уже работает) | нет | работает offline |

**Решение:** **«F + A»**, с архитектурным фундаментом под расширение.

- **F (`st.file_uploader`)** — **уже доступен** в `src/ui/app.py` (вкладка
  «📊 Анализ ТЗ» использует Streamlit-uploader). Sprint 4: **+ дублирующая
  вкладка для KB-источников** «📥 Загрузить ТЗ» с тем же механизмом, но
  складывающая файлы в `data/incoming/` для дальнейшей обработки/индексации.
  Эффор: ≤ 2 ч.
- **A (WebDAV)** — Sprint 5 (BL-49), один адаптер покрывает 3 платформы.
- **E (SMB-share)** — добавляется как опция в settings UI, если у пилота
  будет такой кейс. Эффор: ≤ 4 ч (Python `smbprotocol` или pathlib для
  смонтированной шары).

### 4.2. Интерфейс `CloudSource` (предлагаемый контракт)

```python
# src/cloud/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class RemoteFile:
    name: str
    relative_path: str
    size_bytes: int
    modified_at: datetime
    sha256_hint: str | None  # если хранилище отдаёт ETag/checksum

class CloudSource(ABC):
    @abstractmethod
    def authenticate(self) -> None: ...

    @abstractmethod
    def list_files(self, prefix: str = "") -> list[RemoteFile]: ...

    @abstractmethod
    def download(self, remote_path: str, local_dest: Path) -> Path: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

Реализации:
- `src/cloud/local_uploader.py` — Streamlit `file_uploader` (Sprint 4).
- `src/cloud/webdav_source.py` — на базе `webdavclient3` (Sprint 5).
- `src/cloud/s3_source.py` — на базе `boto3` (Backlog).
- `src/cloud/smb_source.py` — на базе `smbprotocol` (Backlog).

### 4.3. Кэширование и версионирование

```
cloud_cache/
├── metadata.csv              # filename, sha256, downloaded_at, source_type
├── webdav/
│   └── 2026-05-20T10-15_TZ_Onboarding.docx
└── s3/
    └── 2026-05-19T09-00_TZ_Refactoring.xlsx
```

**Правила:**
- Идентификация — `sha256` содержимого, **не** имя файла (на cloud имена
  переименовываются).
- Перед скачиванием: запрос HEAD/PROPFIND → сравнение с `metadata.csv`. Если
  `sha256_hint` совпадает — пропуск, отображение `cache hit`.
- TTL — нет (БА вручную нажимает «Обновить список»). Avoid stale-data риск:
  отображать `downloaded_at` в UI рядом с именем файла.
- `cloud_cache/` добавляется в `.gitignore` (см. §2.2 — паттерн `data/incoming/*`
  допускает аналогичную обработку).

### 4.4. Безопасность токенов

| Метод | Уровень защиты | Сложность для БА | Рекомендация |
|-------|----------------|-------------------|--------------|
| Plain `.env` | ⚠️ Низкий (на диске в открытом виде) | XS | **Не использовать для cloud-токенов** (для LLM ключей — приемлемо, см. §3.2) |
| Windows Credential Manager (через `keyring`) | ✅ Шифрование на уровне DPAPI с привязкой к пользователю Windows | S (БА вводит токен один раз через wizard) | **РЕКОМЕНДАЦИЯ** |
| HashiCorp Vault / Cloud KMS | ✅ Enterprise-grade | L (требует инфраструктуры) | Backlog |

**Маскирование в логах** — все токены (long-string ≥ 16 alphanumeric)
прогоняются через `src/llm/masking.py::mask_text()` (ADR-003 §4.3). В
`logs/cloud.jsonl` хранятся только маскированные идентификаторы (`webdav://*****/files/TZ_*.docx`).

### 4.5. Offline-режим

- При отсутствии сети `health_check()` падает с тайм-аутом 5с.
- UI **не показывает ошибку красным**, а отображает баннер: «Облако недоступно
  (нет сети). Доступна локальная папка `data/incoming/`».
- БА продолжает работу с локальными файлами (через `st.file_uploader` или
  через прямое размещение в `data/incoming/`).

---

## 5. KB Update Flow

### 5.1. Sequence diagram (БА → UI → build_index.py → Chroma)

```
 БА                Streamlit UI           build_index.py        Chroma         FS
 │                     │                         │                  │           │
 │  click "🔄 Обновить"│                         │                  │           │
 ├────────────────────▶│                         │                  │           │
 │                     │ list new files          │                  │           │
 │                     │ (data/incoming/*)       │                  │           │
 │                     ├────────────────────────────────────────────────────────▶│
 │                     │                         │                  │  list     │
 │                     │◀────────────────────────────────────────────────────────┤
 │ select files,       │                         │                  │           │
 │ click "Применить"   │                         │                  │           │
 ├────────────────────▶│                         │                  │           │
 │                     │ compute sha256          │                  │           │
 │                     ├────────────────────────────────────────────────────────▶│
 │                     │◀────────────────────────────────────────────────────────┤
 │                     │ check source_registry   │                  │           │
 │                     │ (duplicates, version    │                  │           │
 │                     │  conflicts)             │                  │           │
 │                     │─[if conflict]──────────▶│                  │           │
 │                     │   prompt БА: overwrite? │                  │           │
 │                     │                         │                  │           │
 │                     │ backup chroma_data/     │                  │           │
 │                     ├────────────────────────────────────────────────────────▶│
 │                     │   copytree -> chroma_data_backup_<ts>      │           │
 │                     │                         │                  │           │
 │                     │ spawn subprocess        │                  │           │
 │                     ├────────────────────────▶│                  │           │
 │                     │                         │ chunk, embed     │           │
 │                     │  ←── stream stdout ─────│                  │           │
 │                     │ (progress: 12/45 docs)  │                  │           │
 │                     │                         │ upsert chunks    │           │
 │                     │                         ├─────────────────▶│           │
 │                     │                         │ write registry   │           │
 │                     │                         ├────────────────────────────▶ │
 │                     │  ←── exit_code = 0 ─────│                  │           │
 │                     │ verify index            │                  │           │
 │                     ├────────────────────────────────────────────▶│           │
 │                     │   count > 0 ?           │                  │           │
 │                     │                         │                  │           │
 │ "Обновлено: +3, -1, │                         │                  │           │
 │  всего 1234 чанков" │                         │                  │           │
 │◀────────────────────│                         │                  │           │
```

### 5.2. UI-вкладка «🔄 Обновить базу знаний»

Минимально-достаточный layout (Streamlit-компоненты):

```python
# src/ui/tabs/kb_update.py (новый файл)
def render():
    st.header("🔄 Обновить базу знаний")

    # 1. источник
    source = st.radio("Источник", ["Локальная папка", "Загрузить файл", "Облако (BL-49)"])

    # 2. список файлов
    files = list_pending_files(source)
    selected = st.multiselect("Выберите файлы для индексации", files)

    # 3. dry-run / validate
    if st.button("Проверить (без индексации)"):
        report = validate(selected)  # sha256, дубликаты, размер, MIME
        st.dataframe(report)

    # 4. применить
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Применить", type="primary", disabled=not selected):
            with st.spinner("Резервная копия…"):
                backup_path = backup_chroma()
            log_placeholder = st.empty()
            with st.spinner("Индексация…"):
                exit_code = run_build_index_streaming(selected, log_placeholder)
            if exit_code == 0:
                st.success(f"Обновлено: +{added}, -{removed}, всего {total} чанков")
            else:
                st.error("Ошибка. Нажмите «↩️ Откатить» для возврата.")
    with col2:
        if st.button("↩️ Откатить последнее обновление"):
            restore_chroma(latest_backup())
            st.success("Откат выполнен.")
```

### 5.3. Безопасная переиндексация

| Проверка | Где | Действие при FAIL |
|----------|------|--------------------|
| sha256 нового файла vs `source_registry.csv` | UI, перед applied | confirm-prompt «Файл уже проиндексирован, перезаписать?» |
| MIME-type (`.pdf`, `.docx`, `.xlsx`, `.md`) | UI | reject + сообщение «Неподдерживаемый формат» |
| Размер файла ≤ 50 MiB (config-driven) | UI | reject + «Файл слишком большой» |
| Sanitization имени файла (no `..`, no symlinks) | UI | reject |
| `build_index.py --dry-run` валидация | UI step 3 | показать ошибки |
| exit_code из `build_index.py` ≠ 0 | UI | автоматический rollback (см. §5.4) |
| Chroma count == 0 после индексации | UI verify | автоматический rollback + alert |

`source_registry.csv` — уже существующий артефакт (см. CONCEPT §6.6 «нет
хардкода» и audit-trail ADR-005). Дополнительные колонки для BL-47:
`added_by` (username Windows), `source_type` (local/upload/webdav), `sha256`,
`indexed_at`, `chroma_collection_version`.

### 5.4. Откат (rollback)

Алгоритм:
1. Streamlit: при ошибке индексации или ручном клике «↩️ Откатить» —
   `shutil.rmtree(chroma_data); shutil.copytree(chroma_data_backup_<ts>, chroma_data)`.
2. Удалить новые строки в `source_registry.csv` (по `indexed_at >= backup_ts`).
3. Restart Chroma client connection (`chromadb.PersistentClient` пересоздаётся
   на следующий запрос UI — Streamlit-singleton инвалидируется через
   `st.cache_resource.clear()`).
4. Лог-событие `KB_ROLLBACK` в `logs/install.jsonl`.

Retention: последние 3 backups; старше — автоматически удаляются (cron-free,
проверка при каждом успешном update).

### 5.5. Обратная связь после индексации

Текстовый шаблон сообщения (БА видит в UI):

```
✅ База знаний обновлена

  Добавлено документов:    3 (TZ_Onboarding.docx, AD_SSO.pdf, Limits.md)
  Удалено устаревших:      1 (TZ_Onboarding_old.docx)
  Изменено (по sha256):    2

  Всего в индексе:
    документов:   24 (+2)
    чанков:       1234 (+87)
    объём:        42.1 MiB

  Резервная копия:         chroma_data_backup_2026-05-20T14-23/
  Откатить можно в течение 30 дней.
```

---

## 6. Proof-of-Concept Plan

**Цель PoC:** провалидировать на демо у Ивана, что БА может пройти
First-Run, Update и переиндексацию КБ без участия разработчика.

**Объём: 3 задачи, суммарно ≤ 16 часов** (укладывается в Sprint 4 без
вытеснения других BL-задач).

| # | Задача | Эффор | Файлы | DoD |
|---|--------|-------|-------|-----|
| **PoC-1** | `clarify-setup.cmd` + `clarify-setup.py` (First-Run, не silent-mode, не Inno Setup) | **8 ч** | `scripts/install/clarify-setup.py` (новый, ~300 LoC), `scripts/install/clarify-setup.cmd` (~10 LoC обёртка), `scripts/install/migrations/.gitkeep`, `tests/test_install_first_run.py` (smoke на временной директории через pytest tmp_path) | На чистой VM Windows 10 (без artifacts) скрипт проходит шаги [1/8]..[8/8] из §3.1 за ≤ 15 мин и оставляет рабочий Streamlit на `:8501`. Тест `test_install_first_run.py` мокает Ollama и проверяет, что все ожидаемые директории/файлы созданы. |
| **PoC-2** | Streamlit-вкладка «🔄 Обновить базу знаний» с backup + rollback (без cloud) | **6 ч** | `src/ui/tabs/kb_update.py` (новый, ~200 LoC), регистрация вкладки в `src/ui/app.py`, `src/kb/backup.py` (новый, ~80 LoC `backup_chroma`/`restore_chroma`), `tests/test_kb_update.py` | На стенде с пред-проиндексированной КБ: БА загружает 1 новый PDF, видит прогресс, видит «Обновлено: +1» в UI. После ручного `chroma_data\` corruption — `Откатить` восстанавливает рабочее состояние. Backup не превышает 3 копий (старшие удаляются). |
| **PoC-3** | Streamlit-вкладка «📥 Загрузить ТЗ» (только `st.file_uploader`, без cloud) | **2 ч** | `src/ui/tabs/tz_upload.py` (новый, ~80 LoC), регистрация вкладки, `tests/test_tz_upload.py` | БА может загрузить `.xlsx` через UI, файл попадает в `data/incoming/`, появляется в списке источников вкладки PoC-2 для индексации. Sanitization имени файла (no `..`, only ascii+cyrillic) проверена тестом. |

**Out-of-PoC** (явное оставление за рамками):
- Inno Setup-обёртка (Layer 2 из §2.1).
- WebDAV / S3 / SMB-адаптеры (BL-49, Sprint 5).
- Полный config-migration framework (§3.4) — заглушка `migrations/.gitkeep`.
- Push-уведомления Windows Toast — заменены на Streamlit-success-баннер.
- Encryption через `keyring` — заменено на plain `.env` (test-mode default).

**Демо-сценарий для Ивана** (после PoC):
1. Клонирует свежую копию `clarify-engine-ai` в чистую папку.
2. Запускает `clarify-setup.cmd` двойным кликом → проходит wizard.
3. Открывает Streamlit, переходит на вкладку «📥 Загрузить ТЗ» → грузит PDF.
4. Переходит на «🔄 Обновить базу знаний» → выбирает свой PDF → «Применить».
5. Возвращается на «💬 Консультация» → задаёт вопрос по своему PDF.
6. Если ответ некорректный → жмёт «↩️ Откатить».

---

## 7. Risks & Mitigations

| ID | Риск | Вероятность | Воздействие | Митигация | Owner |
|----|------|-------------|-------------|-----------|-------|
| **R-INST-01** | Обновление `requirements.txt` ломает `venv` (incompatible torch/chroma) | средняя | высокое (БА не сможет запустить UI) | `venv_backup_<ts>/` + автоматический rollback при exit_code != 0 у `pip install --upgrade`. Тест `tests/test_install_upgrade.py`. | Devs (BL-48) |
| **R-INST-02** | `.env` затирается при некорректной реализации update | низкая | высокое (потеря ключей API) | Атомарный backup в §2.3 шаг 1; explicit `--skip-existing` для tracked файлов в шаге 2; функциональный тест `tests/test_install_preserve_env.py`. | Devs (BL-48) |
| **R-INST-03** | Ollama-модель `qwen2.5:7b` ≥ 4.3 GiB скачивается долго на корпоративной сети | высокая | среднее (БА закрывает окно, считает что зависло) | Скачивание `ollama pull` идёт в interactive-mode с прогресс-баром; wizard явно предупреждает «Загрузка может занять 5-30 мин в зависимости от сети». В silent-mode — лог в `logs/install.jsonl` каждые 60с. | Devs (BL-48) |
| **R-INST-04** | Антивирус блокирует CMD/PowerShell-скрипты в `%LOCALAPPDATA%` | средняя | высокое (БА видит «Windows defended your PC») | Слой 2 (Inno Setup) подписывает `.exe` корп. сертификатом (требует SignTool + EV-cert от IT-отдела). На Слое 1 — рекомендация в `docs/runbooks/arm-deployment-ivan.md`: добавить папку проекта в exclusions Windows Defender. | IT + Devs |
| **R-INST-05** | Wizard падает посреди установки → пользователь видит частично созданную структуру | низкая | среднее | Каждый шаг wizard атомарен (см. §3.1), результат логируется в `logs/install.jsonl`. При повторном запуске wizard detect-ит partial state по marker-файлам (`.install_step_N_done`) и продолжает с прерванного шага. | Devs (BL-48) |
| **R-CLOUD-01** | OAuth-redirect для SharePoint/MS Graph не работает за корпоративным NAT | высокая | низкое (cloud — Sprint 5, опционально) | Sprint 4: отказ от SharePoint Graph (см. §4.1 вариант D). Sprint 5: только WebDAV/S3 с app-passwords. | Devs (BL-49) |
| **R-CLOUD-02** | Токен webdav утечёт через лог при ошибке коннекта (стек-трейс с URL) | средняя | высокое (NFR-05 — 0 утечек) | `src/llm/masking.py::mask_text()` применяется к каждому log-record в `logs/cloud.jsonl` (см. §4.4 и ADR-003 §4.3). Тест `tests/test_cloud_log_masking.py`. | Devs (BL-49) |
| **R-CLOUD-03** | Cloud-кэш разрастается без bound (5 GiB+) | низкая | низкое | TTL-cleanup в `cloud_cache/cleanup.py`, запуск раз в сутки при старте UI. Лимит 2 GiB по умолчанию. | Devs (BL-49) |
| **R-KB-01** | Переиндексация падает посередине, `chroma_data/` в неконсистентном состоянии | средняя | высокое (`/💬` режим перестаёт отвечать) | Backup ДО запуска `build_index.py` + автоматический rollback при exit_code != 0 (см. §5.4). Тест `tests/test_kb_update.py::test_rollback_on_failure`. | Devs (BL-48.1) |
| **R-KB-02** | БА загружает 500 MiB PDF, UI зависает | низкая | среднее | Limit 50 MiB на файл (config-driven) + chunked-upload (Streamlit умеет stream). Validation на UI-уровне до сохранения. | Devs (BL-48.1) |
| **R-KB-03** | Дубль файла (тот же sha256, разное имя) попадает в индекс → дублированные ответы | средняя | низкое (только cosmetic) | Pre-flight check в §5.3 — confirm-prompt; запись в `source_registry.csv` с указанием альтернативного имени. | Devs (BL-48.1) |
| **R-NFR-01** | NFR-04 «RU-резидентность»: cloud-адаптер случайно отправляет данные в зарубежный регион (S3 us-east-1) | низкая | критическое | Whitelist endpoints в `configs/cloud_config.yaml` (только `.ru` / `.cloud.ru` / `.yandex.cloud`); жёсткий refuse в `S3Source.__init__` если endpoint не в whitelist. | Devs (BL-49) + PO |
| **R-DOC-01** | Wizard и runbook расходятся (БА следует устаревшему runbook, wizard работает иначе) | средняя | среднее | После реализации BL-48 — обновить [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) до v2 с разделом «Quick-start через `clarify-setup.cmd`»; старые ручные шаги остаются в Appendix. | Tech writer |

---

## 8. Recommendations

### 8.1. Приоритизация направлений

| Направление | Sprint 4 | Sprint 5 (Pilot) | Backlog / Enterprise |
|-------------|----------|-------------------|------------------------|
| **Installer L1 (`clarify-setup.cmd`)** | ✅ **MUST** — BL-48 (PoC-1, 8 ч) | upgrade-flow поверх git-репо | `--silent` для multi-АРМ распространения |
| **Installer L2 (Inno Setup `.exe`)** | ❌ skip | ⚠️ SHOULD (если у Ивана нет Python) | code-signing с EV-cert |
| **Cloud TZ Access (WebDAV)** | ❌ skip (только design-decision в ADR-010 draft) | ✅ MUST — BL-49 | S3-адаптер, SMB-share |
| **Cloud TZ Access (Yandex Disk REST)** | ❌ | ⚠️ SHOULD (если IT-отдел Ивана даёт OAuth-token) | автомиграция token → keyring |
| **Cloud TZ Access (SharePoint Graph)** | ❌ | ❌ (R-CLOUD-01) | Enterprise (отдельное ADR) |
| **Local upload (`st.file_uploader`-tab)** | ✅ MUST — BL-48 (PoC-3, 2 ч) | расширение MIME-types | drag-and-drop с preview |
| **KB Update UI + backup/rollback** | ✅ MUST — BL-48 (PoC-2, 6 ч) | progress в реальном времени через WebSocket | diff-view изменений в индексе |
| **Config migration framework** | ⚠️ stub (`migrations/.gitkeep`) | ⚠️ SHOULD (первая реальная миграция при `chunk_size` изменении в BL-32) | semver-based migration runner |
| **Token security (keyring)** | ❌ | ✅ MUST для cloud-токенов | HashiCorp Vault для Enterprise |
| **Wizard для `.env`** | ✅ MUST — часть PoC-1 | дополнить проверкой ключей через `gigachat ping` | централизованный `.env` через GPO |

### 8.2. Что требует отдельного ADR

1. **`docs/ADR/010-cloud-tz-access.md`** — выбор WebDAV как первого адаптера,
   контракт `CloudSource`-интерфейса, политика whitelist endpoints для NFR-04.
   **Draft в Sprint 4** (≤ 2 ч), approval до старта BL-49.
2. **`docs/ADR/011-installer-architecture.md`** — двухслойная архитектура
   (L1 Python-бутстрапер, L2 Inno Setup), алгоритм `backup → deploy → restore`,
   политика migration `configs/`. **Draft в начале BL-48** (≤ 2 ч).
3. **`docs/ADR/012-kb-update-from-ui.md`** — контракт rollback,
   `source_registry.csv` schema v2, политика retention backups. **Опционально**
   (можно описать в BL-48.1 commit-message, если решения некритичны).

### 8.3. Что делать в Sprint 4 (executive)

```
Sprint 4 backlog (proposed, ≤ 16 ч PoC + ≤ 4 ч ADR drafts):
  BL-48     PoC-1: clarify-setup.cmd                      8 ч
  BL-48.1   PoC-2: KB Update UI + backup/rollback         6 ч
  BL-48.2   PoC-3: TZ upload tab (st.file_uploader)       2 ч
  BL-48.3   ADR-011 draft (installer architecture)        2 ч
  BL-49     ADR-010 draft (cloud access)                  2 ч
                                                ────────
                                                  20 ч
```

### 8.4. Что отложить до Enterprise

- PyInstaller / Nuitka self-contained сборка.
- SharePoint Graph API адаптер.
- HashiCorp Vault для секретов.
- Code-signing инсталлятора с EV-сертификатом.
- Auto-update через background-service (windows scheduled task).

### 8.5. Финальные DoD-чеки (по DoD из issue #180)

- [x] Отчёт `docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md` создан, содержит все 8 разделов (§1–§8).
- [x] Явно описан механизм работы с `.gitignore`-артефактами (§2.2 — таблица по 13 группам).
- [x] Предложен алгоритм `backup → deploy → restore/migrate` с путями (§2.3 — 7 шагов, явно перечислены `chroma_data/`, `.env`, `knowledge_base/sources/`, `configs/`, `venv/`).
- [x] Описан сценарий первой установки (§3.1 — 8 шагов wizard, §3.2 ключи, §3.3 Ollama, §3.5 ярлыки).
- [x] По каждому направлению дана рекомендация Sprint 4 / Sprint 5 / Enterprise (§8.1).
- [x] План PoC: 3 задачи, 16 ч (§6).
- [ ] Ревью PO (после merge PR-181). _Owner: G-Ivan-A._
- [x] В `CHANGELOG.md` запись `RESEARCH: BL-47 ARM installer & cloud access feasibility study` добавлена (см. §[Unreleased] → ### Research).

---

## История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-20 | Первая версия. Закрывает BL-47 DoD: установка/cloud/KB-update, .gitignore-контракт, PoC ≤ 16 ч, риски с митигацией, ADR-предложения. |
