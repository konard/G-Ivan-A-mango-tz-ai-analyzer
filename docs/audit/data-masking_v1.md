# 🔒 Audit: Data Masking Implementation

**Версия:** v1.2 | **Дата:** 2026-05-17 | **Статус:** Approved (Sprint 1 P0)

---

## 1. Scope
Документ описывает план аудита маскирования чувствительных данных при передаче в зарубежные LLM-API (Qwen, DeepSeek). Цель — обеспечить «0 утечек» чувствительных данных в production-сценариях, согласно разделу 6 концепции ([`docs/CONCEPT.md`](../CONCEPT.md)).

Связанные документы:
- [`docs/CONCEPT.md`](../CONCEPT.md) — концепция MVP, раздел 6 (Управление рисками: «Утечка данных»).
- [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — RAG-архитектура и LLM fallback-цепочка.
- [`docs/analysis/2026-05-12_review_mvp-context_v1.md`](../analysis/2026-05-12_review_mvp-context_v1.md) — ревью MVP (SHOULD: аудит маскирования).

## 2. Regex Patterns (`configs/masking_rules.yaml`)
Набор паттернов, которые должны быть зафиксированы в `configs/masking_rules.yaml` и применяться до отправки запросов во внешние LLM-API:

- [ ] Email: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
- [ ] Телефон РФ: `\+7[\s\-]?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}`
- [ ] IP-адреса: `\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b`
- [ ] Внутренние домены: `\b(?:[a-zA-Z0-9-]+\.)?(internal|corp|local)\.[a-z]{2,}\b`

## 3. Test Cases
- [ ] **Тест 1.** Email в требовании → заменён на `[EMAIL]`.
- [ ] **Тест 2.** Телефон РФ в требовании → заменён на `[PHONE]`.
- [ ] **Тест 3.** IP-адрес в требовании → заменён на `[IP]`.
- [ ] **Тест 4.** Внутренний домен в требовании → заменён на `[DOMAIN]`.

Каждый тест-кейс должен быть оформлен как юнит-тест в `tests/test_masking.py` и валидировать вход/выход маскирующего модуля.

## 4. Metrics
- **Цель:** 0 утечек чувствительных данных в production.
- **Мониторинг:** аудит логов на наличие исходных паттернов (раздел 6 концепции).
- **Частота проверки:** при каждом запуске пайплайна с `use_test_data_mode: false`.
- **Триггер инцидента:** найдена хотя бы одна не замаскированная сущность из раздела 2 в исходящем трафике к зарубежным LLM-API.

## 5. Implementation Status
- [x] Regex-паттерны добавлены в `configs/masking_rules.yaml`.
- [x] Модуль `src/llm/masking.py` реализован.
- [x] Юнит-тесты написаны (`tests/test_masking.py`).
- [x] Интеграция в LLM-пайплайн (между подготовкой промпта и вызовом провайдера) завершена.
- [x] RAG context маскируется перед отправкой в LLM (риск 9.1 закрыт; флаг `mask_rag_context: true` в `configs/embedding_config.yaml`, BL-04).
- [x] Log sanitization подключён: `sanitize_log_record()` в `src/llm/masking.py` + `logging.Filter` в `src/pipeline.py` (BL-23, ADR-003 §4.3).
- [x] Аудит логов на утечки добавлен в чек-лист релиза (см. §8 Log sanitization).

## 6. Test Coverage
Все тест-кейсы реализованы в `tests/test_masking.py`:

| Тест | Паттерн | Статус |
|------|---------|--------|
| Тест 1 | Email в требовании → `[EMAIL]` | ✅ |
| Тест 2 | Телефон РФ в требовании → `[PHONE]` | ✅ |
| Тест 3 | IP-адрес в требовании → `[IP]` | ✅ |
| Тест 4 | Внутренний домен в требовании → `[DOMAIN]` | ✅ |
| Тест 5 | Email в context chunk → `[EMAIL]` | ✅ |
| Тест 6 | IP в context chunk → `[IP]` | ✅ |
| Тест 7 | Domain в context chunk → `[DOMAIN]` | ✅ |
| Тест 8 | `test_classify_requirement_masks_requirement_and_context` — полная проверка маскирования требования и контекста | ✅ |
| Тест 9 | `test_classify_requirement_fails_without_context_masking` — регрессионный тест на риск 9.1 | ✅ |

## 6. Open Questions
- Какой формат токенов-заглушек считать каноническим (`[EMAIL]`, `<EMAIL>`, `__EMAIL__`)? — закреплено в `configs/masking_rules.yaml`.
- Нужно ли маскировать ФИО на этапе MVP, или этот класс сущностей покрывается на следующей итерации?
- Будет ли применяться отдельный набор правил для внутренних резидентных LLM (GigaChat, YandexGPT)?

## 7. История изменений
| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-12 | Первая версия аудита маскирования: regex-паттерны, тест-кейсы, метрики, статус реализации. |
| v1.1 | 2026-05-12 | Закрытие риска 9.1: RAG context теперь маскируется перед отправкой в LLM. Добавлены тесты `test_classify_requirement_masks_requirement_and_context` и `test_classify_requirement_fails_without_context_masking` в `tests/test_llm_client.py`. Обновлён раздел Test Coverage. |
| v1.2 | 2026-05-17 | BL-23 (issue #87): добавлен §8 «Log sanitization (FR-08 + RAG-eval)» с привязкой к ADR-003 §4.3 (`sanitize_for_log()`). BL-04: явная ссылка на флаг `mask_rag_context: true` в `configs/embedding_config.yaml` и `generate_rag_response`. Обновлён §5 Implementation Status. |

## 8. Log sanitization (FR-08 + RAG-eval)

Раздел добавлен в версии v1.2 (BL-23, issue #87) и фиксирует контракт
санитайзера для JSON-логов FR-08 и отчётов `evaluate_rag.py`.

### 8.1 Scope
- JSON-логи пайплайна (`src/pipeline.py`) — все записи, проходящие через `_JsonFormatter`.
- Отчёты `evaluate_rag.py` (`reports/rag-*.json`), включая CI-артефакты smoke-job `rag-eval-smoke` (BL-05.1).
- Любые `extra={...}` поля, передаваемые с `requirement_id` / `run_id`.

### 8.2 Контракт `sanitize_log_record(record: dict) -> dict`
- Алиас к `sanitize_for_log()` из [ADR-003 §4.3 Log sanitization](../ADR/003-multi-agent-orchestration-draft.md#43-log-sanitization-manage).
- Применяет regex-маскирование из `configs/masking_rules.yaml` к полям:
  `message`, `payload`, `context`, `answer`, `question`, `requirement_text`,
  `chunks[*].text` (рекурсивно по списку чанков).
- Заменяет значения переменных окружения, помеченных как секреты
  (`*_API_KEY`, `*_TOKEN`, `*_SECRET`), на `***REDACTED***`.
- Усекает поле `payload` (если оно ≥ `N` КБ, по умолчанию 32 КБ) — защита
  от взрыва build-artifacts CI.
- НЕ модифицирует `run_id`, `requirement_id`, `level`, `timestamp`,
  `logger`, `provider`, `classification` (они нужны для трассировки).

### 8.3 Интеграция в код
- Реализация — `src/llm/masking.py::sanitize_log_record`.
- Подключение как `logging.Filter` — `src/pipeline.py::configure_json_logging`
  (фильтр применяется ко всем хендлерам root-логгера).
- Регрессионный тест —
  `tests/test_masking.py::TestLogSanitization::test_log_sanitization_applies_to_evaluate_rag_report`.

### 8.4 Метрики и триггеры инцидента
- **Цель:** 0 совпадений regex чувствительных данных в `reports/rag-*.json`
  и в CI-логах.
- **Триггер инцидента:** в CI-артефакте обнаружена хотя бы одна
  не замаскированная сущность из §2.
- **Чек-лист релиза:** перед публикацией tag'а — прогон `evaluate_rag.py`
  на Golden Set + grep по `reports/` regex'ами из §2 (должно быть 0 совпадений).
