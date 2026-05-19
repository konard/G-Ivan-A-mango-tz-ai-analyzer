# ADR-004. Централизованная Prompt Library и версионирование промптов

**Status:** Accepted
**Date:** 2026-05-17
**Owner:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
**Author of draft:** konard (AI issue solver)
**Связанные документы:** [CONCEPT.md §6.5](../CONCEPT.md), [ADR-001](001-rag-architecture.md), [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.md) BL-08 / BL-23, [issue #94](https://github.com/G-Ivan-A/clarify-engine-ai/issues/94)

> 🔢 **Numbering Note (004A — Prompt Management).** В каталоге `docs/ADR/`
> совместно с этим документом существует [`004-ui-operation-modes.md`](004-ui-operation-modes.md)
> — оба ADR официально называются «ADR-004», но описывают **ортогональные**
> области принятия решений (управление промптами vs. режимы UI). Конвенция
> номеров и допустимость таких дублей зафиксированы в [`docs/ADR/README.md`](README.md).
> Для устранения неоднозначности в логах и ссылках используйте кодировку
> «ADR-004A (Prompt Management)» для этого файла и «ADR-004B
> (UI Operation Modes)» — для соседнего.

---

## Context

До этой задачи системные и few-shot-промпты были захардкожены прямо в
коде:

- `src/llm/client.py::LLMClient._load_system_prompt` содержал
  multi-line системный промпт классификатора.
- `src/ui/app.py::SYSTEM_PROMPT` хранил отдельный системный промпт для
  free-text RAG-ответа Streamlit-UI.
- Калибровочные few-shot-примеры лежали в `prompts/few_shot_examples.json`
  без версии в имени файла.

Это нарушало несколько принципов проекта:

1. **Аудит (BL-23).** Невозможно по логу `run_id` восстановить *точную*
   ревизию промпта, которая дала спорный ответ модели — Python-патчи
   шли смешанной кучей с правками промптов.
2. **Ответственность Prompt Owner**
   ([`docs/standards/roles.md`](../standards/roles.md) §2.3). Бизнес-роль
   должна редактировать промпты без правок Python; в текущем виде это
   требовало Pull Request с кодом.
3. **A/B-эксперименты.** Сравнение версий промпта требовало форка
   `LLMClient`, что несовместимо с критерием «нельзя менять публичные
   сигнатуры» в issue #94.
4. **NFR-04 — воспроизводимость.** Регресс-прогон Golden Set после
   правки промпта не отличим от регресса после правки кода, что мешает
   локализовать причину.

## Decision

Промпты переезжают в директорию `prompts/` как **версионируемые
артефакты с конвенцией имени и обязательной записью в changelog**.
Загрузка — через единый модуль `src/llm/prompt_loader.py`, который
вычисляет SHA-256 содержимого и логирует загрузку с привязкой к
`run_id`.

### 1. Структура каталога

```
prompts/
├── system_classifier_v1.0.md      # системный промпт RAG-классификатора
├── system_rag_v1.0.md             # системный промпт free-text KB Q&A (UI)
├── few_shot_examples_v1.0.json    # калибровочные few-shot примеры
├── prompt_changelog.md            # история версий + SHA-256
└── README.md                      # навигация и DoD для Prompt Owner
```

Конвенция имени файла: `<name>_v<MAJOR>.<MINOR>.<ext>`. Это значит, что
любое изменение содержимого промпта требует **нового файла** плюс новой
строки в `prompt_changelog.md`. Старые версии не удаляются — они нужны
для воспроизведения регресс-прогонов Golden Set (BL-05).

Допустимые расширения:

- `.md` — основной формат для системных промптов (Markdown).
- `.txt` — голый текст для коротких промптов.
- `.json` — структурированные few-shot-примеры и метаданные.

### 2. Loader API (`src/llm/prompt_loader.py`)

```python
from src.llm.prompt_loader import (
    load_prompt,
    load_few_shot_examples,
    load_prompt_from_path,
)

system = load_prompt("system_classifier", version="v1.0", run_id=run_id)
print(system.sha256)        # 'e3070fdc...' — audit trail
print(system.content[:80])  # 'You are an expert Business Analyst ...'

examples, sha = load_few_shot_examples("few_shot_examples", "v1.0")
```

Контракт:

- `load_prompt(name, version="v1.0", *, prompts_dir, run_id) -> PromptInfo` —
  ищет `{name}_{version}.md`, затем `.txt`. Возвращает `frozen dataclass`
  с полями `name`, `version`, `path`, `content`, `sha256`. Хеш считается
  по UTF-8-байтам и равен значению `sha256sum prompts/<file>`.
- `load_few_shot_examples(...)` — JSON-аналог для калибровочных примеров.
- `load_prompt_from_path(path, *, run_id)` — мост обратной совместимости
  для `LLMClient(prompt_path=...)`: вытаскивает `(name, version)` из
  имени файла или, если оно не соответствует конвенции, использует
  filename-stem и `version="unknown"`. Это позволяет старым тестам и
  пайплайну работать без изменений сигнатур.
- `parse_prompt_filename(filename)` — публичная утилита, возвращает
  `(name, version) | None`.
- `compute_sha256(content)` — вспомогательная функция, чтобы тесты и
  скрипты могли независимо проверить хеш.

### 3. Аудит-лог

Loader пишет `INFO`-запись в `src.llm.prompt_loader` с `extra=`-полями:

```python
{
    "prompt_name": "system_classifier",
    "prompt_version": "v1.0",
    "prompt_sha256": "e3070fdc...",
    "run_id": "<uuid>",  # только если передан caller'ом
}
```

JSON-логгер пайплайна (`src/pipeline.py::configure_json_logging`)
автоматически прокидывает эти поля в общий поток логов, и в анализе
сбоев Sentry / Loki можно фильтровать по `prompt_sha256` независимо от
номера версии. SHA-256 — основной audit-ключ, версия — человеко-читаемый
ярлык.

### 4. Интеграция

- `LLMClient._load_system_prompt` вызывает `load_prompt_from_path` с
  `DEFAULT_PROMPT_PATH = "prompts/system_classifier_v1.0.md"`. При
  `PromptNotFoundError` (например, в проде с broken install) остаётся
  минимальный inline-fallback в три абзаца — это требование к
  отказоустойчивости из issue #94, а не «дублирование промпта».
- `src/ui/app.py` хранит только имя и версию (`system_rag`, `v1.0`) и
  минимальный fallback; реальная загрузка идёт через
  `@st.cache_resource get_rag_system_prompt()` — лениво и один раз на
  процесс.
- Публичные сигнатуры `LLMClient.classify_requirement`,
  `LLMClient.generate_rag_response` **не меняются** (требование DoD).

### 5. Изменение промпта (Definition of Done)

1. Создать новый файл `<name>_v<MAJOR>.<MINOR>.<ext>` рядом со старым.
2. `sha256sum prompts/<file>` — записать хеш.
3. Добавить строку в `prompts/prompt_changelog.md`: версия, дата,
   автор, SHA-256, краткое описание изменений.
4. Если меняется default-версия — обновить вызовы `load_prompt(...)` и
   `LLMClient(prompt_path=...)`. Иначе ничего менять в Python не нужно.
5. Перезапустить `pytest tests/test_prompt_loader.py -q` (16 кейсов,
   <0.2 s).

## Consequences

### Positives

- **Аудит-трасса по SHA-256.** Любой ответ модели можно сопоставить с
  ревизией промпта по `prompt_sha256` в JSON-логе (BL-23 закрыт).
- **A/B без форка кода.** Достаточно положить `system_classifier_v1.1.md`,
  и evaluation-скрипт (`scripts/evaluate/evaluate_quality.py`) подгрузит
  его через `version="v1.1"`. Основной пайплайн продолжает работать на
  `v1.0` до явного промоушна.
- **Read-only роль Prompt Owner.** Бизнес-роль работает только с
  `prompts/*.md` и `prompt_changelog.md` — без Python.
- **Воспроизводимость.** Старые версии не удаляются, регресс на Golden
  Set всегда детерминирован.
- **Совместимость.** Сигнатура `LLMClient(prompt_path=...)` и default
  `DEFAULT_PROMPT_PATH` сохранены, существующие тесты и пайплайн
  работают без правок.

### Negatives / Tradeoffs

- **Дисциплина changelog.** SHA в `prompt_changelog.md` нужно
  поддерживать вручную; рассинхрон ловится только при ревью diff.
  Митигация: CI-проверка хеша добавляется в backlog отдельной задачей
  (см. §Triggers).
- **Минимальный fallback.** В `LLMClient` остаётся inline-копия первых
  абзацев промпта на случай broken install. Эта копия — *не* источник
  правды и помечена комментарием; при изменении основного промпта её
  обновлять не обязательно, но желательно.
- **Никакой Jinja.** Loader намеренно тонкий: нет шаблонов, нет
  переменных окружения, нет remote fetch. Это упрощает аудит, но
  означает, что любую динамику (имя пользователя, дата) каллер
  собирает сам.

## Alternatives considered

1. **YAML с метаданными в одном файле.** Отвергнуто: метаданные
   (автор, дата, SHA, описание) уже живут в `prompt_changelog.md`;
   дублирование в front-matter каждого файла создавало бы два источника
   правды и провоцировало рассинхрон. Метаданные смотрим в changelog,
   контент — в `.md`.
2. **Алиас `latest` (`system_classifier.md` → `v1.x`).** Отвергнуто: при
   откате на старую версию через `git checkout` сложно понять, какая
   именно ревизия активна. Явная версия в имени файла исключает
   неоднозначность.
3. **Хранение в БД (Chroma / SQLite).** Отвергнуто: промпты живут в
   git-репозитории как код, должны проходить ревью, не нуждаются в
   индексации.
4. **Авто-вычисление и hard-fail при расхождении SHA в changelog vs на
   диске.** Согласовано как follow-up: реализуется отдельной задачей
   (`scripts/check_prompts.py` + CI-шаг). В текущем ADR — только
   логирование SHA, расхождение виден в diff PR.

## Triggers for Revision

- Появление >5 версий любого промпта — нужен retention-policy для
  старых файлов.
- Запрос на A/B-тестирование по проценту трафика — потребует
  расширения loader'а (sticky bucket по `run_id`).
- Внедрение Prompt Owner-роли в CI (BL-24, draft) — может потребовать
  YAML-метаданных вместо changelog-таблицы.
- Появление CI-шага «промпт изменён без записи в changelog» — отдельный
  ADR не нужен, но обновим §How-to.

## History

- **v1.0 (2026-05-17, konard).** Initial Accepted. Loader + три промпта
  (`system_classifier_v1.0`, `system_rag_v1.0`, `few_shot_examples_v1.0`),
  changelog с SHA-256, 16 unit-тестов в `tests/test_prompt_loader.py`,
  обратная совместимость с `LLMClient(prompt_path=...)` сохранена.
- **v1.1 (2026-05-19, BL-40, issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)).**
  ADR-sync с CONCEPT.md v2.5 и BL-34 audit. Заменён неформальный
  Numbering Note на явную нотацию **«ADR-004A (Prompt Management)»** vs.
  **«ADR-004B (UI Operation Modes)»** со ссылкой на конвенцию
  [`docs/ADR/README.md`](README.md). Содержание решения и API loader'а
  не меняются.
