# 🎛️ Standard: LLM Decoding Behavior

**Версия:** 1.0 | **Дата:** 2026-05-17 | **Статус:** Approved

---

## 1. Назначение

Стандарт фиксирует **централизованные параметры декодирования** (`temperature`,
`top_p`, `seed`, `max_tokens`), применяемые ко всем вызовам LLM в `clarify-engine-ai`.
Цель — обеспечить **воспроизводимость** ответов между запусками, **аудируемость**
параметров каждого вызова (FR-08, NFR-06) и **независимость поведения** от
конкретного провайдера.

Стандарт является приложением к [ADR-001](../ADR/001-rag-architecture.md) и
[`docs/CONCEPT.md`](../CONCEPT.md) §6.7 / FR-04 / FR-08. Реализация: задача
**BL-22** ([issue #101](https://github.com/G-Ivan-A/clarify-engine-ai/issues/101),
[issue #87](https://github.com/G-Ivan-A/clarify-engine-ai/issues/87)).

## 2. Single source of truth

| Артефакт | Назначение |
|----------|------------|
| [`configs/llm_config.yaml`](../../configs/llm_config.yaml) — блок `decoding:` | Канонические значения параметров декодирования. **Единственное место**, где они меняются. |
| [`src/llm/client.py`](../../src/llm/client.py) — `LLMClient._merge_decoding()` | Загружает блок и инжектит его в per-provider config на каждом вызове. |
| [`tests/test_decoding_lock.py`](../../tests/test_decoding_lock.py) | Регрессионная защита: блок применяется и побеждает provider-override’ы. |

### 2.1 Контракт значений MVP

```yaml
decoding:
  temperature: 0.1    # детерминизм > креативность
  top_p: 0.9          # отсекаем хвост распределения
  seed: 42            # воспроизводимость на провайдерах, которые поддерживают seed
  max_tokens: 1024    # достаточно для JSON-ответа классификации (FR-04)
```

> **Почему `max_tokens: 1024`, а не 2048.** Промпт `system_classifier_v1.0.md`
> возвращает компактный JSON; 1024 токена — двукратный запас от наблюдаемой
> длины ответа на Golden Set (BL-05). Если в Пилоте появятся ответы у границы,
> поднимаем значение и фиксируем причину в `CHANGELOG.md` (см. §6 этого стандарта).
> Issue #101 приводил `2048` как пример («указано в `decoding:`-блоке»);
> фактический контракт MVP — `1024`.

## 3. Где значения применяются

`LLMClient` мержит блок `decoding:` поверх per-provider config’а перед каждым
вызовом каждого из callers. Параметры **переопределяют** любые значения
температуры/top_p/seed/max_tokens, заданные на уровне провайдера или промпта
(BL-22: prompt overrides запрещены).

| Caller | Где применяется |
|--------|-----------------|
| `_call_deepseek` | classification flow (FR-04) |
| `_call_gigachat` | classification flow (FR-04) |
| `_call_gigachat_rag` | RAG free-text flow (UI Q&A) |
| `_call_openrouter_rag` | RAG free-text flow (fallback chain) |
| `_call_ollama_rag` | RAG free-text flow (local fallback) |
| `_call_stub` | offline тестовый stub (детерминированный ответ; параметры игнорируются) |

## 4. Рекомендуемые значения по провайдерам и режимам

> Колонка «MVP» — закреплённые значения из `configs/llm_config.yaml` (см. §2.1).
> Колонка «Допустимый коридор» — пределы, внутри которых параметры можно
> подкручивать в Пилоте **без** изменения этого стандарта; выход за коридор
> требует ADR.

| Провайдер | Режим | `temperature` | `top_p` | `seed` | `max_tokens` | Примечание |
|-----------|-------|--------------:|--------:|-------:|-------------:|------------|
| **DeepSeek** (`deepseek-chat`) | Classification (FR-04, JSON) | **0.1** | **0.9** | **42** | **1024** | `response_format: json_object` фиксируется в caller’е. `seed` поддерживается. |
| **GigaChat** (`GigaChat-Pro`) | Classification (FR-04) | **0.1** | **0.9** | **42**\* | **1024** | \*GigaChat не гарантирует детерминизм по `seed` — параметр передаётся, но воспроизводимость **best-effort**. |
| **GigaChat** (`GigaChat-Pro`) | RAG free-text | **0.1** | **0.9** | **42**\* | **1024** | Тот же блок; формат ответа не ограничен JSON. |
| **OpenRouter** (`deepseek/deepseek-r1:free`) | RAG free-text (fallback) | **0.1** | **0.9** | **42** | **1024** | OpenAI-compatible payload; `seed` пробрасывается, поддержка зависит от downstream-модели. |
| **Ollama** (`qwen2.5:7b`, локально) | RAG free-text (local fallback) | **0.1** | **0.9** | **42** | **1024** | Для локальной воспроизводимости `seed` рекомендуется задавать всегда. |
| **stub** | offline-тесты | n/a | n/a | n/a | n/a | Ответ детерминирован in-code; параметры декодирования не передаются. |

**Допустимый коридор для Пилота (без ADR):**

| Параметр | Коридор | Когда выходить за рамки |
|----------|---------|--------------------------|
| `temperature` | `[0.0, 0.3]` | Только эксперименты в `experiments/`; для production требуется ADR. |
| `top_p` | `[0.8, 1.0]` | Снижение ниже 0.8 ведёт к обрывам JSON — фиксировать как known issue. |
| `seed` | любое целое ≥ 0 | Менять только если внешний провайдер сменил алгоритм. |
| `max_tokens` | `[512, 4096]` | Подъём выше 4096 — после замера p95-длины ответа на Golden Set. |

## 5. Аудит и логирование (FR-08, NFR-06)

Перед каждым вызовом классификации `LLMClient` логирует применённый блок:

```text
INFO src.llm.client decoding_lock applied: {'temperature': 0.1, 'top_p': 0.9, 'seed': 42, 'max_tokens': 1024}
```

Запись связана с `run_id` через стандартный JSON-логгер (см. FR-08). По логам
аудит может восстановить, **какие именно** параметры повлияли на конкретный
ответ. Если блок `decoding:` в `configs/llm_config.yaml` отсутствует, лог
не пишется и применяются дефолты caller’а — это режим обратной совместимости
для legacy-конфигов.

## 6. Replacement / change criteria

Значения этого стандарта меняются только при выполнении одного из условий:

- Падение качества классификации на Golden Set ниже 70 % F1 при текущих параметрах (NFR-01).
- Систематические обрывы JSON-ответа на длинных требованиях (требует подъёма `max_tokens`).
- Смена провайдера / модели, для которой текущие значения некорректны (например, модель не поддерживает `top_p`).
- Доказанная (на ≥ 2 прогонах Golden Set) воспроизводимость лучше при другом `seed`.

Любое изменение:
1. Обновляет `configs/llm_config.yaml` и этот документ (увеличивая версию в шапке);
2. Фиксируется записью в `CHANGELOG.md` (раздел `[Unreleased]`);
3. Покрывается обновлением `tests/test_decoding_lock.py::test_packaged_llm_config_carries_decoding_block`.

## 7. References

- [`docs/CONCEPT.md`](../CONCEPT.md) — FR-04 (LLM-классификация), FR-08 (логирование), §6.7 (обработка ошибок LLM).
- [`docs/ADR/001-rag-architecture.md`](../ADR/001-rag-architecture.md) — архитектура RAG-пайплайна.
- [`docs/backlog/2026-05-17_backlog_rag-optimization_v1.2.md`](../backlog/2026-05-17_backlog_rag-optimization_v1.2.md) §3 — BL-22.
- [`configs/llm_config.yaml`](../../configs/llm_config.yaml) — блок `decoding:` (SSoT).
- [`src/llm/client.py`](../../src/llm/client.py) — `LLMClient._merge_decoding`, `_decoding_overrides`.
- [`tests/test_decoding_lock.py`](../../tests/test_decoding_lock.py) — регрессионные тесты.

## 8. История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-05-17 | BL-22 (issue #101): первая версия стандарта. Зафиксирован канонический блок `decoding:` (`temperature: 0.1`, `top_p: 0.9`, `seed: 42`, `max_tokens: 1024`), таблица рекомендуемых значений по провайдерам и режимам, обязательное аудит-логирование `decoding_lock applied`. |
