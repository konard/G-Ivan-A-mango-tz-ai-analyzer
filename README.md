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

## 📏 Как замерить качество MVP

Для подтверждения NFR-01 (Macro-F1 ≥ 0.70 на gold-standard) используется
CLI-скрипт [`scripts/evaluate/evaluate_quality.py`](scripts/evaluate/evaluate_quality.py).
Скрипт сопоставляет предсказания пайплайна с эталоном из
[`test_data/gold_standard.json`](test_data/gold_standard.json), рассчитывает
Macro-F1 и per-class precision / recall / F1.

```bash
# 1. Запустить пайплайн и получить файл предсказаний (Excel)
python -m src.pipeline \
    --input test_data/sample_tz.xlsx \
    --output output/result_test.xlsx

# 2. Замерить качество относительно эталона
python scripts/evaluate/evaluate_quality.py \
    --gold test_data/gold_standard.json \
    --pred output/result_test.xlsx \
    --output reports/quality_report.json
```

Скрипт поддерживает как Excel-выгрузку пайплайна (колонки `ID` и `[Статус]`),
так и JSON-формат `[{"id": ..., "Статус": "Да"}]`. Полный JSON-отчёт с
матрицей ошибок и детализацией по записям сохраняется при указании
`--output`. См. целевой показатель и Exit Criteria MVP в
[`docs/CONCEPT.md`](docs/CONCEPT.md) §5 и §8.1.1.
