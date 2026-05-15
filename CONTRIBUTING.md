# Contributing — `mango-tz-ai-analyzer`

Этот документ описывает рабочий процесс для всех контрибьюторов проекта (issue #45 — MAY 1). Он намеренно лаконичный: подробные роли и обязанности — в [`docs/standards/roles.md`](docs/standards/roles.md), архитектурные решения — в [`docs/ADR/`](docs/ADR/), требования MVP — в [`docs/CONCEPT.md`](docs/CONCEPT.md).

---

## 1. Definition of Done (DoD)

Pull Request считается готовым к мерджу, когда выполнено всё перечисленное:

- [ ] **Соответствие issue.** Все пункты MUST и применимые SHOULD/MAY из исходного issue реализованы; OUT OF SCOPE не расширен без отдельного согласования с Product Owner.
- [ ] **Тесты.** `python -m pytest tests/ -q` — все тесты проходят локально. Для нового поведения добавлены unit-тесты, для багфикса — регресс-тест.
- [ ] **Соответствие концепции.** Изменения совместимы с актуальной версией [`docs/CONCEPT.md`](docs/CONCEPT.md) (см. FR-01..FR-08 и NFR-01..NFR-09). При расхождении — обновлён CONCEPT.md или открыт ADR.
- [ ] **MVP-контракты не нарушены.** Экспорт сохраняет ровно 4 колонки `[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]` (FR-06). LLM-вызовы остаются последовательными (см. [`docs/ADR/001-rag-architecture.md`](docs/ADR/001-rag-architecture.md)).
- [ ] **Безопасность данных.** Логи и тестовые фикстуры не содержат секретов, ключей API, PII. Маскирование применено для согласованных паттернов (Email/Phone/IP/Domain).
- [ ] **Документация.** Если изменилось пользовательское поведение или конфигурация — обновлены `README.md`, `CHANGELOG.md` (раздел `[Unreleased]`) и при необходимости `docs/`.
- [ ] **Чистый рабочий каталог.** `git status` пуст, все артефакты в коммитах. Сгенерированные файлы (`output/*.xlsx`, `logs/*.jsonl`, `data/chroma/`) не закоммичены.

---

## 2. Матрица команд

Минимальный набор команд, который ожидается от контрибьютора перед открытием PR.

| Шаг | Команда | Когда выполнять |
|------|---------|-----------------|
| Установить зависимости | `pip install --no-cache-dir -r requirements.txt`<br>`pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu` | После клонирования или при изменении `requirements.txt`. |
| Запустить все тесты | `python -m pytest tests/ -q` | Перед каждым `git push`. |
| Запустить отдельный тест | `python -m pytest tests/test_pipeline.py -q` | Точечная отладка. |
| Построить индекс БЗ | `python knowledge_base/indexing/build_index.py` | После изменений в `knowledge_base/` или в `configs/embedding_config.yaml`. |
| Запустить UI | `streamlit run src/app.py` | Ручная проверка UX-сценариев. |
| Оценить качество | `python scripts/evaluate/evaluate_quality.py --pipeline-output output/result.xlsx` | После изменений в промптах, retrieval или LLM-клиенте. |
| Бенчмарк | `python scripts/evaluate/benchmark_pipeline.py --mode stub --count 50` | После изменений в `src/pipeline.py`. |

Опциональные линтеры/типчеки в MVP не обязательны (см. OUT OF SCOPE — Pre-commit hooks). Если используете локально — не коммитьте сторонние конфигурации без обсуждения.

---

## 3. Правила ветвления

Проект использует pull-request-only workflow. Прямые коммиты в `main` запрещены.

### 3.1. Базовая ветка
- Все ветки создаются от актуального `main`.
- Перед открытием PR — `git pull --rebase origin main` (или мердж `main` в ветку), чтобы свести конфликты к минимуму.

### 3.2. Именование веток
Используйте префикс по типу работы и привязку к issue:

```
<type>/issue-<number>-<short-slug>
```

| Префикс | Назначение |
|---------|------------|
| `feat/` | Новая функциональность (`feat/issue-45-mvp-final`). |
| `fix/` | Исправление бага. |
| `docs/` | Только документация (`docs/issue-12-contributing`). |
| `refactor/` | Рефакторинг без изменения поведения. |
| `test/` | Только тесты или тестовые фикстуры. |
| `chore/` | Зависимости, конфиги, служебные изменения. |

Если ветку создаёт автоматизация (например, AI-агент), допускается формат `issue-<number>-<hash>` — он уже соответствует соглашению.

### 3.3. Коммиты
- Используйте [Conventional Commits](https://www.conventionalcommits.org/) в заголовке: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...`.
- Заголовок ≤ 72 символов, в теле — мотивация и контекст («почему», а не «что»).
- Один логический шаг = один коммит. Не сквошьте этапы, имеющие самостоятельную ценность (помогает анализу истории).

### 3.4. Pull Request
- PR открывается **только** против `main`.
- В описании укажите: ссылку на issue, краткое summary, чек-лист DoD, скриншоты (для UI), команды воспроизведения.
- Merge в `main` выполняет **только Product Owner** (см. RACI в [`docs/standards/roles.md`](docs/standards/roles.md)).
- Force-push в `main` запрещён. Force-push в собственную ветку допустим до начала ревью.

### 3.5. Закрытие ветки
После мерджа ветка удаляется (вручную или автоматически GitHub). Локально — `git branch -d <name>` (только если все коммиты в `main`).

---

## 4. Что НЕ нужно делать в MVP

Чтобы избежать неоправданного расширения scope, перечисленное ниже намеренно вынесено за рамки текущей фазы (см. OUT OF SCOPE в issue #45):

- Параллельные вызовы LLM.
- Экспорт в `.docx`.
- Маскирование ФИО.
- Inline-редактирование результатов в Streamlit UI.
- Интеграция с SharePoint и внешними KB-источниками.
- Pre-commit hooks и GitHub Actions CI.

Если возникает потребность — открывайте отдельный issue или ADR, не добавляйте такой код «попутно».

---

## 5. Связанные документы
- [`docs/CONCEPT.md`](docs/CONCEPT.md) — SSoT по требованиям и архитектуре.
- [`docs/standards/roles.md`](docs/standards/roles.md) — роли, RACI, владельцы.
- [`docs/standards/naming-convention.md`](docs/standards/naming-convention.md) — соглашения об именах файлов.
- [`docs/ADR/001-rag-architecture.md`](docs/ADR/001-rag-architecture.md) — почему RAG последовательный, BM25+Dense+RRF.
- [`SECURITY.md`](SECURITY.md) — обработка утечек и контакты PO.
- [`CHANGELOG.md`](CHANGELOG.md) — Keep a Changelog + SemVer.
