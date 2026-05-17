# 📂 docs/standards/

Каталог стандартов и шаблонов проектной документации: правила именования файлов, требования к структуре аналитических документов, шаблоны для повторного использования.

## Содержание
- [`roles.md`](roles.md) — роли, владельцы и ответственности команды проекта (Product Owner, Code Agent, Prompt Owner).
- [`naming-convention.md`](naming-convention.md) — стандарт именования файлов документации (ISO 8601, типы документов, семантическое версионирование).
- [`embedding-model.md`](embedding-model.md) — стандарт модели эмбеддингов (`BAAI/bge-m3`, критерии замены).
- [`export-markup.md`](export-markup.md) — единая схема разметки результата ИИ-анализа ТЗ для форматов `.xlsx` / `.docx` / `.md` (issue [#79](https://github.com/G-Ivan-A/clarify-engine-ai/issues/79)).
- [`llm-behavior.md`](llm-behavior.md) — стандарт параметров декодирования LLM (`temperature`, `top_p`, `seed`, `max_tokens`) и аудит-логирование (BL-22, issue [#101](https://github.com/G-Ivan-A/clarify-engine-ai/issues/101)).
- [`templates/analysis-template.md`](templates/analysis-template.md) — шаблон для аналитических отчётов и ревью.
- [`templates/decision-template.md`](templates/decision-template.md) — шаблон для документов с решениями вне ADR.

## Принципы
- Стандарты должны быть применимы ко всем документам в [`docs/analysis/`](../analysis/) и, по возможности, к ADR в [`docs/ADR/`](../ADR/).
- Изменения стандартов фиксируются увеличением версии в имени файла стандарта (например, `naming-convention_v2.md`) и сопровождаются заметкой в `CHANGELOG.md`.
- Шаблоны лежат в подкаталоге `templates/`, чтобы их было удобно копировать в `docs/analysis/`.
