# `prompts/` — Centralised Prompt Library

Этот каталог — централизованная prompt library проекта (BL-08, issue #94).
Все системные и few-shot промпты хранятся здесь как версионируемые
артефакты, чтобы Prompt Owner мог редактировать их без правок Python и
чтобы каждое изменение проходило аудит (BL-23).

> **Не правьте промпты внутри `src/` или `configs/`.** В коде допустимы
> только вызовы загрузчика `src.llm.prompt_loader`. Минимальный fallback
> в `LLMClient._load_system_prompt` остаётся только на случай, когда
> файл недоступен (broken install / тест на отказоустойчивость).

## Структура

```
prompts/
├── system_classifier_v1.0.md      # системный промпт RAG-классификатора
├── system_rag_v1.0.md             # системный промпт free-text KB Q&A (UI)
├── system_rag_reflection_v1.0.md  # судья достаточности контекста для multi-hop
├── system_rag_query_expansion_v1.md # промпт генерации переформулировок
├── few_shot_examples_v1.0.json    # калибровочные few-shot примеры
├── prompt_changelog.md            # история версий + SHA-256
└── README.md                      # этот файл
```

## Конвенция именования

`<name>_v<MAJOR>.<MINOR>.<ext>` — версия в имени файла, без «алиаса
последней версии». Это значит, что любое изменение содержимого промпта
требует нового файла + новой строки в `prompt_changelog.md`. Старые
версии сохраняются, иначе мы не сможем воспроизвести регресс-прогоны
Golden Set (BL-05).

Допустимые расширения:

- `.md` — Markdown, основной формат для system-промптов.
- `.txt` — голый текст (когда Markdown не нужен).
- `.json` — структурированные few-shot примеры и метаданные.

## Загрузка из кода

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

`LLMClient` принимает аргумент `prompt_path=` для обратной совместимости
с пайплайном (`src/pipeline.py --prompt`); внутри он вызывает
`load_prompt_from_path`, который вытаскивает имя/версию из имени файла
и фиксирует SHA-256 в логе.

## Аудит изменений (Definition of Done)

1. Создайте новый файл по конвенции `<name>_v<MAJOR>.<MINOR>.<ext>`.
2. `sha256sum prompts/<file>` — посчитайте хеш.
3. Добавьте строку в `prompt_changelog.md`: версия, дата, автор, SHA-256,
   краткое описание изменений.
4. Если меняется default-версия — обновите вызовы `load_prompt(...)`
   и `LLMClient(prompt_path=...)`. Иначе ничего менять в коде не нужно.
5. Перезапустите тесты: `python -m pytest tests/test_prompt_loader.py -q`.

## A/B-тестирование

A/B-эксперименты сводятся к подмене аргумента `version` в точке вызова:
например, основной пайплайн остаётся на `v1.0`, а экспериментальный
скрипт `scripts/evaluate/evaluate_quality.py` запускается с `v1.1`.
Логика загрузки не зависит от Python-окружения — достаточно положить
рядом файл `system_classifier_v1.1.md` и добавить запись в changelog.

## Ссылки

- [`docs/ADR/004-prompt-management.md`](../docs/ADR/004-prompt-management.md) —
  архитектурное решение по управлению промптами.
- [`docs/CONCEPT.md`](../docs/CONCEPT.md) §6.5 — место промпт-менеджмента
  в общей картине Clarify Engine.
- [`docs/standards/roles.md`](../docs/standards/roles.md) §2.3 — роль и
  ответственность Prompt Owner.
