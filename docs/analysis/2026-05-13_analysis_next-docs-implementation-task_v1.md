# ⚠️ WARNING: ANALYTICAL DOCUMENT ONLY

**Этот файл содержит АНАЛИТИЧЕСКИЕ РЕКОМЕНДАЦИИ, а не задачи для выполнения.**

## ❌ НЕ ИСПОЛЬЗОВАТЬ для генерации кода
- Это документ анализа/планирования
- Реальные задачи находятся в **GitHub Issues** репозитория
- Code Agent должен выполнять ТОЛЬКО задачи из вкладки Issues

## ✅ Источник истины для Code Agent
- GitHub Issues: https://github.com/G-Ivan-A/clarify-engine-ai/issues
- Product Owner: @G-Ivan-A создаёт и назначает задачи
- Code Agent: @konard выполняет ТОЛЬКО назначенные Issues

---

# Оригинальное содержание файла ниже

# Анализ следующей приоритетной задачи по документации

## Метаданные
- **Дата:** 2026-05-13
- **Версия:** v1
- **Автор:** Codex AI issue solver
- **Статус:** Draft
- **Связанные документы:**
  - [`docs/audit/2026-05-12_repository-consistency_audit_v1.md`](../audit/2026-05-12_repository-consistency_audit_v1.md)
  - [`docs/analysis/2026-05-12_review_mvp-context_v1.md`](2026-05-12_review_mvp-context_v1.md)
  - [`docs/CONCEPT.md`](../CONCEPT.md)
  - [`docs/audit/data-masking_v1.md`](../audit/data-masking_v1.md)

---

## 1. Понимание контекста

Issue #23 требует сформулировать текст следующей приоритетной задачи на реализацию: внести изменения и дополнения в документацию репозитория, включая код в документации, на основе актуального аудита репозитория и ревью концепции.

Исходный аудит дал verdict **Conditional Approve**: критических блокеров нет, но условия снятия Conditional завязаны на рекомендации #1-#7. Часть из них уже закрыта побочными правками аудита (`CHANGELOG.md`, дубликат `PyYAML`), поэтому следующая задача должна сфокусироваться на оставшихся пробелах, которые одновременно улучшают документацию, тестируемость и трассируемость требований.

## 2. Анализ текущего состояния

Изучены:
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md`, разделы 7-9.
- `docs/analysis/2026-05-12_review_mvp-context_v1.md`, рекомендации и открытые вопросы.
- `docs/CONCEPT.md`, разделы 3-6.
- текущая структура `src/`, `tests/`, `configs/`, `docs/`.

Ключевые факты:
- `CHANGELOG.md` уже содержит MVP baseline, поэтому рекомендация аудита #1 не должна становиться отдельной новой задачей.
- Основной риск из раздела 9.1 аудита: RAG context пока не маскируется перед отправкой в LLM.
- Маскирование реализовано внутри `src/llm/client.py`, но аудит и концепция ожидают отдельный, документируемый блок маскирования.
- `docs/audit/data-masking_v1.md` описывает тест-кейсы для email, телефона, IP и internal domain, но тестовое покрытие явно проверяет только email и телефон.
- Валидация JSON реализована в `src/llm/client.py`, но отдельный модуль/контракт валидатора не выделен.
- Метрики F1 и benchmark важны, но зависят от качества stub/LLM-данных и лучше идут следующим инкрементом после закрытия риска утечки.

## 3. Рекомендация

Следующая приоритетная задача должна объединить рекомендации аудита #2, #3, #4 и #7:

1. выделить маскирование и валидацию LLM-ответа в отдельные документируемые модули;
2. распространить маскирование на RAG context;
3. добавить тесты, подтверждающие отсутствие утечек для всех паттернов из `configs/masking_rules.yaml`;
4. обновить документацию так, чтобы фактический код соответствовал концепции, аудиту маскирования и аудиту репозитория.

Это лучший следующий шаг, потому что он закрывает наиболее конкретный риск из аудита: потенциальную утечку чувствительных данных через `context_chunks`.

## 4. Готовый текст нового issue

### Title

```text
Refactor LLM masking/validation modules and document context masking guarantees
```

### Body

```markdown
## Цель

