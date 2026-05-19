# 🔧 Бэклог исправлений по результатам тестирования на АРМ (Pilot Readiness) — v1.0

> Новая ветка бэклога, сформированная по результатам первого функционального
> тестирования установки `clarify-engine-ai` на АРМ Бизнес-Аналитика
> (`Windows 10/11`, `Python 3.14`, `CPU-only`, `32 GiB RAM`) тестировщиком
> [Иваном Гулиенко](https://github.com/G-Ivan-A) 20 мая 2026 г. (см.
> [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)).
>
> Документ **не модифицирует код**. Кодовые изменения и обновления связанной
> документации стартуют только после статуса `Accepted` и утверждения Product
> Owner. Каждая BL-задача из этого файла — самостоятельная единица работы,
> которая после `Accepted` переносится в основной реестр статусов
> [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](2026-05-17_backlog_rag-optimization_v1.5.md)
> §0.6 и реализуется отдельным PR.

## 🗂 Метаданные

- **Дата:** 2026-05-20
- **Версия:** v1.0
- **Тип документа:** `backlog` (см. [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1 §3.2)
- **Статус:** `Draft → Review`
- **Автор:** konard (AI issue solver, по [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182))
- **Владелец ревью:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
- **Связанный PR:** [#183](https://github.com/G-Ivan-A/clarify-engine-ai/pull/183)
- **Исходные данные:** Отчёт тестировщика «🔍 Верификация процесса развёртывания Clarify Engine AI» от 2026-05-20 (полный текст — в теле [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182))
- **Связанный основной бэклог:** [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](2026-05-17_backlog_rag-optimization_v1.5.md) — продолжаем сквозную нумерацию (V-10 invariant, см. §0.6 v1.5, §0.2 и §12.2 v1.4)
- **Связанные документы:**
  - [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) — runbook, по которому проводилось тестирование (артефакт BL-45)
  - [`docs/user_guide/02_interface_elements.md`](../user_guide/02_interface_elements.md) §2 «Зона загрузки файла» — документированное поведение режима «📊 Анализ ТЗ» (артефакт BL-44)
  - [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md) — исследование инсталлятора и cloud-доступа (BL-47), формирует контекст для BL-48 (installer) и BL-49 (cloud)
  - [`docs/CONCEPT.md`](../CONCEPT.md) §4 FR-01 «Парсинг входных файлов (`.xlsx`+`.docx`)», §4 FR-07 «Streamlit UI», §5 NFR-04/NFR-05 (резидентность, 0 утечек), §5 NFR-08 «Доступность сервиса»
  - [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — гибридный поиск, контракт инфраструктуры RAG-пайплайна
- **Связанные Issues:** [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (этот документ), [#168 / BL-41](https://github.com/G-Ivan-A/clarify-engine-ai/issues/168) (UI refactor — источник регрессии для BL-54), [#173 / BL-44](https://github.com/G-Ivan-A/clarify-engine-ai/issues/173) (user guide), [#176 / BL-45](https://github.com/G-Ivan-A/clarify-engine-ai/issues/176) (ARM runbook), [#180 / BL-47](https://github.com/G-Ivan-A/clarify-engine-ai/issues/180) (installer research)

---

## 1. Цель и область применения

**Цель документа** (повторяет формулировку [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)):

> Сформировать новую ветку бэклога (задач) на исправления продукта для
> контроля задач в рамках тестирования на АРМ пользователя. Устранить все
> проблемы, получить ожидаемое поведение системы в соответствии с
> документацией проекта. Записать в документацию хранения бэклогов.

**Область применения.** Документ покрывает 7 проблем, выявленных в первом
функциональном тестировании по runbook
[`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md).
Все задачи привязаны к конкретным разделам отчёта тестировщика и к
существующим артефактам документации (runbook, user guide, CONCEPT, ADR).

**Что НЕ входит в область.** Документ не запускает кодовых изменений. Документ
не пересматривает архитектурные ADR-001 / ADR-003 / ADR-007. Документ не
изменяет статус активных задач основного бэклога v1.4 (BL-30..BL-47) — он
только добавляет новые BL-задачи в сквозную нумерацию и обновляет §0.6
основного файла после ревью PO.

**Сквозная нумерация (V-10 invariant).** Основной бэклог v1.4 §0.6 содержит
открытые BL-30..BL-32, BL-46, BL-47. Исследование BL-47
([`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md))
явно зарезервировало:
- `BL-48` — реализация инсталлятора `clarify-setup.cmd` (Sprint 4);
- `BL-49` — облачный доступ к ТЗ (WebDAV + S3, Sprint 5).

Поэтому новые задачи получают идентификаторы **BL-50..BL-56**. Следующий
свободный ID после этого документа — `BL-57`.

---

## 2. Сводка по тестированию

| Категория | Кол-во | Комментарий |
|-----------|--------|-------------|
| Учтённых этапов развёртывания | 8 | Подготовка среды → клонирование → venv → конфигурация → Ollama → переменные → индексация → Streamlit |
| Выявленных проблем | **7** | Покрываются BL-50..BL-56 |
| Решено на месте (workaround) | 4 | `.env.txt`-rename, замена модели в `.env`, полный путь к Ollama, прогрев модели |
| Требуют доработки кода | **3** | Валидация `.env` (BL-50), UI «Анализ ТЗ» (BL-54), автодетект Ollama (BL-51) |
| Успешно протестированные компоненты | 6 | RAG-поиск, Ollama, fallback-цепочка, режим «Консультация», индексация КБ (6934 чанка, 100 % покрытие метаданных), Streamlit UI |
| Общее время развёртывания | ~45 минут | Без учёта скачивания модели |
| Время первичной индексации | ~24 минуты | CPU embedding `bge-m3` на корпусе из 11 PDF |

**Готовность к пилоту:** ⚠️ **Частично готова** — режим «💬 Консультация»
работает (RAG + LLM), но основной use-case «📊 Анализ ТЗ» (массовая проверка
требований из загруженного файла) заблокирован (BL-54 P0).

---

## 3. Карта зависимостей (depends_on graph)

```
BL-50 (.env validation) ──► BL-52 (.env.example sync)
BL-51 (Ollama PATH)     ──► [updates runbook §1] ──┐
BL-52 (.env.example)    ──► [updates runbook §1] ──┤
BL-53 (Streamlit cache) ──► [updates runbook §2] ──┼──► BL-45 (runbook v2)
BL-54 (Анализ ТЗ UI)    ──► BL-41 (UI refactor)    │
BL-55 (first-response)  ──► [updates user_guide]   │
BL-56 (datetime.utcnow) — независима, tech debt    │
                                                    │
[все P0/P1 fixes] ─────► retest pass ──────────────┘
```

Граф **ацикличен**. Внешние зависимости:
- `BL-41` — закрыта (см. v1.4 §15 архив Sprint 3), фиксируется как источник регрессии BL-54.
- `BL-44`, `BL-45` — закрыты, обновляются документально в рамках retest после BL-50..BL-55.
- `BL-48` (installer) — открыта в v1.4 §0.6 как следствие BL-47; BL-50..BL-53 формируют **требования** к BL-48 (см. §6 ниже).

---

## 4. Бэклог исправлений (BL-50..BL-56)

### 4.1. Сводная таблица

| ID | Задача | Приоритет | Effort | depends_on | Источник проблемы | Файлы для правки (после Accepted) |
|----|--------|-----------|--------|-----------|--------------------|-----------------------------------|
| **BL-50** | Startup-валидация `.env` (detect `.env.txt` + автокопирование `.env.example`) | **P0** | S (0.5 д) | — | Отчёт §1.4 «Notepad сохранил как `.env.txt`», Проблема #1 | `src/config_loader.py` (новый guard) или `src/pipeline.py`, `src/ui/app.py` startup |
| **BL-51** | Автодетект пути к Ollama + PATH guidance в runbook | P1 | S (0.5 д) | — | Отчёт §1.5 / Проблема #2 | `src/llm/client.py` (`OllamaProvider`), [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1 |
| **BL-52** | Sync `OLLAMA_MODEL` в `.env.example` с runbook (`qwen2.5:7b`) | **P0** | XS (0.25 д) | BL-50 | Отчёт §1.4 / Проблема #3 | [`.env.example`](../../.env.example) :34 |
| **BL-53** | Документировать поведение Streamlit `.env`-кэша + кнопка «Перезагрузить конфиги» в debug-mode | P2 | S (0.5 д) | — | Отчёт §1.6 / Проблема #4 | [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §2/§6, [`docs/user_guide/04_troubleshooting.md`](../user_guide/04_troubleshooting.md), `src/ui/components/sidebar.py` (опционально) |
| **BL-54** | **🔴 КРИТИЧНО — Восстановить file uploader в режиме «📊 Анализ ТЗ»** | **P0** | M (2–3 д) | BL-28, BL-29, BL-41 | Отчёт §1.8 / Проблема #5 (блокирует пилот) | [`src/ui/app.py`](../../src/ui/app.py) `_run_analysis_mode`, [`src/ui/components/`](../../src/ui/components/), [`src/ui/constants.py`](../../src/ui/constants.py) (label updates), `tests/test_ui_modes.py`, `tests/test_ui_components.py` |
| **BL-55** | UX первого ответа: progress-indicator + warmup-кнопка | P2 | S (1 д) | — | Отчёт §2 / Проблема #6 (60–90 сек) | [`src/ui/app.py`](../../src/ui/app.py), [`src/ui/components/`](../../src/ui/components/), [`src/ui/constants.py`](../../src/ui/constants.py) |
| **BL-56** | Замена `datetime.utcnow()` на timezone-aware datetime (Python 3.14 deprecation) | P2 | XS (0.25 д) | — | Отчёт §1.7 / Проблема #7 | [`knowledge_base/indexing/build_index.py`](../../knowledge_base/indexing/build_index.py) :116 |

**Совокупная нагрузка:** ≈ 5–6 человеко-дней (один Sprint Hot-fix). BL-54 —
основной риск длительности; реальный effort зависит от того, восстанавливаем ли
мы старый путь из `src/app.py` (M, ~2 д) или интегрируем новый паттерн
`ExportRouter`+`file_uploader` поверх BL-41 рефакторинга (M+, ~3 д).

### 4.2. BL-50 — Startup-валидация `.env` (P0)

| Поле | Значение |
|------|----------|
| **ID** | BL-50 |
| **Приоритет** | P0 |
| **Effort** | S (0.5 д) |
| **depends_on** | — |
| **Статус** | `⏳ Waiting` (после `Accepted`) |
| **Источник проблемы** | Отчёт тестировщика §1.4 / Проблема #1 |
| **Контекст** | Windows Explorer скрывает расширения файлов по умолчанию; Notepad при «Сохранить как» добавляет `.txt`, если пользователь не выбрал `All Files (*.*)`. Тестировщик потратил ~10 минут на диагностику до обнаружения дубликата `.env.txt`. |
| **Проблема** | Приложение читает строго `.env`. Если рядом существует `.env.txt`, переменные окружения молча игнорируются. LLM-запросы падают на HTTP 404 (имя модели не загружено) или «Все провайдеры недоступны». Ошибка возникает на 100 % АРМ с дефолтной Windows-конфигурацией. |
| **Решение** | Добавить guard в startup-путь (один из: `src/config_loader.py` если есть, иначе `src/pipeline.py` и `src/ui/app.py`): 1) Если `.env` отсутствует И `.env.txt` существует — `logger.error` + остановка с понятной подсказкой («Обнаружен `.env.txt` — переименуйте в `.env` командой `ren .env.txt .env`»). 2) Если `.env` отсутствует И `.env.txt` тоже — `logger.info` + auto-copy `.env.example → .env` (см. отчёт §5 рекомендация MUST HAVE #1). 3) После загрузки `.env` — валидация ключевых переменных (`OLLAMA_MODEL`, `OLLAMA_BASE_URL`) на непустоту. |
| **Триггеры готовности** | Юнит-тесты `tests/test_env_validation.py`: (a) `.env.txt` без `.env` → fail с явной ошибкой; (b) только `.env.example` → auto-create `.env` и продолжить; (c) пустой `OLLAMA_MODEL` в `.env` → fail с подсказкой. Smoke-прогон runbook на чистой Windows 11 проходит без ручных вмешательств в `ren`/`copy`. CHANGELOG-запись `BL-50 .env startup validation`. |
| **Связь с документацией** | [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1.4 (Notepad-предупреждение остаётся; добавляется ссылка «BL-50 startup-guard скажет вам об этом автоматически»); [`docs/user_guide/04_troubleshooting.md`](../user_guide/04_troubleshooting.md) — раздел «`.env` не найден». |

### 4.3. BL-51 — Автодетект пути к Ollama + PATH guidance (P1)

| Поле | Значение |
|------|----------|
| **ID** | BL-51 |
| **Приоритет** | P1 |
| **Effort** | S (0.5 д) |
| **depends_on** | — |
| **Статус** | `⏳ Waiting` |
| **Источник проблемы** | Отчёт §1.5 / Проблема #2 |
| **Контекст** | Инсталлятор Ollama для Windows не добавляет путь в системный PATH автоматически. Тестировщик использовал полный путь `C:\Users\ivan\AppData\Local\Programs\Ollama\ollama.exe` в каждой команде. Это усложняет runbook и повторяемость для других АРМ (другой `%USERNAME%`). |
| **Проблема** | Команда `ollama` не работает в свежей CMD-сессии после установки. Runbook §1, §2 предполагают доступность `ollama` в PATH, но в реальности БА должен либо вручную править PATH, либо копировать полный путь. На разных АРМ путь различается (`%LOCALAPPDATA%` ≠ `C:\Users\ivan\...` у других пользователей). |
| **Решение** | (1) В `src/llm/client.py` (`OllamaProvider`) добавить вспомогательную функцию `_resolve_ollama_executable()`: пробуем `shutil.which("ollama")`, затем стандартные пути (`%LOCALAPPDATA%\Programs\Ollama\ollama.exe`, `C:\Program Files\Ollama\ollama.exe`). Логируем найденный путь. Если не найден — детерминированная ошибка с инструкцией. (2) В `docs/runbooks/arm-deployment-ivan.md` §1 добавить шаг «Добавьте Ollama в PATH» с `setx PATH "%PATH%;%LOCALAPPDATA%\Programs\Ollama"` и явным указанием перезапустить CMD. (3) `tests/test_ollama_resolution.py` — мокаем `shutil.which` и проверяем fallback на стандартный путь. |
| **Триггеры готовности** | Тест `test_ollama_resolution.py` зелёный. Runbook §1 содержит шаг «setx PATH» с явным предупреждением о перезапуске CMD. Smoke-прогон на чистой Windows 11 без ручной правки PATH успешно проходит `ollama serve` / `ollama pull qwen2.5:7b`. |
| **Связь с документацией** | Runbook §1 (новый шаг), §6 «Сценарий В: ошибка в UI» — обновить строку «Connection refused» с указанием на BL-51 guard. |

### 4.4. BL-52 — Sync `OLLAMA_MODEL` в `.env.example` (P0)

| Поле | Значение |
|------|----------|
| **ID** | BL-52 |
| **Приоритет** | P0 |
| **Effort** | XS (0.25 д) |
| **depends_on** | BL-50 (валидатор должен поймать рассинхрон, если он повторится) |
| **Статус** | `⏳ Waiting` |
| **Источник проблемы** | Отчёт §1.4 / Проблема #3 |
| **Контекст** | [`.env.example`](../../.env.example) :34 содержит `OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M` (квантованная сборка). [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) :83 рекомендует `OLLAMA_MODEL=qwen2.5:7b` (базовая сборка), и `ollama pull qwen2.5:7b` (строка :96 runbook) скачивает именно базовую модель. Это **прямой рассинхрон артефактов**, который ловится только в проде через HTTP 404 от Ollama. |
| **Проблема** | После `copy .env.example .env` без ручной правки имя модели в `.env` не соответствует имени фактически скачанной модели. Ollama возвращает HTTP 404 на каждый LLM-вызов. Цепочка fallback приводит к ошибке «Все провайдеры недоступны» (если GigaChat/OpenRouter без ключей). RAG-поиск при этом работает корректно — это сильнее запутывает пользователя. |
| **Решение** | (1) Изменить [`.env.example`](../../.env.example) :34 на `OLLAMA_MODEL=qwen2.5:7b` (согласовано с runbook §1.4 и §1.5). (2) Добавить комментарий выше строки: `# Должно совпадать с моделью из 'ollama pull' (см. arm-deployment-ivan.md §1.5).`. (3) Добавить регрессионный тест `tests/test_env_example_runbook_sync.py`: парсить `OLLAMA_MODEL=` из `.env.example` и `ollama pull qwen2.5:` из runbook — значения должны совпадать. Это страхует от ручного дрейфа в будущем. |
| **Триггеры готовности** | Тест `test_env_example_runbook_sync.py` зелёный. На чистой АРМ-сессии после `copy .env.example .env` (без правки) первый LLM-запрос успешен. CHANGELOG-запись `BL-52 .env.example OLLAMA_MODEL aligned to qwen2.5:7b`. |
| **Связь с документацией** | Runbook §1.4 — убрать строку «Стало: `qwen2.5:7b`» из таблицы исправлений (поскольку теперь это default). |

### 4.5. BL-53 — Документировать Streamlit `.env`-кэш + Reload Config (P2)

| Поле | Значение |
|------|----------|
| **ID** | BL-53 |
| **Приоритет** | P2 |
| **Effort** | S (0.5 д) |
| **depends_on** | — |
| **Статус** | `⏳ Waiting` |
| **Источник проблемы** | Отчёт §1.6 / Проблема #4 |
| **Контекст** | Streamlit загружает `.env` и YAML-конфиги через `load_dotenv()` и `yaml.safe_load()` один раз при старте процесса. Hot-reload работает только для исходников `src/`, но не для `.env` и `configs/*.yaml`. Тестировщик потратил время на отладку «изменил `.env`, обновил браузер — ошибка осталась». |
| **Проблема** | Поведение Streamlit-кэша не документировано в runbook и user guide. Пользователи (БА) тратят время на ложную диагностику, теряя доверие к системе. |
| **Решение** | (1) В runbook §2 (Сценарий А) и §6 (Сценарий В) добавить явный блок «⚠️ После изменения `.env` или `configs/*.yaml`: `Ctrl+C` → `streamlit run` заново → `Ctrl+Shift+R` в браузере». (2) В [`docs/user_guide/04_troubleshooting.md`](../user_guide/04_troubleshooting.md) добавить раздел «Изменения в `.env` не применяются». (3) **Опционально (если P0 не блокирует Sprint):** в debug-mode (флаг `ui.debug_mode: true` в [`configs/ui_config.yaml`](../../configs/ui_config.yaml)) показывать в сайдбаре кнопку «🔄 Перезагрузить конфиги» — вызывает `os.execv(sys.executable, sys.argv)` или эквивалентный graceful-restart. Кнопка скрыта в production-режиме. |
| **Триггеры готовности** | Runbook §2 и §6 содержат явные предупреждения. User guide §4 содержит троублшут «`.env` cache». При включённом debug-mode кнопка «Перезагрузить конфиги» появляется в сайдбаре и корректно перезапускает процесс. Smoke-тест `tests/test_arm_deployment_runbook.py` обновлён, проверяет наличие новых строк-предупреждений. |
| **Связь с документацией** | Runbook §2, §6; user guide `04_troubleshooting.md`; `configs/ui_config.yaml` (флаг `debug_mode`). |

### 4.6. BL-54 — 🔴 Восстановить file uploader в режиме «📊 Анализ ТЗ» (P0, БЛОКИРУЕТ ПИЛОТ)

| Поле | Значение |
|------|----------|
| **ID** | BL-54 |
| **Приоритет** | **P0** — блокирует основной use-case пилота |
| **Effort** | M (2–3 д) |
| **depends_on** | `BL-28` (ExportRouter, см. v1.4 §12.1 — закрыта в Sprint 3, см. v1.4 §15 архив), `BL-29` (UI-селектор экспорта, закрыта), `BL-41` (UI refactor, закрыта — источник регрессии) |
| **Статус** | `⏳ Waiting` |
| **Источник проблемы** | Отчёт §1.8 / Проблема #5; visual evidence — два прикреплённых скриншота в [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182): (a) ожидаемый UI согласно «руководству» = file uploader + format selector + «Скачать отчет»; (b) фактический UI на тестировании = только chat-style text-area без uploader |
| **Контекст** | **Документированное поведение режима «📊 Анализ ТЗ»** ([`docs/user_guide/02_interface_elements.md`](../user_guide/02_interface_elements.md) §2): «Прямоугольная область **«📎 Файл тендерного ТЗ»** с подсказкой «Drag and drop file here / Upload»». Принимаются `.xlsx` / `.docx`, лимит 10 МБ. Согласуется с FR-01 ([`docs/CONCEPT.md`](../CONCEPT.md) §4 FR-01 «Парсинг входных файлов (`.xlsx`+`.docx`)»). **Подтверждается runbook** ([`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1.8: «В режиме "Анализ ТЗ" загрузите тестовый файл из `test_data`, запустите анализ и скачайте отчет»). **Подтверждается ExportRouter** ([`docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md`](2026-05-17_backlog_rag-optimization_v1.4.md) §12.1 / BL-28: «Round-trip-матрица `xlsx in → {xlsx, docx, md} out`, `docx in → {docx, md} out`»). |
| **Проблема** | **Фактическое поведение** в [`src/ui/app.py`](../../src/ui/app.py) (точка входа runbook `streamlit run src/ui/app.py`): режим `MODE_STATELESS` («📊 Анализ ТЗ», см. [`src/ui/constants.py:18-22`](../../src/ui/constants.py)) реализует **stateless query-mode** — `st.text_area` с placeholder «Сформулируйте вопрос или вставьте требование из ТЗ…» (см. [`src/ui/constants.py:113-116`](../../src/ui/constants.py)). File uploader (`st.file_uploader` для `.xlsx`/`.docx`) **отсутствует**. Селектор формата отчёта **disabled** до выполнения запроса. Кнопка «Скачать отчёт» **неактивна**. **Корневая причина:** BL-41 UI refactor (`src/ui/`, issue #168) разделил оригинальный `src/app.py::render_analysis_tab` (там `st.file_uploader` на [`src/app.py:237`](../../src/app.py)) на компоненты, но **не перенёс** file-upload-путь в новый `_run_analysis_mode`. BL-44 user guide написан под ожидаемое поведение (`02_interface_elements.md` §2), BL-45 runbook ссылается на `src/ui/app.py` — рассинхрон между документацией и кодом не был пойман в BL-43 smoke/E2E gate (поскольку CLI-pipeline `python -m src.pipeline` корректен). |
| **Решение** | **Архитектурное решение:** объединить два пути в `src/ui/app.py`, сохраняя BL-41 архитектуру компонентов. Конкретно: (1) В `src/ui/components/` добавить компонент `analysis_uploader.py` — `st.file_uploader` + валидация расширения (`.xlsx`/`.docx`) + лимит 10 МБ ([CONCEPT NFR-09](../CONCEPT.md#5-нефункциональные-требования-нфт)). (2) В `_run_analysis_mode` ([`src/ui/app.py`](../../src/ui/app.py) lines 996-1027) заменить текущий `st.text_area`-flow на: `uploaded_file = analysis_uploader.render()`; если файл загружен → `st.radio` для формата (xlsx/docx/md, через `EXPORT_FORMAT_LABELS` из `src/ui/constants.py:46-50`); кнопка «🚀 Запустить анализ» → вызов существующего `src.pipeline.run_pipeline(file_path, output_format)`; результат → `ExportRouter` (BL-28). (3) Сохранить query-style как **под-режим** (для smoke-тестирования одного требования) под опциональным флагом `ui.analysis_query_mode: true` в [`configs/ui_config.yaml`](../../configs/ui_config.yaml), default = `false`. Это снимает риск ломать BL-43 E2E-тесты, которые могли опираться на текущий путь. (4) Обновить `tests/test_ui_modes.py` — добавить кейсы upload + format + download. (5) Обновить `tests/test_ui_components.py` — кейсы для `analysis_uploader`. (6) **НЕ менять** label «📊 Анализ ТЗ» в `src/ui/constants.py:19` — он соответствует user guide. |
| **Триггеры готовности** | (a) При запуске `streamlit run src/ui/app.py` и выборе «📊 Анализ ТЗ» отображается file uploader с подписью из user guide §2 («📎 Файл тендерного ТЗ»). (b) Загрузка `test_data/sample_tz.xlsx` → выбор формата `.xlsx` → клик «Запустить анализ» → за ≤ 15 мин (NFR-03) генерируется отчёт; кнопка «Скачать отчёт» становится активной. (c) `tests/test_ui_modes.py` и `tests/test_ui_components.py` зелёные. (d) Smoke-тест `tests/test_arm_deployment_runbook.py` (BL-45) подтверждает, что runbook §1.8 (загрузка файла + скачивание отчёта) выполним без модификаций. (e) E2E-тест BL-43 (`docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md`) повторно зелёный, **с дополнительным сценарием** «UI upload → analyse → download». (f) Скриншот «после» в PR соответствует ожидаемому UI из [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182). |
| **Связь с документацией** | [`docs/user_guide/02_interface_elements.md`](../user_guide/02_interface_elements.md) §2 — без правок (уже описывает целевое поведение). [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md) §1.8, §5 — добавить explicit-проверку «file uploader виден» в чек-лист. [`docs/CONCEPT.md`](../CONCEPT.md) §4 FR-07 — без правок. [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md`](2026-05-17_backlog_rag-optimization_v1.4.md) §11.1 FR-01 — добавить ссылку BL-54 в строку «FR-01 Парсинг входных файлов». |

### 4.7. BL-55 — UX первого ответа: progress indicator + warmup (P2)

| Поле | Значение |
|------|----------|
| **ID** | BL-55 |
| **Приоритет** | P2 |
| **Effort** | S (1 д) |
| **depends_on** | — |
| **Статус** | `⏳ Waiting` |
| **Источник проблемы** | Отчёт §2 проблема #6 (первый запрос 60–90 сек на CPU-only) |
| **Контекст** | CPU-only инференс через Ollama даёт холодный старт 60–90 сек (модель `qwen2.5:7b` грузится в RAM). `bge-m3`-embedding тоже на CPU. Пользователь видит «крутилку» в Streamlit без подсказки и может подумать, что система зависла. |
| **Проблема** | Снижение доверия пользователя на этапе пилота. Не блокирует работу, но влияет на UX и репутацию системы. |
| **Решение** | (1) В [`src/ui/constants.py`](../../src/ui/constants.py) `LABELS` обновить `spinner_llm` на «Спрашиваем LLM (GigaChat → OpenRouter → Ollama)… ⏱ Первый ответ на CPU может занять 60–90 сек.». (2) В сайдбаре сделать кнопку «🔥 Прогреть модель» (visible только в debug-mode или при `OLLAMA_BASE_URL` локальном) — выполняет фоновый `requests.post(OLLAMA_BASE_URL + "/api/generate", {"model": ..., "prompt": "ok", "keep_alive": "10m"})`. (3) В [`docs/user_guide/01_intro_modes.md`](../user_guide/01_intro_modes.md) добавить предупреждение «На CPU-only АРМ первый ответ — 60–90 сек, последующие — 5–15 сек». (4) В runbook §1.8 уже есть «На CPU-only Ollama первый ответ может занимать до 90 секунд» — подтвердить актуальность. |
| **Триггеры готовности** | Юнит-тест `tests/test_ui_constants.py` (если есть) подтверждает обновлённый `spinner_llm`. На локальном smoke первый запрос отображает обновлённый прогресс-текст. Кнопка прогрева работает (POST в Ollama даёт 200 OK). User guide обновлён. |
| **Связь с документацией** | User guide `01_intro_modes.md`, `04_troubleshooting.md`; runbook §1.8 (без правок). |

### 4.8. BL-56 — Замена `datetime.utcnow()` на timezone-aware datetime (P2)

| Поле | Значение |
|------|----------|
| **ID** | BL-56 |
| **Приоритет** | P2 |
| **Effort** | XS (0.25 д) |
| **depends_on** | — |
| **Статус** | `⏳ Waiting` |
| **Источник проблемы** | Отчёт §1.7 проблема #7 |
| **Контекст** | Python 3.14 (целевая версия АРМ — runbook §1) помечает `datetime.utcnow()` как `DeprecationWarning`. На индексации (`py knowledge_base\indexing\build_index.py`) warning попадает в stderr и в логи. |
| **Проблема** | (a) Логи засоряются deprecation-warnings, что снижает их пригодность для production-аудита (NFR-06). (b) В будущей версии Python метод будет удалён → индексация упадёт с `AttributeError`. (c) Косметика — пользователь видит warning и может подумать о сбое. |
| **Решение** | В [`knowledge_base/indexing/build_index.py`](../../knowledge_base/indexing/build_index.py): (1) Заменить импорт на строке 29: `from datetime import date, datetime, timezone`. (2) Заменить строку 116 на: `"time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),` (либо проще: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`). (3) Поискать другие `datetime.utcnow()` в кодовой базе (`grep -rn "datetime.utcnow" src/ knowledge_base/`) и применить ту же правку. (4) `tests/test_build_index.py` — добавить ассерт, что лог-строка времени заканчивается на `Z` и парсится через `datetime.fromisoformat(...)`. |
| **Триггеры готовности** | `grep -rn "datetime.utcnow" .` возвращает 0 совпадений в `src/` и `knowledge_base/`. `py knowledge_base\indexing\build_index.py` не выдаёт `DeprecationWarning` в stderr. Лог-строки `kb_indexer` сохраняют валидный ISO-8601 формат (`...Z`). |
| **Связь с документацией** | Нет правок документации (внутренний tech debt). |

---

## 5. Матрица соответствия (Test Report ↔ BL ↔ Документация)

| # | Проблема (отчёт §) | BL | Затронутая документация |
|---|--------------------|------|--------------------------|
| 1 | §1.4 / Проблема #1 — Notepad → `.env.txt` | BL-50 | Runbook §1.4, user guide `04_troubleshooting.md`, `tests/test_arm_deployment_runbook.py` |
| 2 | §1.5 / Проблема #2 — Ollama не в PATH | BL-51 | Runbook §1, `src/llm/client.py` |
| 3 | §1.4 / Проблема #3 — Mismatch имени модели | BL-52 | `.env.example`, runbook §1.4 |
| 4 | §1.6 / Проблема #4 — Streamlit кэширует `.env` | BL-53 | Runbook §2 / §6, user guide `04_troubleshooting.md`, `configs/ui_config.yaml` |
| 5 | §1.8 / Проблема #5 — Режим «📊 Анализ ТЗ» без uploader | **BL-54 (P0)** | `src/ui/app.py`, `src/ui/components/`, `src/ui/constants.py`, user guide `02_interface_elements.md` (без правок), `docs/backlog/...v1.4.md` §11.1 FR-01 |
| 6 | §2 / Проблема #6 — Долгий первый ответ (60–90 сек) | BL-55 | `src/ui/constants.py`, user guide `01_intro_modes.md`, runbook §1.8 |
| 7 | §1.7 / Проблема #7 — `datetime.utcnow()` deprecation | BL-56 | `knowledge_base/indexing/build_index.py:29,116` |

---

## 6. Связь с активным реестром (v1.5 §0.6) и BL-48 (Installer)

### 6.1. Обновление §0.6 основного бэклога

> **Статус на момент создания этого файла (v1.0, 2026-05-20):** одноимённый
> PR с этим документом одновременно создаёт
> [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](2026-05-17_backlog_rag-optimization_v1.5.md),
> где §0.6 уже содержит строки BL-50..BL-56 со статусом `📝 New`.
> Приведённая ниже таблица — целевой статус **после Accepted PO**: BL-задачи
> переходят из `📝 New` в `⏳ Waiting` (или `🟡 In Progress` для hot-fix-релиза)
> и закрепляются за конкретными PR.

После `Accepted` ревью PO в [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](2026-05-17_backlog_rag-optimization_v1.5.md)
§0.6 обновляются строки:

| ID | Задача | Приоритет | Статус | Зависимости | Обоснование | DoD |
|----|--------|-----------|--------|-------------|-------------|-----|
| BL-50 | Startup-валидация `.env` (detect `.env.txt`) | P0 | ⏳ Waiting | — | Pilot blocker — silent .env miss приводит к HTTP 404 на Ollama | `tests/test_env_validation.py` зелёный, runbook §1.4 ссылается на BL-50 |
| BL-51 | Автодетект пути к Ollama + PATH guidance | P1 | ⏳ Waiting | — | Усложнение runbook для не-технических БА | `tests/test_ollama_resolution.py` зелёный, runbook §1 содержит шаг `setx PATH` |
| BL-52 | Sync `OLLAMA_MODEL` в `.env.example` | P0 | ⏳ Waiting | BL-50 | Прямой рассинхрон `.env.example` ↔ runbook | `tests/test_env_example_runbook_sync.py` зелёный, default `.env` работает без правки |
| BL-53 | Streamlit `.env`-кэш: документация + Reload Config | P2 | ⏳ Waiting | — | UX — потеря времени БА на ложную диагностику | Runbook §2/§6 содержит предупреждения, user guide `04_troubleshooting.md` обновлён |
| **BL-54** | **🔴 Восстановить file uploader в режиме «📊 Анализ ТЗ»** | **P0** | ⏳ Waiting | BL-28, BL-29, BL-41 | **Pilot blocker** — основной use-case недоступен; рассинхрон BL-41 ↔ BL-44/BL-45 | `tests/test_ui_modes.py`, `tests/test_ui_components.py` зелёные; BL-43 E2E повторно зелёный с upload-сценарием |
| BL-55 | UX первого ответа: progress + warmup | P2 | ⏳ Waiting | — | Снижение доверия БА при 60–90 сек ожидании | Обновлённый `spinner_llm` в `src/ui/constants.py`, user guide §1 |
| BL-56 | `datetime.utcnow()` → timezone-aware | P2 | ⏳ Waiting | — | Python 3.14 deprecation, tech debt | `grep` показывает 0 `datetime.utcnow()` в `src/` и `knowledge_base/`, `tests/test_build_index.py` зелёный |

### 6.2. Связь с BL-48 (Installer, Sprint 4)

Исследование [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md)
§5 («План реализации») зафиксировало BL-48 как PoC `clarify-setup.cmd`
(≤ 8 ч). Текущий бэклог формирует **дополнительные acceptance-критерии** для
BL-48, которые ловятся через BL-50..BL-53:

| BL | Что должен делать `clarify-setup.cmd` |
|----|----------------------------------------|
| BL-50 | Wizard сам копирует `.env.example → .env` и редактирует через `set/echo`, минуя Notepad. Проверка существования `.env.txt` встроена в wizard step. |
| BL-51 | Wizard проверяет `where ollama`, в случае отсутствия — добавляет `%LOCALAPPDATA%\Programs\Ollama` через `setx PATH`. |
| BL-52 | Wizard читает `OLLAMA_MODEL` из `.env`, сверяет с `ollama list`, при несоответствии — `ollama pull <model>` или ошибка с подсказкой. |
| BL-53 | Wizard в конце прогрева запускает `streamlit run src/ui/app.py` свежим процессом — гарантия отсутствия stale-кэша. |

После реализации BL-50..BL-53 как **отдельных runtime-guard-ов в `src/`**,
BL-48 wizard просто полагается на них (DRY: один источник истины —
runtime-валидатор) и обогащает CLI-инсталляторный UX (прогресс-бар,
обработка прерываний).

---

## 7. План реализации

| Sprint | Задачи | Артефакт |
|--------|--------|----------|
| **Hot-fix Sprint** (≤ 1 нед) | BL-52, BL-56 (XS-задачи, изолированные) | PR с правкой `.env.example` + `build_index.py` (≤ 0.5 д) |
| **Sprint 4** | BL-50, BL-51, BL-54 (всё P0 / P1 руками) | PR с runtime-guards и восстановлением file uploader; повторный smoke-прогон runbook |
| **Sprint 4 (parallel)** | BL-48 (installer PoC) использует BL-50..BL-52 как зависимости | PoC `clarify-setup.cmd` ([BL-47 §5](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md#5-план-реализации)) |
| **Sprint 5** | BL-53, BL-55 (UX-polish) | PR с обновлённым user guide и опциональной кнопкой «Перезагрузить конфиги» |

Финальная очерёдность утверждается PO на Sprint Planning. **Условие старта
любой задачи:** статус документа `Accepted` и явное согласие PO в комментариях
[PR #183](https://github.com/G-Ivan-A/clarify-engine-ai/pull/183).

---

## 8. Definition of Done (для этого документа v1.0)

- [ ] Файл `docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md` создан и соответствует [`naming-convention.md`](../standards/naming-convention.md) v1.1 (тип `backlog`, дата `2026-05-20`, версия `v1.0`).
- [ ] Документ содержит 7 BL-задач (BL-50..BL-56), сопоставленных 1-к-1 с 7 проблемами отчёта тестировщика.
- [ ] Каждая задача имеет явные поля `Приоритет`, `Effort`, `depends_on`, `Контекст`, `Проблема`, `Решение`, `Триггеры готовности`, `Связь с документацией`.
- [ ] Граф зависимостей (§3) ацикличен; «висячих» ссылок нет (BL-28, BL-29, BL-41 — закрыты в v1.4 §15).
- [ ] §5 «Матрица соответствия» однозначно мапит проблемы отчёта на BL и затронутые файлы документации.
- [ ] §6.1 содержит готовую таблицу-вставку для §0.6 основного бэклога v1.4 → v1.5.
- [ ] §6.2 фиксирует связь с BL-48 (Installer) без дублирования scope.
- [ ] §7 содержит реалистичный sprint-план (Hot-fix → Sprint 4 → Sprint 5).
- [ ] Все ссылки на файлы документации существуют (валидируется в CI или ревью).
- [ ] CHANGELOG.md содержит запись `DOCUMENTATION: BL-* arm pilot test fixes backlog branch` (см. §10).
- [ ] PR [#183](https://github.com/G-Ivan-A/clarify-engine-ai/pull/183) переведён в статус Ready for Review, в описании указан testing report и список BL-50..BL-56.
- [ ] Статус документа `Draft → Review`. Кодовые изменения **не выполняются** в этом PR (только документация).

---

## 9. Решённые на месте проблемы (записано из отчёта тестировщика)

Эти проблемы **не требуют** отдельных BL-задач — workaround зафиксирован в
отчёте §1 и применяется до выполнения BL-50..BL-56:

| # | Workaround | Где зафиксировано |
|---|-----------|--------------------|
| (a) | Папка `clarify-engine-ai` заблокирована active venv → `deactivate` + `cd` из папки перед переименованием | Отчёт §1.2 |
| (b) | `ren` не сработал (Access denied) → `move clarify-engine-ai clarify-engine-ai_old_<date>` | Отчёт §1.2 |
| (c) | `force-reinstall torch torchvision` выполнилось мгновенно — CPU-версия уже была установлена из `requirements.txt` | Отчёт §1.3 nuance |
| (d) | Прогрев Ollama-модели через `ollama run qwen2.5:7b "Готов"` перед UI-сессией | Отчёт §1.5; уже в runbook §1.5, §2 |

Эти workaround-ы остаются в runbook §1 как «good practice» и не требуют
автоматизации в Sprint 4. При желании можно вынести в BL-57+ как «runbook
polish», но это вне scope текущего документа.

---

## 10. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1.0 | 2026-05-20 | Первая версия. Сформирована ветка бэклога BL-50..BL-56 по отчёту тестировщика на АРМ (issue [#182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182)). Учтены все 7 выявленных проблем; зафиксированы 4 workaround-а как already-resolved (§9); связь с BL-48 (Installer, [BL-47 research](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md)) описана в §6.2. Документ привязан к runbook BL-45, user guide BL-44, основному бэклогу v1.5 §0.6 (одновременно с этим файлом добавлен в PR #183). |

---

## 11. Ссылки

- Полный текст отчёта тестировщика — в теле [issue #182](https://github.com/G-Ivan-A/clarify-engine-ai/issues/182) (скриншоты ожидаемого vs фактического UI прикреплены).
- Основной бэклог (актуальная версия): [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.5.md`](2026-05-17_backlog_rag-optimization_v1.5.md).
- Основной бэклог (предыдущая версия): [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.4.md`](2026-05-17_backlog_rag-optimization_v1.4.md).
- ARM runbook (BL-45): [`docs/runbooks/arm-deployment-ivan.md`](../runbooks/arm-deployment-ivan.md).
- User guide для БА (BL-44): [`docs/user_guide/`](../user_guide/).
- Исследование инсталлятора (BL-47): [`docs/research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md`](../research/2026-05-20_bl-47_arm-installer-cloud-research_v1.md).
- Стандарт именования: [`docs/standards/naming-convention.md`](../standards/naming-convention.md) v1.1.
- BL-43 smoke/E2E baseline: [`docs/audit/2026-05-20_bl-43-smoke-e2e-report_v1.md`](../audit/2026-05-20_bl-43-smoke-e2e-report_v1.md).
