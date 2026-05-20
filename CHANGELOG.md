# Changelog

Все значимые изменения проекта `clarify-engine-ai` фиксируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Documentation
- **DOCS: BL-53 Streamlit `.env` / `configs/*.yaml` cache documented (issue #198).**
  По отчёту пилотного тестирования на АРМ
  ([issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) §1.6 /
  Проблема #4) Streamlit держит результат `load_dotenv()` и
  `yaml.safe_load()` в памяти процесса до его завершения — кнопка
  `Rerun` повторно `.env` / `configs/*.yaml` не перечитывает, hot-reload
  Streamlit срабатывает только на изменения в `src/`. БА из-за этого
  тратил 5–10 минут на ложную диагностику «правка `.env` не
  применилась». В рамках минимального scope BL-53 (документация +
  smoke-тест, см. бэклог
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §4.5) обновлены:
  [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md)
  §2 — рядом с командой `streamlit run src/ui/app.py` добавлен блок
  «⚠️ BL-53 — кэш `.env` и `configs/*.yaml`» с явным чек-листом
  `Ctrl+C` → `streamlit run` → `Ctrl+Shift+R`; §6 — добавлен абзац-
  префикс «прежде чем искать ошибку, проверьте кэш» со ссылкой на §2
  и новая строка в таблице «Типовые ошибки» («Правка `.env` /
  `configs/*.yaml` не применилась»).
  [`docs/user_guide/04_troubleshooting.md`](docs/user_guide/04_troubleshooting.md)
  — новый раздел «⚙️ Изменения в `.env` / `configs/*.yaml` не
  применяются» c BA-понятным объяснением, почему `Rerun` / обновление
  вкладки браузера не помогают, и тем же тремя-шаговым чек-листом.
  Покрытие:
  [`tests/test_arm_deployment_runbook.py`](tests/test_arm_deployment_runbook.py)
  расширен четырьмя кейсами BL-53 — §2 содержит предупреждение, §6
  содержит обратную ссылку, user guide содержит новый раздел,
  CHANGELOG содержит маркер BL-53. PII / маскирование: ни runbook,
  ни user guide, ни сообщения в табличках не содержат значений
  переменных окружения — только имена файлов и UI-инструкции,
  поэтому `sanitize_log_record` (BL-23) затрагивать не нужно.
  Опциональная часть DoD («🔄 Перезагрузить конфиги» в сайдбаре при
  `ui.debug_mode: true`) отложена в BL-57+ согласно
  Scope Note контракта BL-53 («часть „опциональная кнопка“ может быть
  отложена … Минимальный scope — только runbook + user guide +
  smoke-тест»); каталог
  [`src/ui/components/`](src/ui/components/) пока не содержит
  `sidebar.py`, поэтому внедрение требует отдельного PR с проектным
  решением, где разместить кнопку без регрессии BL-41 / BL-54.
  Backward compat: документация фиксирует уже существующее поведение
  Streamlit (см. https://docs.streamlit.io/library/advanced-features/caching),
  поведение приложения не меняется. Backlog v1.5 §0.6 строка BL-53
  переведена в `🟡 In Progress` со ссылкой на
  [PR #205](https://github.com/G-Ivan-A/clarify-engine-ai/pull/205).

### Code
- **CODE+DOCS: BL-57-F close active UI/runbook P1 gaps (issue #208).**
  Active `streamlit run src/ui/app.py` now matches FR-07 batch UX for
  «📊 Анализ ТЗ»: the upload pipeline renders a progress bar, live
  `Успешно: X / Ошибки: Y` counter, output-mode caption, and
  `🔁 Повторить только ошибки` control backed by the latest canonical XLSX
  result in `st.session_state` (no re-upload required). `src.pipeline.run_analysis`
  accepts an optional `progress_callback` and emits per-row `PipelineStats`
  snapshots without breaking CLI callers. Upload acceptance logging no longer
  uses reserved `LogRecord.filename`; it writes `upload_filename` instead.
  Runbook §2 now includes the BL-53 `.env` / `configs/*.yaml` restart checklist
  required by the existing contract test.

- **CODE+DOCS: BL-55 first-response UX (spinner + warmup) (issue #199).**
  Спиннер «Спрашиваем LLM…» в [`src/ui/constants.py`](src/ui/constants.py)
  теперь содержит явное предупреждение «⏱ Первый ответ на CPU может
  занять 60–90 сек.», чтобы БА на CPU-only АРМ не воспринимал cold-start
  `qwen2.5:7b` как зависание UI (см. отчёт тестировщика
  [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)
  §2 / Проблема #6). В сайдбаре добавлена опциональная кнопка
  **«🔥 Прогреть модель»**
  ([`src/ui/components/sidebar.py`](src/ui/components/sidebar.py)): она
  отправляет фоновый `requests.post(OLLAMA_BASE_URL + "/api/generate",
  json={"model": OLLAMA_MODEL, "prompt": "ok", "keep_alive": "10m"},
  timeout=120)` через `threading.Thread(daemon=True)`, поэтому Streamlit-
  поток не блокируется на 60–90 сек. Видимость кнопки строго ограничена:
  (a) `ui.debug_mode: true` в
  [`configs/ui_config.yaml`](configs/ui_config.yaml) ИЛИ (b)
  `OLLAMA_BASE_URL` указывает на `127.0.0.1` / `localhost` / `::1` —
  иначе кнопка скрыта, чтобы пилотный или облачный Ollama не получал
  warmup-флуд (BL-51 совместимость). PII / маскирование: warmup-prompt
  фиксирован строкой `"ok"`, пользовательские данные не логируются и не
  передаются. Failure handling: при connection refused / timeout кнопка
  показывает `st.error("Ollama не отвечает на прогрев")` со ссылкой на
  runbook §6, а не падает в общий error-handler. Документация
  синхронизирована: [`docs/user_guide/01_intro_modes.md`](docs/user_guide/01_intro_modes.md)
  получил блок «⏱ Первый ответ на CPU-only АРМ — 60–90 сек»,
  [`docs/user_guide/04_troubleshooting.md`](docs/user_guide/04_troubleshooting.md)
  — раздел «Долгий первый ответ (60–90 сек на CPU)»,
  [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md)
  §1 и §2 — формулировка «60–90 секунд» (en-dash) синхронизирована со
  spinner-текстом, добавлена ссылка на BL-55 и кнопку прогрева.
  Покрытие: [`tests/test_ui_constants.py`](tests/test_ui_constants.py)
  пинит «60–90» и provider-chain в `LABELS.spinner_llm`,
  [`tests/test_ui_components.py`](tests/test_ui_components.py) проверяет
  видимость кнопки (`debug_mode=true` → видна,
  `OLLAMA_BASE_URL=https://remote.example.com` + `debug_mode=false` →
  скрыта, localhost-варианты → видна), тело warmup-запроса (POST на
  `/api/generate` c фиксированным `prompt="ok"` и `keep_alive="10m"`),
  устойчивость к `ConnectionError` и success/error-ветки рендера.
  [`tests/test_arm_deployment_runbook.py`](tests/test_arm_deployment_runbook.py)
  расширен smoke-кейсом «60–90 сек + 🔥 Прогреть модель» для контроля
  синхронизации runbook ↔ spinner. Backward compat:
  `src.ui.app.render_sidebar` принимает новый опциональный `ui_config`,
  старые вызовы без него продолжают работать через `load_ui_config()`.

- **CODE: BL-54 restore file uploader in «📊 Анализ ТЗ» (issue #196).**
  Восстановлен пилотный use-case бизнес-аналитика (загрузка `.xlsx`/`.docx`
  ТЗ → выбор формата отчёта → запуск анализа → скачивание результата),
  потерянный в рефакторе BL-41 (см.
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §4.6, P0 pilot blocker). Реализация: новый компонент
  [`src/ui/components/analysis_uploader.py`](src/ui/components/analysis_uploader.py)
  с валидацией расширения (FR-01: только `.xlsx`/`.docx`) и размера
  (NFR-09: 10 МБ); рерайт `_run_analysis_mode` в
  [`src/ui/app.py`](src/ui/app.py) на dispatch между новым
  `_run_analysis_upload_mode` (по умолчанию) и legacy
  `_run_analysis_query_mode` (за флагом). `_run_analysis_upload_mode`
  рендерит uploader + radio форматов (`xlsx`/`docx`/`md` через
  `EXPORT_FORMAT_LABELS` BL-28) + кнопку «🚀 Запустить анализ»;
  `_execute_analysis_pipeline` пишет байты во временный файл,
  вызывает `src.pipeline.run_analysis(...)`, сохраняет
  `report_bytes`+`stats`+`run_id`+`duration_seconds` в
  `SESSION_ANALYSIS_LAST_RUN_KEY`; `_render_analysis_run_summary` отдаёт
  `st.download_button` с per-format `mime`/`file_name`
  (`{stem}__result_{run_id}.{ext}`). Spinner-текст
  «Идёт анализ требований… NFR-03: ≤ 15 мин на CPU-only» явно ссылается
  на бюджет латентности. Старый query-style flow сохранён за флагом
  `ui.analysis_query_mode: true` в
  [`configs/ui_config.yaml`](configs/ui_config.yaml) (default `false`)
  для совместимости с BL-43 E2E и regression-кейсом
  `tests/test_ui_error_handling.py::test_run_analysis_mode_disables_controls_while_pending`.
  PII / маскирование: имена загружаемых файлов проходят через
  `sanitize_log_record` (BL-23) перед логированием; ключ extra
  переименован в `upload_filename`, чтобы не конфликтовать со стандартным
  атрибутом `LogRecord.filename`. Label «📊 Анализ ТЗ» в
  [`src/ui/constants.py`](src/ui/constants.py) сохранён без изменений
  (user guide §2); добавлены 11 LABELS-ключей под новый flow. Покрытие:
  [`tests/test_ui_components.py`](tests/test_ui_components.py) — 11
  кейсов (валидация расширения/размера/None, render happy/error path,
  PII санитайз через BL-23),
  [`tests/test_ui_modes.py`](tests/test_ui_modes.py) — 13 кейсов
  upload+format+download (mock `src.pipeline.run_analysis` + streamlit
  stub),
  [`tests/test_arm_deployment_runbook.py`](tests/test_arm_deployment_runbook.py)
  — smoke-кейс «runbook §2.8 выполняется автоматически» (uploader →
  format radio → run button → активный download_button после успешного
  run).
  [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md)
  §2.8 — чек-лист пилотного smoke-теста (`.xlsx`/`.docx` ≤ 10 МБ → формат
  отчёта → «🚀 Запустить анализ» → «📥 Скачать отчёт ({формат})»);
  отдельным абзацем указано, что вернуться к старому query-style flow
  можно через `configs/ui_config.yaml: ui.analysis_query_mode`.
- **CODE: BL-48 ARM Installer L1 clarify-setup.cmd.** Добавлен
  Windows-first First-Run wizard
  [`scripts/install/clarify-setup.py`](scripts/install/clarify-setup.py) и
  thin CMD wrapper
  [`scripts/install/clarify-setup.cmd`](scripts/install/clarify-setup.cmd).
  Wizard закрывает шаги `[1/8]..[8/8]`: environment, runtime directories,
  venv/pip, `.env`, Ollama/model, smoke import, shortcuts и final summary.
  Тяжёлые команды проходят через testable `run_step()`, `.env` создаётся
  из `.env.example`, существующий `.env` не перезаписывается, `.env.txt`
  останавливает установку с подсказкой `ren .env.txt .env`, модель по
  умолчанию — `qwen2.5:7b`, `ollama pull` требует подтверждения. Логи
  пишутся как structured JSONL в `logs/install.jsonl`, секретные поля
  редактируются перед записью. Добавлены
  [`scripts/install/migrations/.gitkeep`](scripts/install/migrations/.gitkeep)
  и регрессионные тесты
  [`tests/test_install_first_run.py`](tests/test_install_first_run.py).
- **CODE: BL-51 auto-detect Ollama path (issue #195).** Добавлены
  `_resolve_ollama_executable()` и `_log_ollama_executable_once()` в
  [`src/llm/client.py`](src/llm/client.py). Резолюция идёт в порядке
  `shutil.which("ollama")` → `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` →
  `C:\Program Files\Ollama\ollama.exe`; при провале — детерминированная
  `RuntimeError` с готовой командой `setx PATH ...` и ссылкой на runbook
  §1.4a. `_call_ollama_rag` вызывает `_log_ollama_executable_once()`
  одной строкой через `sanitize_log_record` (BL-23), поэтому путь
  логируется ровно один раз на процесс и не ломает HTTP-вызов, если
  бинарь не найден (демон может быть доступен по сети). Покрытие:
  [`tests/test_ollama_resolution.py`](tests/test_ollama_resolution.py)
  фиксирует три обязательных сценария DoD (PATH miss + Windows fallback
  hit, `which` hit short-circuit, оба пустые → исключение с
  инструкцией) плюс два кейса на one-shot logging.
  [`tests/test_arm_deployment_runbook.py`](tests/test_arm_deployment_runbook.py)
  получил `test_runbook_documents_bl51_ollama_path_guard`, который
  проверяет наличие §1.4a с `setx PATH "%PATH%;%LOCALAPPDATA%\Programs\Ollama"`,
  предупреждение о перезапуске CMD и обновлённую строку «Connection
  refused» в §6. Linux/macOS fallback-пути оставлены как TODO в коде
  (BL-51 scope — только Windows ARM, см.
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §4.3). PII / маскирование: в логе фигурирует только путь к исполняемому
  файлу — BL-23 sanitiser обрабатывает строку без правок.
- **CODE: BL-50 `.env` startup validation (issue #194).** Добавлен
  startup-guard в новом модуле
  [`src/config_loader.py`](src/config_loader.py): `validate_env()`
  вызывается из `src/pipeline.py::main` и `src/ui/app.py::main` **до**
  любого чтения `os.environ`. Контракт BL-50 (см.
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  §4.2): (1) если рядом с проектом лежит `.env.txt`, а `.env`
  отсутствует — guard останавливает запуск с подсказкой
  `ren .env.txt .env` (silent rename запрещён, см. issue
  [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) §1.4
  Notepad-проблема); (2) если `.env` и `.env.txt` отсутствуют, но есть
  `.env.example` — guard копирует пример в `.env` и пишет
  `logger.info("Создан .env из .env.example")`; (3) после загрузки
  переменные `OLLAMA_MODEL` и `OLLAMA_BASE_URL` валидируются на
  непустоту, иначе детерминированная остановка со ссылкой на
  `docs/user_guide/04_troubleshooting.md`. Покрытие:
  [`tests/test_env_validation.py`](tests/test_env_validation.py) (пять
  сценариев — три обязательных по DoD плюс отсутствие `.env.example` и
  happy-path с уже загруженным `.env`),
  [`tests/test_arm_deployment_runbook.py`](tests/test_arm_deployment_runbook.py)
  расширен smoke-кейсом «после удаления `.env` guard создаёт его из
  `.env.example`» и проверкой ссылки на BL-50 в runbook.
  [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md)
  §1–§6 — добавлен Notepad-warning со ссылкой «BL-50 startup-guard
  скажет вам об этом автоматически», шаг `copy .env.example .env`
  помечен как опциональный, в типовых ошибках появились строки
  «Обнаружен файл `.env.txt`» и «В `.env` отсутствуют или пустые
  обязательные переменные».
  [`docs/user_guide/04_troubleshooting.md`](docs/user_guide/04_troubleshooting.md)
  — новый раздел «`.env` не найден или сохранён как `.env.txt`»
  описывает три ветки поведения guard'а для бизнес-аналитика. PII /
  маскирование: в сообщениях фигурируют только имена файлов, без
  содержимого `.env`, поэтому существующий sanitiser BL-23 пропускает
  их без изменений. Backward compat: deployment-ы с корректным `.env`
  (включая теневое окружение, заполненное через `setx` без файла) не
  меняют поведения.

### Documentation
- **DOCUMENTATION: issue #192 — Sprint 5 kickoff (BL-53, BL-55) + sub-issues.**
  Сформирован kickoff-документ Sprint 5
  [`docs/analysis/2026-05-19_sprint-5-kickoff_v1.md`](docs/analysis/2026-05-19_sprint-5-kickoff_v1.md)
  по §7 «План реализации» бэклога
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md):
  scope Sprint 5 — **BL-53** (Document Streamlit `.env`/`configs/*.yaml`
  cache behaviour + optional «Reload Config» debug button, P2) и **BL-55**
  (First-response UX — spinner text update + optional «Прогреть модель»
  warmup button, P2). Sprint 5 — два P2-issue UX-polish, закрывающие
  оставшиеся проблемы пилотного тестирования на АРМ
  ([issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)).
  В отличие от прецедента Sprint 4 (issue #187, PR #188), где kickoff
  содержал «формулировки для копирования PO», в Sprint 5 PO явно делегирует
  создание sub-issues solver-у, поэтому GitHub issues открыты сразу в этом
  же потоке: [#198 — BL-53](https://github.com/G-Ivan-A/clarify-engine-ai/issues/198)
  (Streamlit cache docs + reload button) и
  [#199 — BL-55](https://github.com/G-Ivan-A/clarify-engine-ai/issues/199)
  (spinner text + warmup button). Документ фиксирует Definition of Ready /
  Definition of Done, риски и митигацию, открытые вопросы для PO, MUST/
  SHOULD/MAY-рекомендации. Sprint 5 **не блокирует и не блокируется**
  Sprint 4 (pilot blocker BL-54) и Hot-fix Sprint (BL-52, BL-56) — обе
  задачи UX-polish, изолированы от RAG-пайплайна и могут стартовать после
  закрытия Sprint 4. Sync §0.6 v1.5 (`📝 New → 🟡 In Progress` для BL-53/
  BL-55) и Sprint-5 Execution Report — отдельными последующими PR.
- **DOCUMENTATION: issue #190 — Sprint 4 parallel BL-48 installer PoC kickoff.**
  Сформирован kickoff-документ
  [`docs/analysis/2026-05-20_sprint-4-parallel-kickoff_v1.md`](docs/analysis/2026-05-20_sprint-4-parallel-kickoff_v1.md)
  по §7 «Sprint 4 (parallel)» бэклога
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md).
  Документ фиксирует scope **BL-48 ARM Installer L1** (`clarify-setup.cmd`
  + `clarify-setup.py` First-Run wizard), зависимости BL-50..BL-52,
  Definition of Ready / Definition of Done, риски, открытые вопросы для PO
  и готовую формулировку GitHub issue. Первый implementation PR BL-48
  ограничивается Installer L1 / PoC-1 из BL-47 research §6; BL-48.1
  (KB Update UI), BL-48.2 (TZ upload tab) и BL-48.3 (ADR-011) вынесены
  в отдельные последующие issues после PO-согласования. Документ остаётся
  `Draft → Review`; кодовые изменения стартуют только после Accepted PO.
- **DOCUMENTATION: issue #187 — Sprint 4 kickoff (BL-50, BL-51, BL-54).**
  Сформирован kickoff-документ Sprint 4
  [`docs/analysis/2026-05-20_sprint-4-kickoff_v1.md`](docs/analysis/2026-05-20_sprint-4-kickoff_v1.md)
  по §7 «План реализации» бэклога
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md):
  scope Sprint 4 — **BL-50** (`.env` startup validation, P0), **BL-51**
  (auto-detect Ollama path, P1), **🔴 BL-54** (Restore file uploader в режиме
  «📊 Анализ ТЗ», P0, **pilot blocker** — регресс BL-41). Документ фиксирует
  Definition of Ready / Definition of Done, риски и митигацию, открытые
  вопросы для PO, а также содержит готовые формулировки трёх sub-issues
  (Labels / Milestone `Sprint 4 — Pilot Readiness & Automation` / Linked
  Backlog / Depends On / 🎯 Цель / 👤 User Story / 🛡 Контракт / 📋
  Рекомендации / ✅ DoD / 📦 Scope Note) — готовы к копированию в GitHub
  UI Product Owner'ом после Accepted-ревью. Документ остаётся `Draft →
  Review`, кодовые изменения и сами GitHub sub-issues стартуют только
  после Accepted PO. Sync §0.6 v1.5 (`📝 New → 🟡 In Progress` для трёх
  задач) и Sprint-4 Execution Report — отдельными последующими PR.
  Параллельный BL-48 (installer PoC) вынесен в самостоятельный поток и
  не входит в DoD Sprint 4 для сохранения фокуса на pilot blocker BL-54.
- **DOCUMENTATION: issue #182 — ARM pilot test fixes backlog branch + v1.5 sync.**
  По результатам пилотного тестирования на АРМ пользователя ([@G-Ivan-A](https://github.com/G-Ivan-A))
  сформирована отдельная ветка бэклога
  [`docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`](docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md)
  с 7 задачами BL-50..BL-56 (P0/P1/P2), покрывающими все 7 пунктов отчёта
  тестера: BL-50 (`.env` startup validation, P0), BL-51 (Auto-detect Ollama
  path на Windows, P1), BL-52 (Sync `.env.example` ↔ runbook `OLLAMA_MODEL`,
  P0), BL-53 (Streamlit `.env` cache documentation, P2), **BL-54 (Restore
  file uploader в режиме «📊 Анализ ТЗ», P0 — критический регресс BL-41
  относительно user guide и runbook)**, BL-55 (First-response UX на холодном
  Ollama, P2), BL-56 (`datetime.utcnow()` → timezone-aware Python 3.14, P2).
  Цель ветки — устранить все проблемы пилотного тестирования и достичь
  ожидаемого поведения системы согласно
  [`docs/user_guide/02_interface_elements.md`](docs/user_guide/02_interface_elements.md)
  и [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md).
  Сквозная нумерация V-10 сохранена (BL-48/BL-49 зарезервированы BL-47
  research; следующий свободный ID после v1.5 — **BL-57**). Основной реестр
  [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md)
  обновлён: §0.6 содержит BL-50..BL-56 со статусом `📝 New`, §14 ссылается
  на отдельную ветку, BL-46 и BL-47 переведены в `✅ Closed` (артефакты v1.4
  и BL-47 research note существуют), §13 History дополнен записью v1.5.
  Кодовые изменения и обновления связанной документации (`src/`, `.env.example`,
  `docs/runbooks/`, `docs/user_guide/`) стартуют **только после Accepted-ревью
  Product Owner** отдельной ветки. План релизов: hot-fix-вход (BL-50, BL-52,
  BL-54) → Sprint 4 (BL-51, BL-55) → Sprint 5 (BL-53, BL-56) с явной
  координацией с BL-48 ARM Installer (BL-50..BL-53 — runtime guards, которые
  переиспользует installer wizard).

### UI
- **UI: BL-48.6 business-friendly retrieval parameter naming & expanded
  top_k range (issue #184).** Слайдер «Сколько чанков извлекать» в сайдбаре
  Streamlit-UI заменён на бизнес-формулировку **«Макс. число источников для
  проверки»** с info-блоком, где явно описано поведение системы: для
  КАЖДОГО атомарного требования ищется до N релевантных разделов
  документации, при недостатке совпадений возвращаются только фактические
  результаты (никакого padding'а). Диапазон расширен с `1–10` до `1–20`
  (default = 5, production-safe лимит = 10): значения выше production-лимита
  подсвечиваются предупреждением о возможном росте латентности и расхода
  токенов (NFR-03). Вся пользовательская копия и лимиты вынесены в новую
  секцию `ui.retrieval` файла `configs/ui_config.yaml` (`top_k_min`,
  `top_k_max`, `top_k_default`, `top_k_production_max`, `top_k_label`,
  `top_k_help`, `top_k_tooltip`, `top_k_warning_template`); компонент
  `src/ui/components/mode_selector.py` читает их через
  `resolve_retrieval_settings()`, оркестратор `src/ui/app.py` пробрасывает
  настройки в сайдбар через `get_retrieval_settings()` — никаких
  захардкоженных значений и текстов в `src/ui/` не осталось. Резолвер
  устойчив к битому конфигу (пропущенные/некорректные ключи → фоллбек на
  модульные дефолты; `top_k_default` зажимается к `[top_k_min, top_k_max]`).
  Покрытие: `tests/test_ui_components.py` — контракт LABELS пополнен ключами
  `sidebar_topk_info_expander` / `sidebar_topk_warning_template`, добавлены
  тесты резолвера (полный конфиг, пустой конфиг, мусорные значения, clamp
  default'а, warning above/below production-max, проверка shipped tooltip и
  YAML на наличие всех BL-48.6 ключей и отсутствие слова «чанк» в label);
  `tests/test_ui_modes.py` — добавлен smoke на `app.get_retrieval_settings()`
  и проброс настроек через `app.render_sidebar(... retrieval_settings=...)`.

### Research
- **RESEARCH: BL-47 ARM installer & cloud access feasibility study (issue #180).**
  Опубликован отчёт
  [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md)
  с архитектурными рекомендациями по трём направлениям пилота с
  не-техническими пользователями (БА): (1) упрощённая установка на АРМ
  Windows 10/11 + Python 3.14 + CPU Ollama через тонкий Python-бутстрапер
  `clarify-setup.cmd` (PoC-1, ≤ 8 ч) поверх существующего runbook
  [`docs/runbooks/arm-deployment-ivan.md`](docs/runbooks/arm-deployment-ivan.md)
  (BL-45); (2) облачный доступ к ТЗ — выбран WebDAV как первый адаптер
  (покрывает Я.Диск/Nextcloud/OwnCloud), SharePoint Graph отложен (R-CLOUD-01,
  OAuth-redirect за корп. NAT); (3) обновление КБ из UI — Streamlit-вкладка
  «🔄 Обновить базу знаний» поверх существующего идемпотентного
  `knowledge_base/indexing/build_index.py` с backup→deploy→rollback (PoC-2,
  ≤ 6 ч). Зафиксирован исчерпывающий контракт `.gitignore`-артефактов по 13
  группам путей: `chroma_data/`, `logs/`, `knowledge_base/sources/`, `.env`,
  `configs/*.yaml`, `venv/` и др. — что упаковывается, что создаётся при
  First-Run, что сохраняется при Update, какая backup-стратегия. Алгоритм
  обновления `backup → deploy → restore/migrate` детализирован в 7 шагов с
  атомарным rollback при FAIL. Описан First-Run wizard (8 шагов CLI) с
  обработкой ключей API через wizard-prompt (test-mode default, без
  хранения в коде), проверкой Ollama (`qwen2.5:7b` ~4.3 GiB) и созданием
  ярлыков на рабочем столе и в меню «Пуск». PoC-план — 3 задачи ≤ 16 ч
  суммарно, укладывается в Sprint 4 без вытеснения других BL-задач.
  Риски (R-INST-01..05, R-CLOUD-01..03, R-KB-01..03, R-NFR-01, R-DOC-01)
  с конкретными митигациями. Рекомендованы три отдельных ADR: `ADR-010
  cloud-tz-access`, `ADR-011 installer-architecture`, `ADR-012
  kb-update-from-ui`. Отчёт готов как основа для BL-48 (реализация
  инсталлятора) и BL-49 (cloud integration).

### ⚠️ BREAKING CHANGES
- **BREAKING (KB schema, BL-32, issue #152):** Документация и конфиг синхронизированы с окном `chunk_size=512`, `chunk_overlap=64`, guardrails `[384, 768]`. Для индексов, созданных на старом окне `256/32` или `250/50`, требуется полная переиндексация KB перед сравнением retrieval-метрик.

### QA
- **QA: BL-43 Post-fix Smoke & E2E verification passed (issue #172).** Post-fix
  smoke- и E2E-верификация после BL-41 (UI refactor, #168) и BL-42 (Fallback
  chain sync, #170) проведена на снепшоте `d1934c8`. Pre-deploy инварианты
  соблюдены: батч-цепочка `gigachat → openrouter → ollama` и чат-цепочка
  `gigachat → ollama` сходятся с `configs/llm_config.yaml`; `strict_embedder:
  true` и decoding-lock (`temperature=0.1, top_p=0.9, seed=42,
  max_tokens=1024`) применяются на каждом провайдер-вызове; имя отчёта
  следует шаблону `<basename>_report_<runId8>.{xlsx,docx,md}`; live CLI-прогон
  (`python -m src.pipeline … sample_tz.xlsx`) выдаёт корректные
  `PIPELINE_START` / `PIPELINE_END` события с pipeline-level UUID4 run_id
  (`039c62128a964333804f11f56763a7b8`) и per-requirement 12-hex LLM run_id
  (5 уникальных); `_hash_embedding` fallback отсутствует в логах; STRICT_MODE
  детерминированно возвращает «НД» при пустом контексте; export-contract
  v1.0 (`schema_version: "1.0"`, 7 базовых полей, MVP-колонки `[Статус]
  [Комментарий] [Confidence] [RunID]`, Ref-локаторы, UUID4 run_id) проверен
  по xlsx/docx/md; `LLM_REQUEST` / `LLM_RESPONSE` несут `prompt_sha256`,
  decoding-lock и маскированные PII (`[EMAIL]`, `[PHONE]`, `[DOMAIN]`);
  CPU-only torch и env-placeholder pattern в `requirements.txt` /
  `.env.example` подтверждают ARM-готовность. Полный тест-сьют — 351
  passed / 0 failed. P0/P1-регрессий не обнаружено. Детали и подтверждающие
  ссылки на тесты:
  [`docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md`](docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md).

### Changed
- **CONFIG & DOCS: BL-42 sync LLM chains to production reality (GigaChat primary)
  (issue #170).** Production fallback chains для batch- и chat-режимов
  переписаны под реальность Пилота. `configs/llm_config.yaml` теперь содержит
  два явных контракта: `pipeline.fallback_providers: ["gigachat", "openrouter",
  "ollama"]` для ветки «📊 Анализ ТЗ» (GigaChat — RU-резидентный primary,
  NFR-04) и `ui.chat_fallback_providers: ["gigachat", "ollama"]` для ветки
  «💬 Консультация». DeepSeek помечен `# Deprecated for Pilot: deepseek
  (paid-only)` — провайдер сохранён в `providers:` и в `_call_deepseek`
  для быстрого возврата по согласованию бюджета, но исключён из обеих
  активных цепочек. Код P0-фикс: вынес hardcoded `RAG_FALLBACK_CHAIN` из
  `src/llm/client.py:82` в config — `_chat_fallback_chain()` резолвит чейн
  в порядке `ui.chat_fallback_providers` → `pipeline.fallback_providers` →
  top-level `fallback_providers` → `DEFAULT_CHAT_FALLBACK_CHAIN` (Pre-deploy
  Invariant #5: zero hardcoded chains in `src/`). Алиас `RAG_FALLBACK_CHAIN`
  сохранён для backward compatibility с импортирующими тестами/скриптами.
  SSoT синхронизация: `CONCEPT.md` v2.6 (§2.3 deprecation note, §5 MVP/Pilot
  примечание, §6.2 п.9, §6.3.1, §6.3.2, §6.4 — две таблицы batch/chat +
  сноска), ADR-001 v1.6 (`Decision §4`, `Triggers for Revision`),
  ADR-004 (UI Operation Modes) v1.2 (`Configuration` block + резолвер),
  `.env.example` и `README.md` (контрактные цепочки + DeepSeek-deprecation
  блок). Zero logic change в `_ordered_providers` для legacy конфигов
  (top-level `fallback_providers` всё ещё работает как fallback).

- **BL-41 — Streamlit UI refactor & UX polish (issue #168).** `src/ui/app.py`
  decomposed into single-responsibility components under
  `src/ui/components/` (`mode_selector.py`, `upload_zone.py`,
  `chat_interface.py`, `results_viewer.py`). All Russian user-facing copy
  centralised in `src/ui/constants.LABELS` so translations or proof-reads
  touch one dict. UX touch-ups: `st.toast` notifications on history-clear
  and successful search, tooltip legend over the status column
  (Да / Нет / Частично / НД / Ошибка) via `STATUS_TOOLTIPS`, ℹ️ info icons
  on export-format radio and debug error remediation. No changes to
  prompts, configs, `LLMClient`, `pipeline.py`, or the `src.ui.app` public
  surface (`MODE_LABELS`, `SESSION_*`, `UI_GENERATION_ERROR_TEXT`, etc.
  remain importable as before). New `tests/test_ui_components.py` pins the
  `LABELS` contract and component callables; full suite at 347 tests.

### Documentation
- **DOCUMENTATION: BL-46 backlog branch update to v1.4 (issue #178).** Added
  `docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md`, archived
  completed Sprint 3 tasks BL-34..BL-45 with artifact links, updated the active
  backlog register, and added BL-47 research for ARM installer, cloud TZ
  access, and documentation update flow.

- **DOCUMENTATION: BL-45 ARM deployment runbook for Windows CMD + CPU Ollama
  (issue #176).** Added `docs/runbooks/arm-deployment-ivan.md` with the
  Ivan Gulienko ARM deployment path: clean Windows CMD install, restart flow,
  CPU-only Ollama setup for `qwen2.5:7b`, UTF-8/cp1251 guardrails, Streamlit
  launch via `streamlit run src/ui/app.py`, UI error diagnostics through
  `debug_error_details: true` and "📥 Скачать логи", plus update and
  reindexing steps. Added a documentation contract test to keep the runbook
  aligned with the BL-45 operational scenarios.

- **DOCUMENTATION: BL-40 ADR sync & numbering convention (issue #166).** Pure
  documentation synchronization across `docs/ADR/001..009` with `CONCEPT.md` v2.5
  and the BL-34 architecture-consistency audit. No source/config/contract
  changes. Reaffirmed every Accepted ADR (`001, 002, 004A, 004B, 005, 006,
  007A, 008, 009`) and explicitly excluded Draft ADRs (`003 Multi-Agent`,
  `007B Canonical Cache / Pivot`) from the Pilot architecture per CONCEPT.md
  §2.3 invariants. Promoted the «ADR-NNNA / ADR-NNNB» disambiguation notation
  in [`docs/ADR/README.md`](docs/ADR/README.md) (orthogonal pairs `004A/004B`,
  `007A/007B`, status glossary, BL-40 alignment note). Added §History v1.1
  entries to all reaffirmed ADRs. Highlights:
  ADR-001 — references BL-22 (`docs/standards/llm-behavior.md`) and BL-34
  §CHK-01;
  ADR-002 — explicit **Channel separation** vs. ADR-008 + inline
  `EXPORT_SCHEMA_VERSION = "1.0"`;
  ADR-003 — top-level **🚫 Non-Scope for Pilot** block forbidding `agent_id`,
  `asyncio.Queue`, `parent_run_id`, `agent_trace`, `AGENT_SHARED_SECRET` in
  `src/`;
  ADR-004A/004B — formal Numbering Note blockquotes;
  ADR-005 — explicit `src/llm/masking.py::sanitize_log_record` boundary
  (BL-23 alias);
  ADR-006 — new §Security Contract (`file://` exclusion, path-traversal
  rejection);
  ADR-007B — Numbering Note paired with 007A + §Triggers for Revision tied
  to **Gate 0 — Stability ≥ 5 sessions** (CONCEPT.md §8.1.1);
  ADR-008 — Channel separation vs. ADR-002 + `mask_text()` allow-list;
  ADR-009 — explicit **Mode Contract** table (`use_parent_context=True` only
  in Консультация), pinned `parent_context_max_chars: 6000` default.
- **DOCS: CONCEPT.md → v2.5 SSoT sync (BL-39, issue #164).** Pure documentation
  synchronization (no source/config/contract changes). Bumped header to
  v2.5 / 2026-05-19; expanded §1.1 dual-scope goal (batch + consultation +
  multi-format export); added two-mode workflow table to §2.1
  («📊 Анализ ТЗ» stateless / «💬 Консультация» stateful, history ≤ 6); new
  §2.3 Pre-deploy Invariants block (six invariants from BL-34: strict_embedder,
  zero source modification, ADR-003/007 read-only boundary, PoC location,
  decoding-lock centralization, masking-rules single source); rewrote FR-06
  (pipeline vs UI export channels, `EXPORT_SCHEMA_VERSION = "1.0"`, 7 fields),
  FR-07 (sidebar-radio modes, two-layer history limit, graceful error UX),
  FR-08 (dual `run_id` — pipeline UUID4 + LLM `uuid4.hex[:12]`, full audit
  event set incl. `PIPELINE_START/END`, `LLM_REQUEST/RESPONSE`,
  `ui_generation_failed`); refreshed NFR-03/06/08 and added new NFR-10
  (prompt drift control via SHA-256 + `decoding_lock applied`); expanded §6.2
  component registry from 10 to 15 (added `ParentAwareRetriever`,
  `IterativeRetriever`, `QueryExpansionRetriever`, `PromptLoader`,
  `ExportRouter`, `ErrorHandler`); split §6.3 into §6.3.1 «Анализ ТЗ»
  (HARD-LOCK one-shot) and §6.3.2 «Консультация» (opt-in QueryExpansion /
  Iterative / ParentAware); §6.6 now lists concrete config values (chunk_size
  512/64, rrf_k=60, `strict_rag_mode`, `parent_context_max_chars`); added
  risks R-10 (prompt drift), R-11 (Streamlit state corruption), R-12
  (cache/Pivot misuse); added Gate 0 «Stability ≥ 5 sessions» and pre-deploy
  invariant check to §8.1.1; added open questions 8 (cache validation trigger,
  BL-33) and 9 (Timeline Production UI Gateway, ADR-003 Concept §8.1.3) to
  §10; expanded §11 to reference ADR-004 (prompt + UI), ADR-005, ADR-006,
  ADR-007 (canonical-cache + error-handling), ADR-008, ADR-009 and
  `docs/audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md`.

### Fixed
- **PATCH: BL-52 / BL-56 hot-fix release 200526 (issue #186).**
  Aligned `.env.example` `OLLAMA_MODEL` with the ARM runbook's
  `ollama pull qwen2.5:7b` command so a copied default `.env` uses the model
  actually installed during pilot setup. Replaced the KB indexer JSON-log
  timestamp source with timezone-aware UTC (`datetime.now(timezone.utc)`) to
  avoid Python 3.14 `datetime.utcnow()` deprecation warnings. Regression
  coverage: `tests/test_env_example_runbook_sync.py` and
  `tests/test_build_index.py`.
- **PATCH: BL-34-F drift cleanup & audit recommendations (issue #162).**
  Clarified ADR numbering/export-channel docs, added the CONCEPT pre-deploy
  invariant for Concept/Pivot ADRs, and emitted structured
  `PIPELINE_START` / `PIPELINE_END` audit events.
- **PATCH: Code Review triage hardening (BL-26, issue #142).**
  Added the code-review triage matrix, made `strict_embedder: true` explicit
  while allowing an audited hash fallback only for `strict_embedder: false`,
  keyed the Streamlit retriever cache by the md5 of `embedding_config.yaml`,
  kept DOCX locators page-free with table/list traceability, and expanded
  masking regex coverage for 8-prefix RU phones and multi-level internal
  domains.
- **PATCH: configurable LLM provider HTTP timeouts (issue #139).**
  `LLMClient` resolves per-provider `timeout` / `timeout_seconds` values before
  falling back to `OLLAMA_TIMEOUT`, `PROVIDER_TIMEOUT`,
  `LLM_PROVIDER_TIMEOUT`, then 30 seconds. DeepSeek, GigaChat, OpenRouter, and
  Ollama HTTP calls now use the resolved timeout; regression tests cover
  config/env/default precedence.
- **PATCH: Windows UTF-8 config compatibility (BL-26, issue #125).**
  YAML/Markdown/Python text attributes are pinned to UTF-8/LF and regression
  tests verify config loaders read YAML with explicit `encoding="utf-8"` so
  Russian Windows `cp1251` locales do not trigger `UnicodeDecodeError`.
- **PATCH: Parent-aware retrieval wiring (BL-10, issue #137).**
  KB UI again exposes the `search_kb` retrieval path, composes multi-hop and
  query expansion with `ParentAwareRetriever`, enables parent context only for
  «Консультация», and aligns `configs/embedding_config.yaml.required_metadata`
  with `parent_id` / `section_id` / `parent_text`.

### Added
- **BL-35 (issue #158):** Added the isolated Track 2 cache-validation backlog
  `docs/backlog/2026-05-19_track2-cache-validation_v2.md` with `🟡 DEFERRED`
  status, activation gates 0→3, `T2-BL-*` task sequencing, isolation rules,
  and links to ADR-007, CONCEPT NFR-07, and the main backlog v1.3.
- **BL-31 (issue #153):** Added isolated offline DOCX structure enrichment.
  `scripts/tools/enrich_docx_structure.py` parses `.docx` files and writes
  atomized JSON with deterministic span slicing, SHA-256 `exact_text`
  validation metadata, `parent_id`, export-compatible `Ref`, confidence-based
  manual-review flags, local Ollama support, and heuristic fallback.
- **BL-30 (issue #151):** Added an isolated canonical query cache PoC in
  `scripts/poc/semantic_cache_poc.py`, covering Golden Set replay loading,
  deterministic threshold sweeps (`0.90`, `0.95`, `0.97`), cache hit/latency/
  token/accuracy metrics, optional `BAAI/bge-m3` embeddings, regression tests,
  and draft ADR verdict in `docs/ADR/007-canonical-cache-draft.md`.
- **BL-29 (issue #150):** KB UI analysis export now exposes `.xlsx`, `.docx`,
  and `.md` format selectors with session-state persistence, keeps the MVP
  mode locked to `create_new`, and generates downloads through `ExportRouter`
  with a friendly Streamlit error when export generation fails.
- **BL-27 (issue #146):** Accepted export-markup v1.0 as the shared
  `.xlsx` / `.docx` / `.md` result contract, added Pydantic `ExportRow`
  validation for the 7 required fields plus `Ref` / schema metadata, and
  documented ADR-002 extension rules for `schema_version: "1.1"+`.
- **BL-28 (issue #148):** Multi-format export through `ExportRouter`.
  Added `.docx` and `.md` report adapters, report filename templating via
  `configs/export_config.yaml`, pipeline routing by output suffix, and
  multi-sheet `.xlsx` export that maps results by parser locator without
  modifying the source file.
- **BL-14 (issue #136):** Offline Dependency Extraction for KB chunks.
  `scripts/tools/extract_dependencies.py` enriches ChromaDB metadata with
  `related_sections`, `prerequisites`, `see_also`, and
  `dependencies_extracted` using deterministic regex extraction by default and
  optional local Ollama enrichment via `--use-ollama`. `build_index.py` exposes
  `--extract-dependencies` / `--dependency-use-ollama`, and the KB UI decodes
  the metadata into prompt context plus visible «См. также» / prerequisites in
  source chunk expanders. Tests: `tests/test_extract_dependencies.py`,
  `tests/test_metadata_extraction.py`, `tests/test_citation_links.py`.
- **BL-18 (issue #132):** `.docx` ingest is routed through
  `load_requirements_by_extension()` alongside `.xlsx`; `DocxParser` now emits
  non-empty `locator` metadata for paragraphs and table cells, and Excel ingest
  supports multi-sheet workbooks with `sheet_name` in each locator.
- **MINOR: Multi-hop Retrieval for Consultation mode (BL-11, issue #123).**
  `configs/llm_config.yaml` now exposes `rag.multi_hop_enabled: false`,
  `rag.max_hops: 2`, and `rag.min_confidence_to_stop: 0.8`.
  `src/rag/retriever.py::IterativeRetriever` wraps the existing hybrid
  retriever with bounded follow-up retrieval, cross-hop deduplication by
  `(source, chunk_idx)`, and graceful fallback to the accumulated context when
  reflection times out, fails, or returns invalid JSON. `src/ui/app.py`
  hard-locks this path to «Консультация»; «Анализ ТЗ» ignores the flag and
  remains one-shot retrieval. Reflection uses
  `prompts/system_rag_reflection_v1.0.md` with strict JSON output
  `{sufficient, follow_up, confidence}`. Tests:
  `tests/test_iterative_retriever.py`, `tests/test_ui_modes.py`,
  `tests/test_prompt_loader.py`.
- **BL-12 (issue #124):** Query Expansion для режима «Консультация»:
  `QueryExpansionRetriever` генерирует 3–4 семантические переформулировки
  через `prompts/system_rag_query_expansion_v1.md`, выполняет retrieval по
  вариантам запроса и объединяет хиты через RRF с дедупликацией. Флаги
  `rag.query_expansion_enabled: false` и `rag.expansion_count: 3` добавлены
  в `configs/embedding_config.yaml`; graceful fallback возвращает результаты
  исходного запроса при сбое LLM или невалидном JSON.
- **BL-25 (issue #122):** конфигурируемый блок `providers.ollama` в
  `configs/llm_config.yaml` с `${OLLAMA_*:default}` placeholders для
  `model`, `base_url`, `timeout_seconds` и локальными `options`
  (`num_ctx`, `num_thread`, `keep_alive`, `temperature`). `LLMClient`
  применяет YAML/env значения и централизованный `decoding:` к Ollama
  RAG-вызовам; дефолтный timeout повышен до 180 секунд для CPU-only АРМ.
  Документация обновлена в `README.md`, `.env.example` и
  `docs/standards/llm-behavior.md`; регресс-тест —
  `tests/test_llm_client.py::test_ollama_config_loading`.
- **PATCH: dependency hardening (BL-24a, issue #120).** Добавлен
  `torchvision>=0.18.0` в `requirements.txt`, чтобы optional vision-backends
  из `transformers` не засоряли Streamlit-логи `ModuleNotFoundError` при
  чистой установке зависимостей.

## [0.2.0] - 2026-05-18

### ⚠️ BREAKING CHANGES
- **BL-06** (#92): Переход на `chunk_size=512`, `chunk_overlap=64` и section-aware splitting. Требуется полная переиндексация базы знаний: удалить старую ChromaDB-коллекцию и выполнить `python knowledge_base/indexing/build_index.py`.

### Added
- **MINOR: Parent Document Retrieval L2 (BL-10, issue #118).**
  Индексатор сохраняет `parent_id` / `section_id` / `parent_text` для L1-чанков,
  `HybridRetriever` и `HybridChromaRetriever` поддерживают opt-in
  `use_parent_context`, а режим «Консультация» в KB UI передаёт в LLM
  сгруппированный родительский контекст с лимитом `parent_context_max_chars`.
  ADR — [`docs/ADR/009-parent-document-retrieval.md`](docs/ADR/009-parent-document-retrieval.md);
  тесты — `tests/test_retriever.py`, `tests/test_hybrid_chroma_retriever.py`,
  `tests/test_build_index.py`, `tests/test_ui_modes.py`.
- **MINOR: audit trail with run_id tracing & BL-04 compliance (BL-23, issue #103).**
  `src/llm/client.py` creates a 12-hex per-request `run_id` for
  `classify_requirement()` and `generate_rag_response()`, preserves it through
  provider fallback via provider config, and emits masked structured
  `LLM_REQUEST` / `LLM_RESPONSE` records with provider, decoding params,
  prompt version/hash, response status, and latency. Logger failures are
  best-effort and do not interrupt the main LLM request. ADR:
  [`docs/ADR/005-audit-trail.md`](docs/ADR/005-audit-trail.md); tests:
  `tests/test_audit_trail.py`.
- **MINOR: graceful error handling & retry UX (BL-13, issue #106).**
  KB-тестовый UI (`src/ui/app.py`) теперь обрабатывает сбои ретривера и LLM
  без сырых traceback в интерфейсе: запрос сохраняется в
  `st.session_state["last_query"]`, кнопка «Повторить» переиспользует это
  значение, во время queued generation поля ввода блокируются, а ошибка
  рендерится отдельным `st.error("Не удалось получить ответ.")` без
  фейкового RAG-ответа. UI-логи `ui_prompt_built` /
  `ui_generation_failed` несут `run_id`, `error_type`, `provider` и
  изолированы `try/except`, чтобы сбой логирования не ронял Streamlit.
  ADR — [`docs/ADR/007-error-handling.md`](docs/ADR/007-error-handling.md);
  тесты — `tests/test_ui_error_handling.py`.
- **MINOR: evaluation script for RAG metrics (BL-05, issue #105).**
  `scripts/evaluate/evaluate_rag.py` reads the Golden Set from
  `data/golden_set_v1.jsonl`, loads retrieval settings from
  `configs/embedding_config.yaml`, computes Hit Rate@5 and MRR, and writes
  `outputs/eval_report_v1.json`. The runner supports `--config` and emits a
  clear error when the configured Chroma directory is missing. Metric formulas
  are documented in `docs/standards/evaluation-metrics.md`.
- **MINOR: clickable citation links with page anchors (BL-09.1, issue #104).**
  `configs/ui_config.yaml` задаёт `citations.base_url` и `source_dir`,
  `src/ui/app.py` строит Markdown-ссылки вида
  `http://localhost:8000/docs/file.pdf#page=N`, а
  `src/api/static_serve.py` добавляет безопасный FastAPI endpoint
  `GET /docs/{filename}` с валидацией basename/path traversal и
  `application/pdf`. ADR — [`docs/ADR/006-citation-links.md`](docs/ADR/006-citation-links.md);
  тесты — `tests/test_citation_links.py`, `tests/test_static_serve.py`.
- **MINOR: metadata inheritance & coverage improvement (BL-02 hardening, issue #109).**
  `knowledge_base/indexing/build_index.py` добавляет per-document
  `SectionPropagationState`: чанки без локального заголовка наследуют
  ближайший `section_title` / `section_number`, получают audit-флаг
  `section_inherited`, а после длинного разрыва по страницам контекст
  сбрасывается для защиты от ghost inheritance. До первого заголовка
  используется fallback по имени документа (`section_fallback=source_filename`),
  чтобы UI-цитаты имели человекочитаемую подпись.
- **BL-15 (issue #107):** контекстно-зависимый экспорт из KB UI:
  `src/utils/export.py` генерирует `.xlsx` и `.md` в памяти через
  `io.BytesIO`, `configs/export_config.yaml` задаёт строгий allow-list
  Excel-колонок (`requirement_id`, `requirement_text`, `classification`,
  `reasoning`, `citations`), а `src/ui/app.py` показывает кнопки
  «📥 Скачать отчет (.xlsx)» для режима «Анализ ТЗ» и
  «📥 Сохранить диалог (.md)» для режима «Консультация». Экспорт применяет
  `mask_text()` ко всем строковым значениям и не включает служебные поля
  вроде `raw` / `provider`. ADR — [`docs/ADR/008-data-export.md`](docs/ADR/008-data-export.md);
  тесты — `tests/test_context_export.py`.
- `docs/standards/llm-behavior.md` v1.0 — стандарт параметров декодирования LLM (BL-22, issue #101): канонический блок `decoding:` (`temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024`), таблица рекомендуемых значений по провайдерам/режимам (DeepSeek, GigaChat, OpenRouter, Ollama), допустимый коридор изменений в Пилоте, обязательное аудит-логирование `decoding_lock applied`. Зарегистрирован в `docs/standards/README.md`.
- **Prompt Library `prompts/` + `src/llm/prompt_loader.py` (BL-08, issue #94).**
  Все системные и few-shot-промпты вынесены из `src/llm/client.py` и
  `src/ui/app.py` в версионируемые файлы по конвенции
  `<name>_v<MAJOR>.<MINOR>.<ext>`: `prompts/system_classifier_v1.0.md`,
  `prompts/system_rag_v1.0.md`, `prompts/few_shot_examples_v1.0.json`.
  Loader (`load_prompt`, `load_few_shot_examples`,
  `load_prompt_from_path`) вычисляет SHA-256 содержимого и пишет
  `INFO`-запись в JSON-лог с `prompt_name`, `prompt_version`,
  `prompt_sha256`, `run_id` — audit-трасса BL-23. `LLMClient`
  использует `load_prompt_from_path` через существующий
  `DEFAULT_PROMPT_PATH`, публичные сигнатуры не меняются; `src/ui/app.py`
  загружает `system_rag_v1.0.md` через `@st.cache_resource`. Архитектура
  и DoD — [`docs/ADR/004-prompt-management.md`](docs/ADR/004-prompt-management.md);
  изменения промптов — `prompts/prompt_changelog.md`; 16 unit-кейсов в
  `tests/test_prompt_loader.py`.
- **BL-07 (issue #93):** два режима работы KB-тестового UI (`src/ui/app.py`) — **«📊 Анализ ТЗ»** (полностью stateless, токен-cost совпадает с pre-BL-07 baseline) и **«💬 Консультация по документации»** (stateful чат, история ≤ `ui.max_history_messages` сообщений, по умолчанию 6). Переключатель режимов в `st.sidebar.radio`, кнопка «🧹 Очистить историю», автоматический сброс истории при смене режима (`_ensure_mode_state`), инлайн истории в `<history>`-блок промпта без изменения сигнатуры `LLMClient.generate_rag_response()`, JSON-лог `ui_prompt_built mode=… history_messages=… approx_tokens=…` на каждый вызов. Конфиг — `configs/llm_config.yaml` (`ui.max_history_messages`). ADR — [`docs/ADR/004-ui-operation-modes.md`](docs/ADR/004-ui-operation-modes.md); обновлён `docs/CONCEPT.md` §6.2 (компонент UI) и §6.8 (режимы работы UI). Регресс-тесты — `tests/test_ui_modes.py`.
- `src/rag/chunker.py::split_sections` и флаг `section_aware_chunking` в `configs/embedding_config.yaml` — section-aware splitter режет текст по заголовкам (Markdown `#`, нумерованные разделы `\d+(\.\d+)+`, локализованные `Раздел N` / `Section N`, CAPS-блоки PDF) до применения token-окна; заголовок остаётся в первом чанке секции (BL-06, issue #92).
- `tests/test_chunker.py` — unit-тесты L1-контракта: дефолты 512/64, guardrails 384–768, корректность section-aware разбиения и пропагация флагов из конфига (BL-06, issue #92).
- `src/rag/retriever.py` — `HybridChromaRetriever.search()` теперь пишет INFO-лог `bm25_hits=… dense_hits=… fused=… rrf_k=60 top_k=…` на каждый запрос. Лог подтверждает, что в production-пути UI отрабатывает именно фьюжн BM25 + Dense + RRF, а не только векторный поиск (BL-01 DoD, issue #91).
- `tests/test_hybrid_chroma_retriever.py::test_hybrid_chroma_search_logs_fusion_breakdown` — регресс-тест, проверяющий формат строки фьюжн-лога (issue #91).
- `src/ui/app.py` — Streamlit UI для ручного тестирования RAG-пайплайна по базе знаний: поле запроса, кнопка «Search KB», вывод ответа LLM в Markdown, секция «Source Chunks» с именем файла, обрезанным текстом и similarity-скором; сайдбар с тоглом Debug Mode и выбором провайдера (DeepSeek / GigaChat). ChromaDB читается из `knowledge_base/vector_store/` (коллекция `clarify_engine_kb`), эмбеддер `BAAI/bge-m3`, конфиг провайдеров — `configs/llm_config.yaml`, секреты — `.env`. Запуск: `streamlit run src/ui/app.py` (issue #70).
- `python-dotenv` в `requirements.txt` — необходим UI для чтения `.env`.
- `.env.example` — шаблон переменных окружения с плейсхолдерами `DEEPSEEK_API_KEY`, `GIGACHAT_API_KEY` и флагами `USE_TEST_DATA_MODE`, `STRICT_EMBEDDER` (issue #59; `YANDEXGPT_API_KEY` исключён в issue #64).
- `scripts/evaluate/evaluate_quality.py` — CLI для замера качества классификации (Macro-F1 и per-class P/R/F1) против `test_data/gold_standard.json`, поддерживает Excel и JSON-предсказания, JSON-логирование и опциональный детальный отчёт (issue #47, NFR-01).
- `tests/test_quality.py` — smoke-тесты метрик, парсеров входных файлов и CLI evaluate_quality.
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md` — аудит согласованности репозитория, полноты документации и тестируемости требований (issue #21).
- `docs/analysis/2026-05-15_analysis_repo-state-and-mvp-recommendations_v1.md` — анализ состояния репозитория, оценка готовности MVP, профиль нагрузки и рекомендации по доработке кода, архитектуры и документации (issue #35).
- `src/rag/chunker.py` — токенайзер-чанкер на основе `BAAI/bge-m3`, параметры 200–300 токенов с overlap 50 (issue #45 MUST 2).
- `scripts/evaluate/evaluate_quality.py` — расчёт точности/полноты/F1 по `[Статус]` против `test_data/gold_standard.json` (issue #45 SHOULD 1).
- `scripts/evaluate/benchmark_pipeline.py` — бенчмарк пропускной способности пайплайна на N синтетических требований в режимах `stub` / `production` (issue #45 SHOULD 1).
- `CONTRIBUTING.md` — Definition of Done, матрица команд, правила ветвления (issue #45 MAY 1).
- `SECURITY.md` — политика обработки утечек, SLA, контакты Product Owner (issue #45 MAY 1).
- `tests/test_excel_exporter.py`, `tests/test_app_retry.py`, `tests/test_evaluate_quality.py` — регресс-тесты на FR-06 (4-колоночный экспорт), retry-by-RunID и контракт F1-оценщика.
- **BL-01** (#91): Hybrid retrieval (BM25 + `BAAI/bge-m3` dense) с RRF-фьюзией (`k=60`) и INFO-логированием `bm25_hits`, `dense_hits`, `fused`, `rrf_k`, `top_k`.
- **BL-02** (#109): Metadata inheritance (Section Propagation) для чанков базы знаний: наследование `section_title` / `section_number`, audit-флаг `section_inherited`, fallback по имени документа и улучшение coverage.
- **BL-04** (#91): Strict embedder config и централизованное логирование параметров retrieval-пути.
- **BL-06** (#92): Chunker L1: section-aware splitting, improved heading detection, guardrails 384–768 токенов и тесты L1-контракта.
- **BL-07** (#93): Два режима UI (`Анализ ТЗ` / `Консультация по документации`) с историей диалога, очисткой истории и логированием `ui_prompt_built`.
- **BL-08** (#94): Prompt Library (`prompts/`) с версионированием, SHA-256 аудитом, fallback-цепочкой и `src/llm/prompt_loader.py`.
- **BL-15** (#107): Контекстно-зависимый экспорт из KB UI: `.xlsx` для режима анализа ТЗ и `.md` для консультаций, с маскированием строковых данных.
- **BL-22** (#101): Decoding Config: стандарт `docs/standards/llm-behavior.md`, централизованные параметры `temperature`, `top_p`, `seed`, `max_tokens` и аудит `decoding_lock applied`.
- **BL-23** (#103): Расширенный audit trail с `run_id`, latency, provider fallback, prompt version/hash, статусами ответов и masked structured `LLM_REQUEST` / `LLM_RESPONSE`.
- **BL-13** (#106): Graceful error handling and retry UX in KB UI: сохранение последнего запроса, кнопка повторной попытки, блокировка ввода во время queued generation и безопасное отображение ошибок.
- **BL-05** (#105): Evaluation script for RAG metrics: Hit Rate@5, MRR и JSON-отчёт `outputs/eval_report_v1.json`.
- **BL-09.1** (#104): Clickable citation links with page anchors and safe FastAPI static endpoint `GET /docs/{filename}`.
- `src/ui/app.py` — Streamlit UI для ручного тестирования RAG-пайплайна по базе знаний: поле запроса, выбор провайдера, Debug Mode, ответ LLM и секция Source Chunks.
- `python-dotenv` в `requirements.txt` и `.env.example` с плейсхолдерами `DEEPSEEK_API_KEY`, `GIGACHAT_API_KEY`, `USE_TEST_DATA_MODE`, `STRICT_EMBEDDER`.
- `scripts/evaluate/evaluate_quality.py` и `tests/test_quality.py` — CLI и smoke-тесты для метрик качества классификации.
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md` и `docs/analysis/2026-05-15_analysis_repo-state-and-mvp-recommendations_v1.md` — аудит состояния репозитория и рекомендации к MVP.
- `scripts/evaluate/benchmark_pipeline.py` — бенчмарк пропускной способности пайплайна на синтетических требованиях.
- `CONTRIBUTING.md` и `SECURITY.md` — Definition of Done, матрица команд, правила ветвления и политика обработки утечек.
- `tests/test_excel_exporter.py`, `tests/test_app_retry.py`, `tests/test_evaluate_quality.py` — регресс-тесты на FR-06, retry-by-RunID и контракт F1-оценщика.

### Changed
- `configs/embedding_config.yaml` и `docs/standards/embedding-model.md` обновлены под параметры `chunk_size=512`, `chunk_overlap=64`, `metadata_coverage_min=0.65`, section propagation и обязательную схему метаданных.
- `src/rag/chunker.py` переведён на L1-параметры 512/64, guardrails 384–768 и section-aware splitter, включаемый через YAML.
- `src/ui/app.py` показывает кликабельные citation labels с `section_title`, `section_number` или fallback-подписью раздела.
- `docs/ADR/003-multi-agent-orchestration-draft.md` обновлён до Concept (Review) v1.1 с контрактами очередей, event envelope, отказоустойчивостью, security/compliance и observability.
- Проект переименован с `mango-tz-ai-analyzer` на `clarify-engine-ai`; брендовые упоминания заменены на нейтральные термины.
- `docs/CONCEPT.md` обновлён до версии 2.0 с актуальными FR/NFR, рисками, Exit Criteria, глоссарием и реестром связанных документов.
- `requirements.txt` актуализирован для retrieval-зависимостей (`rank_bm25`, `chromadb`, `sentence-transformers`) и установки CPU-версии `torch`.
- `src/llm/client.py` использует экспоненциальный backoff `[5с, 15с, 45с]` для retriable-ошибок при последовательных LLM-вызовах.
- `src/pipeline.py` помечает полный отказ строки как `[Статус: Ошибка]` и продолжает обработку остальных требований.
- `src/exporters/excel_exporter.py` ограничивает экспорт ровно четырьмя MVP-колонками `[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]`.
- `src/app.py` вызывает реальный `run_analysis`, отображает прогресс и счётчики, поддерживает повтор только ошибочных строк и вкладку справки для БА.
- `src/rag/retriever.py` удалил hash-embedding fallback в Strict-Embedder Mode и теперь падает с явной ошибкой при недоступной модели.
- `knowledge_base/indexing/build_index.py` добавил SHA-256 хеши, синхронизацию с `source_registry.csv` и чанкинг через `src/rag/chunker.py`.
- `configs/masking_rules.yaml` оставляет только согласованные паттерны Email/Phone/IP/Domain; маски ФИО/юрлиц/ИП отложены.

### Documentation
- Созданы и обновлены ADR: `docs/ADR/004-prompt-management.md`, `docs/ADR/004-ui-operation-modes.md`, `docs/ADR/005-audit-trail.md`, `docs/ADR/006-citation-links.md`, `docs/ADR/007-error-handling.md`, `docs/ADR/008-data-export.md`.
- Обновлены `docs/CONCEPT.md`, `docs/standards/embedding-model.md`, `docs/standards/llm-behavior.md`, `docs/standards/evaluation-metrics.md`, `docs/standards/README.md`.
- Добавлены sprint/audit материалы в `docs/audit/` и `docs/analysis/`, включая отчёты по состоянию репозитория, MVP-рекомендациям и RAG-оптимизации.

### Removed
- `knowledge_base/indexing/chunk_config.yaml` удалён; параметры чанкинга читаются только из `configs/embedding_config.yaml`.
- Провайдеры Qwen (DashScope) и YandexGPT удалены из fallback-цепочки, конфигов, `.env.example` и документации; актуальная цепочка — DeepSeek и GigaChat.

## [0.1.0-mvp] - 2026-05-12

### Added
- Концепция MVP: [`docs/CONCEPT.md`](docs/CONCEPT.md) v1.0 (разделы 1–8).
- ADR-001: RAG с гибридным поиском (BM25 + Dense + RRF), `BAAI/bge-m3`, ChromaDB.
- Стандарты: roles, naming-convention, embedding-model, шаблоны для analysis / decision.
- Аудит маскирования данных: [`docs/audit/data-masking_v1.md`](docs/audit/data-masking_v1.md).
- Streamlit UI (`src/app.py`) с вкладками «Анализ ТЗ» и «Концепция и БЗ».
- Excel-парсер (`src/parsers/excel_parser.py`), гибридный retriever (`src/rag/retriever.py`), LLM-клиент с fallback на 4 провайдера (`src/llm/client.py`), Excel-экспортёр (`src/exporters/excel_exporter.py`), end-to-end пайплайн (`src/pipeline.py`).
- Конфигурации: `configs/llm_config.yaml`, `configs/embedding_config.yaml`, `configs/classification_rules.json`, `configs/masking_rules.yaml`.
- Промпты: `prompts/system_classifier_v1.0.md`, `few_shot_examples.json`, `prompt_changelog.md`.
- Тестовые данные: `test_data/sample_tz.xlsx`, `test_data/gold_standard.json`.
- Unit-тесты (14): `tests/test_excel_parser.py`, `tests/test_llm_client.py`, `tests/test_pipeline.py`, `tests/test_retriever.py`.