Снять ключевой риск из `docs/audit/2026-05-12_repository-consistency_audit_v1.md`: чувствительные данные сейчас маскируются в тексте требования, но RAG context (`context_chunks`) может уйти в LLM без маскирования. Заодно выровнять код с документацией: концепция и аудит маскирования описывают маскирование и JSON-валидацию как отдельные контролируемые блоки, а сейчас они находятся внутри `src/llm/client.py`.

## Контекст

Источник задачи:
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md`, рекомендации #2, #3, #4, #7.
- `docs/audit/2026-05-12_repository-consistency_audit_v1.md`, раздел 9.1, риск 1: RAG context не маскируется.
- `docs/audit/data-masking_v1.md`, чек-лист и тест-кейсы маскирования.
- `docs/CONCEPT.md`, разделы 3 и 6: mandatory masking, validated JSON, mitigation of data leakage.

## Задача

1. Вынести маскирование из `src/llm/client.py` в `src/llm/masking.py`.
   - Сохранить публичную совместимость: `mask_text` должен оставаться доступен для существующих импортов из `src.llm.client`, если такие импорты уже используются.
   - Использовать текущий `configs/masking_rules.yaml` без изменения формата конфига.

2. Вынести JSON extraction/validation из `src/llm/client.py` в `src/llm/validator.py`.
   - Сохранить текущие правила: категории `Да` / `Нет` / `Частично` / `НД`, confidence `0..1`, обязательные citations для non-`НД`.
   - Не менять wire-format ответа LLM.

3. Маскировать RAG context перед отправкой в LLM.
   - Маскирование должно применяться к `req_text` и к каждому элементу `context_chunks`.
   - В LLM prompt и provider payload не должны попадать email, RU phone, IP address, internal domain из правил маскирования.

4. Добавить тестовое покрытие.
   - `tests/test_masking.py`: email, RU phone, IP address, internal domain.
   - Тест на `LLMClient.classify_requirement`, подтверждающий, что provider получает уже замаскированный requirement и context.
   - Регрессионный тест на JSON validation/extraction после выноса в `validator.py`.

5. Обновить документацию.
   - `docs/audit/data-masking_v1.md`: отметить, какие пункты чек-листа реализованы, и добавить ссылку на новые тесты.
   - `docs/audit/2026-05-12_repository-consistency_audit_v1.md`: добавить короткую v1.1/history note или follow-up note о закрытии рекомендаций #2, #3, #4, #7, если команда допускает обновление аудита; иначе добавить отдельный analysis-note в `docs/analysis/`.
   - `docs/CONCEPT.md` или ADR-001: уточнить, что маскирование применяется и к требованию, и к RAG context перед LLM call.

## Acceptance Criteria

- [ ] `src/llm/masking.py` существует и содержит основную реализацию маскирования.
- [ ] `src/llm/validator.py` существует и содержит extraction/validation LLM JSON payload.
- [ ] `src/llm/client.py` использует новые модули и не содержит дублирующую реализацию маскирования/валидации.
- [ ] `classify_requirement` маскирует both requirement text and RAG context before provider calls.
- [ ] Тесты покрывают все паттерны из `configs/masking_rules.yaml`: email, RU phone, IP address, internal domain.
- [ ] Есть тест, который падает без маскирования `context_chunks`.
- [ ] `pytest tests/` проходит локально.
- [ ] Документация обновлена и явно фиксирует гарантию: no raw sensitive data in requirement or context payload sent to LLM.

## Out of Scope

- Реализация полноценной индексации ChromaDB.
- Расчет F1 на `test_data/gold_standard.json`.
- Benchmark `≤15 мин / 50 требований`.
- Изменение состава LLM-провайдеров.
- Изменение формата экспортируемого Excel.

## Проверка

Перед PR:

```bash
pytest tests/
```

Дополнительно вручную проверить diff по `src/llm/client.py`, чтобы provider payload формировался только после маскирования requirement и context.
```

## 5. Обоснование приоритета

Эта задача должна идти раньше F1/benchmark-инкрементов, потому что она закрывает риск безопасности и одновременно делает архитектуру ближе к документированной концепции. После нее будет проще добавлять quality evaluation и session audit, так как границы LLM-клиента, валидатора и маскирования станут явными.

## 6. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| v1 | 2026-05-13 | Сформулирован текст следующей приоритетной задачи на основе аудита репозитория и ревью концепции. |
