# ADR-002. Расширение схемы экспорта результатов анализа ТЗ

**Status:** Proposed (Post-Pilot)
**Date:** 2026-05-15
**Last Updated:** 2026-05-19 (BL-40: ADR-sync v2.5 — preserved Proposed status, hardened export-markup v1.0 / ADR-008 boundary; see §History)
**Owner:** Product Owner — Ivan Gulienko ([@G-Ivan-A](https://github.com/G-Ivan-A))
**Связанные документы:** [CONCEPT.md §4 FR-06](../CONCEPT.md), [ADR-001](001-rag-architecture.md), [ADR-008](008-data-export.md), [standards/export-markup.md v1.0](../standards/export-markup.md), [`configs/export_config.yaml`](../../configs/export_config.yaml), [issue #48](https://github.com/G-Ivan-A/clarify-engine-ai/issues/48), [issue #79](https://github.com/G-Ivan-A/clarify-engine-ai/issues/79), [issue #146](https://github.com/G-Ivan-A/clarify-engine-ai/issues/146), [issue #166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)

> 🧭 **Канал-разделение (BL-40).** Этот ADR описывает **pipeline-канал**
> экспорта (batch-классификация ТЗ → `.xlsx` / `.docx` / `.md`), контракт
> которого — `EXPORT_SCHEMA_VERSION = "1.0"` (см. `src/exporters/contract.py`).
> **UI-канал** экспорта Streamlit-сессий («📊 Анализ ТЗ» → `.xlsx`,
> «💬 Консультация» → `.md` транскрипт) принят отдельным **[ADR-008](008-data-export.md)
> (Accepted)** и не подпадает под пост-пилотное расширение этого ADR.
> Любое предложенное здесь поле должно явно указывать целевой канал
> и не модифицировать контракт ADR-008 без отдельной ревизии.

---

## Context

В MVP экспорт результатов анализа фиксирует **минимальный набор колонок**
(FR-06), которые являются стабильным пользовательским подмножеством
`ExportRow` из [`standards/export-markup.md`](../standards/export-markup.md):

| Колонка | Назначение |
|--------|-----------|
| `[Статус]` | `Да` / `Нет` / `Частично` / `НД` / `Ошибка` |
| `[Комментарий]` | Обоснование классификации (LLM `reasoning`) |
| `[Confidence]` | Скор уверенности `0.0 – 1.0` |
| `[RunID]` | UUID4 сессии — связь с логами (FR-08) |

Расширенный набор полей (`[Цитаты]`, `[Рекомендация]`, `[Требует ревью]`,
`[Провайдер]`, `[Ошибка]`, диагностические поля) **не входит в MVP-экспорт**
(`src/exporters/excel_exporter.py` эмитирует только четыре MVP-колонки) —
его состав и формат подлежат валидации с БА в ходе Пилота и фиксации в этом
ADR.

BL-27 дополнительно фиксирует форматно-инвариантную строку v1.0 из 7
обязательных полей: `requirement_id`, `requirement_text`, `Ref`, `status`,
`comment`, `confidence`, `run_id`. Эти поля не считаются расширенной схемой:
они являются базовым контрактом трассируемости и round-trip. Версия схемы
закреплена в коде как `EXPORT_SCHEMA_VERSION = "1.0"`
(`src/exporters/contract.py`) и валидируется
[`standards/export-markup.md v1.0`](../standards/export-markup.md) §2/§4/§7;
любая ревизия требует совместного PR на `configs/export_config.yaml`
(`excel_columns` allow-list) и `src/exporters/contract.py`.

## Decision (pending)

Состав расширенной схемы экспорта будет утверждён по итогам Пилота на основе:
1. Обратной связи от 2–3 пилотных БА (см. CONCEPT §8.1.2).
2. Замера F1 / Confidence-калибровки на gold-standard ≥ 50 записей (NFR-01).
3. Анализа сценариев Human-in-the-Loop с inline-редактированием.

Решение будет зафиксировано как новая версия этого ADR (Status: Accepted)
с привязкой к pull request, обновляющему `src/exporters/excel_exporter.py`,
`tests/test_pipeline.py` и CONCEPT.md §4 FR-06.

Обратно-совместимое расширение выполняется только как `schema_version: "1.1"+`
и `additional_columns`. Старые ридеры должны читать семь базовых полей v1.0 и
игнорировать неизвестные дополнительные поля с предупреждением.

## Consequences

- До принятия ADR-002 экспортер эмитирует **только** четыре MVP-колонки
  (`[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]`). Внешние
  интеграции должны полагаться только на этот пользовательский контракт и
  базовые поля трассируемости `requirement_id`, `requirement_text`, `Ref`.
- Любое изменение расширенной схемы оформляется как новая ревизия этого ADR
  через PR в `main` (Product Owner-only коммит).
- Новые колонки добавляются только справа от базовых полей или в
  `additional_columns`; переименование / перестановка семи полей v1.0 является
  breaking change.

## Triggers for Revision

- Завершение Пилота и сбор обратной связи от БА.
- Появление новых требований к аудируемости (например, регуляторных).
- Изменение состава классификации или fallback-цепочки (см. ADR-001).

## Multi-format compatibility (issues #79, #146; V-09 / BL-27)

С переносом мульти-форматного экспорта (`.xlsx` / `.docx` / `.md`) в
MVP-скоуп (CONCEPT.md v2.3 §2.3, §4 FR-06) расширенная схема ADR-002
**ортогональна** новым форматам и должна сохранить совместимость:

- **Контракт MVP неизменен.** Четыре MVP-колонки FR-06
  (`[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]`) остаются
  стабильным контрактом для всех целевых форматов экспорта. Изменение их
  состава, имён или семантики возможно только через новую ревизию ADR-002.
- **Базовая строка v1.0 стабильна.** Семь полей `ExportRow`
  (`requirement_id`, `requirement_text`, `Ref`, `status`, `comment`,
  `confidence`, `run_id`) являются форматом round-trip. `Ref` обязателен для
  каждой строки и не удаляется при расширении.
- **Принцип расширения.** Новые поля, утверждённые по итогам Пилота,
  добавляются:
  - в `.xlsx` / `.docx` / `.md` — **справа** от семи полей v1.0, без
    перестановки;
  - в API / in-memory payload — в `additional_columns`, без модификации
    обязательных полей;
  - версия схемы фиксируется в `schema_version` метаданных отчёта
    (см. [`standards/export-markup.md`](../standards/export-markup.md)
    §2, §4 и §7).
- **Контроль расхождения.** Любая правка `ExportRouter` или адаптеров
  `docx_exporter.py` / `md_exporter.py` (BL-20) должна пройти
  cross-check на соответствие текущему перечню колонок ADR-002 и
  обновить `schema_version`. Расхождение между форматами по составу
  полей запрещено.

Эта секция фиксирует политику до момента, когда ADR-002 перейдёт в
статус `Accepted` и сам определит полный перечень полей для всех
форматов.

## History

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-05-15 | Первая редакция: расширение схемы экспорта зафиксировано как `Proposed (Post-Pilot)`, MVP-контракт — 4 пользовательские колонки FR-06. |
| 1.1 | 2026-05-17 | BL-27: добавлена §«Multi-format compatibility» и обязательная базовая строка `ExportRow` v1.0 (7 полей). |
| 1.2 | 2026-05-19 | BL-40 (issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)): сохранён статус `Proposed (Post-Pilot)`, добавлен явный канал-разделитель (pipeline ADR-002 v1.0 vs UI ADR-008), явная ссылка на `EXPORT_SCHEMA_VERSION = "1.0"` (`src/exporters/contract.py`) и `configs/export_config.yaml`. Кодовые изменения не выполняются. |
