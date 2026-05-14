# mango-tz-ai-analyzer
AI-powered tool for automated analysis of tender requirements (TZ) using RAG architecture. Classifies requirements as Yes/No/Partial/ND with citations to documentation.

## 👥 Команда проекта

| Роль | Имя | GitHub | Ответственность |
|------|-----|--------|-----------------|
| **Product Owner** | Ivan Gulienko | [@G-Ivan-A](https://github.com/G-Ivan-A) | Стратегия, концепция, приёмка MVP, **коммит PR** |
| **Code Agent** | Konstantin Diachenko | [@konard](https://github.com/konard) | Генерация кода по Issues |
| **Prompt Owner** | Ivan Gulienko | [@G-Ivan-A](https://github.com/G-Ivan-A) | Промпты, валидация качества |

Полные обязанности и матрица ответственности — в [`docs/standards/roles.md`](docs/standards/roles.md).

## 📄 Документация
- [Концепция внедрения ИИ-анализатора (MVP)](docs/CONCEPT.md) — единый источник истины по архитектуре, требованиям, рискам и плану внедрения.
- [Архитектурные решения (ADR)](docs/ADR/) — журнал ключевых архитектурных решений ([ADR-001: RAG Architecture](docs/ADR/001-rag-architecture.md)).
- [Аналитические отчёты](docs/analysis/) — ревью концепции, код-аудиты, рекомендации команды.
- [Аудиты](docs/audit/) — реестр технических аудитов ([маскирование данных](docs/audit/data-masking_v1.md)).
- [Стандарты и шаблоны](docs/standards/) — [роли команды](docs/standards/roles.md), [конвенция именования](docs/standards/naming-convention.md), [стандарт модели эмбеддингов](docs/standards/embedding-model.md) и шаблоны документов.
- [Runbooks](docs/runbooks/) — эксплуатационные инструкции (наполнение с этапа «Пилот»).

### Настройка облачной среды
Для установки зависимостей в средах с ограниченным дисковым пространством:
1. **Очистка кэша:** `pip cache purge && rm -rf ~/.cache/pip`
2. **Установка без кэша:** `pip install --no-cache-dir -r requirements.txt`
3. **При нехватке места:** Используйте CPU-версию torch: `pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu`
