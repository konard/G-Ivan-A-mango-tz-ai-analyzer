# DEV_NOTES — issue #73 (RAG-пайплайн)

Цель PR — устранить три разрыва между индексатором и рантайм-RAG, описанные в
[issue #73](https://github.com/G-Ivan-A/clarify-engine-ai/issues/73):

1. UI и retriever читали жёстко прошитый путь `knowledge_base/vector_store`,
   тогда как индексатор пишет в `./chroma_data`.
2. ChromaDB применял встроенную 384-мерную модель к коллекции, построенной на
   1024-мерной `BAAI/bge-m3`.
3. `src/llm/client.py` экспортировал только `classify_requirement()` со строгим
   `json_object` и не подходил для свободного RAG-ответа.

## 1. Изменённые файлы

| Путь | Что изменено |
|------|--------------|
| `src/rag/retriever.py` | Добавлены `resolve_vector_store_path()`, `resolve_collection_name()`, `resolve_embedding_model_name()`, `load_embedding_config()` и класс `ChromaRetriever` (см. §2.1). |
| `src/rag/__init__.py` | Реэкспорт нового API. |
| `src/llm/client.py` | Новый публичный метод `LLMClient.generate_rag_response()` + цепочка `_call_gigachat_rag` → `_call_openrouter_rag` → `_call_ollama_rag` с OAuth2 для GigaChat (см. §2.2). |
| `src/ui/app.py` | Полностью переписан: вместо хардкоженного пути `knowledge_base/vector_store` использует `ChromaRetriever.from_config(...)`; вместо ручного `_call_deepseek/_call_gigachat` — `LLMClient.generate_rag_response()`. Источник (`source`, `chunk_idx`) и similarity пробрасываются в UI. |
| `.env.example` | Добавлены `GIGACHAT_CLIENT_ID`, `GIGACHAT_CLIENT_SECRET`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`. |
| `tests/test_rag_path_resolution.py` | Новые unit-тесты для path-resolution + `ChromaRetriever` (использует `query_embeddings`, не `query_texts`). |
| `tests/test_rag_response.py` | Новые unit-тесты для `generate_rag_response` (порядок цепочки, fallback, ошибка при всех падениях, конфиг-проброс). |
| `docs/DEV_NOTES.md` | Этот файл. |

`knowledge_base/indexing/build_index.py`, `configs/embedding_config.yaml`,
`configs/llm_config.yaml` и существующий `classify_requirement()` не менялись
(см. STRICT CONSTRAINTS в issue).

## 2. Ключевые изменения

### 2.1. Размерность эмбеддингов и путь к БД

`ChromaRetriever` инициализирует `SentenceTransformer(model_name)` (по умолчанию
`BAAI/bge-m3`, 1024-dim) и **сам кодирует запрос** перед обращением к ChromaDB:

```python
class ChromaRetriever:
    def search(self, query: str, top_k: int = DEFAULT_TOP_K):
        embedding = self.embed_query(query)        # 1024-dim, normalized
        raw = collection.query(
            query_embeddings=[embedding],          # НЕ query_texts!
            n_results=max(1, int(top_k)),
            include=["documents", "metadatas", "distances"],
        )
        ...
```

Путь к векторной БД резолвится в одной точке:

```python
def resolve_vector_store_path(config, *, project_root=None) -> Path:
    raw = (config.get("vector_store") or {}).get("persist_directory")
    candidate = Path(raw) if raw else Path("./chroma_data")  # fallback
    if not candidate.is_absolute() and project_root is not None:
        candidate = (project_root / candidate).resolve()
    return candidate
```

UI вызывает `ChromaRetriever.from_config(... project_root=PROJECT_ROOT)` — то
есть путь `./chroma_data` из `configs/embedding_config.yaml` теперь
указывает на ту же директорию, в которую пишет индексатор.

### 2.2. Цепочка реальных LLM-подключений

В `src/llm/client.py` (BL-42, issue #170) контрактная цепочка чата читается из
конфига `configs/llm_config.yaml` (`ui.chat_fallback_providers`) через
`LLMClient._chat_fallback_chain()` — никакого hardcoded `RAG_FALLBACK_CHAIN`
больше нет (Pre-deploy Invariant #5). Дефолт для тестов без конфига:

```python
DEFAULT_CHAT_FALLBACK_CHAIN = ("gigachat", "ollama")
RAG_FALLBACK_CHAIN = DEFAULT_CHAT_FALLBACK_CHAIN  # backward-compatible alias
```

и публичный метод `LLMClient.generate_rag_response(system_prompt, user_prompt)`:

```python
def generate_rag_response(self, system_prompt, user_prompt):
    chat_chain = self._chat_fallback_chain()  # read from YAML
    last_error = None
    for name in chat_chain:
        caller = rag_callers[name]
        try:
            return caller(system_prompt, user_prompt, providers.get(name, {}))
        except Exception as exc:
            logger.warning("RAG provider %s failed (%s); trying next provider.", name, exc)
            last_error = exc
    raise LLMError(f"All RAG providers failed ({' → '.join(chat_chain)}). Last error: {last_error}")
```

Метод **не** использует `response_format: json_object` и **не** валидирует
ответ по JSON-схеме — это критично для свободного текста и Markdown.

#### GigaChat (приоритет 1, OAuth2)

`_gigachat_access_token()`:

1. Берёт `GIGACHAT_CLIENT_ID` + `GIGACHAT_CLIENT_SECRET` из `.env`
   (либо предсобранный `GIGACHAT_AUTH` — для обратной совместимости).
2. Base64-кодирует `client_id:client_secret`, шлёт `POST` на
   `https://ngw.devices.sberbank.ru:9443/api/v2/oauth` со `scope=GIGACHAT_API_PERS`.
3. Возвращает `access_token`.

`_call_gigachat_rag()` далее обращается к
`https://gigachat.devices.sberbank.ru/api/v1/chat/completions`.
SSL-верификация **включена по умолчанию**; для корпоративных сетей можно
точечно отключить через `providers.gigachat.verify_ssl: false` в
`configs/llm_config.yaml` (глобально SSL не отключается, см. STRICT
CONSTRAINTS).

Ошибки `403/429/SSLError/ConnectionError/Timeout` — всё это `RuntimeError` для
оркестратора, который логирует `WARNING` и идёт к следующему провайдеру.

#### OpenRouter (приоритет 2)

OpenAI-совместимый endpoint `https://openrouter.ai/api/v1/chat/completions`.
Ключ — `OPENROUTER_API_KEY` (`.env`). Модель по умолчанию —
`deepseek/deepseek-r1:free`; можно переопределить через
`providers.openrouter.model` в `configs/llm_config.yaml`.

#### Ollama (приоритет 3, локальный fallback)

`http://localhost:11434/v1/chat/completions` (OpenAI-режим). Ключ не нужен.
Модель — `qwen2.5:7b` (или то, что задано через `OLLAMA_MODEL`). При
`ConnectionError` (Ollama не запущен) логируется понятное предупреждение и
цепочка завершается с сообщением «All RAG providers failed».

## 3. Инструкция для проверки

```bash
# 1. Поставить зависимости (включая torch CPU для sentence-transformers).
pip install -r requirements.txt
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2. Скопировать .env.example в .env и заполнить ключи (минимум один из:
#    GIGACHAT_CLIENT_ID/SECRET, OPENROUTER_API_KEY, или запустить Ollama).
cp .env.example .env

# 3. Построить индекс (если коллекция ещё не собрана):
python knowledge_base/indexing/build_index.py
# В логах должны появиться строки вида:
#   {"msg":"KB indexing finished (chunks=...,collection=clarify_engine_kb)"}
# В корне репозитория появится директория ./chroma_data.

# 4. Запустить UI:
streamlit run src/ui/app.py
# В сайдбаре должно быть видно:
#   Vector store: .../chroma_data
#   Collection:   clarify_engine_kb
#   Embedding model: BAAI/bge-m3
#   LLM fallback chain: GigaChat → OpenRouter → Ollama

# 5. Прогнать тесты:
pytest tests/test_rag_path_resolution.py tests/test_rag_response.py -v
# Ожидается: 17 passed.

# Полный прогон:
pytest tests/ -v
# Ожидается: 80 passed, 5 skipped (skip-ы зависят от наличия pandas/openpyxl).
```

При успешном RAG-запросе в Streamlit-логах появится либо `INFO` без warning'ов
(GigaChat ответил), либо `WARNING: RAG provider gigachat failed (...); trying
next provider.` с последующим успехом OpenRouter или Ollama.

## 4. Известные ограничения

- **GigaChat access_token** живёт ограниченное время (≈30 минут). Текущая
  реализация запрашивает токен заново на каждый RAG-вызов — это нагружает
  OAuth2-эндпоинт, но не требует кеширования между процессами. Для
  высоконагруженной продакшен-эксплуатации логичен LRU-кеш с TTL — выносится
  в отдельную задачу.
- **Корпоративные SSL-прокси**: если в сети развёрнут MITM-прокси без
  доверенного сертификата, GigaChat-вызовы упадут на SSL-ошибке. Для
  локального обхода добавлен ключ `providers.gigachat.verify_ssl: false`,
  но включать его в продакшене не рекомендуется.
- **Ollama** обязателен только как последний fallback; если установлен —
  убедитесь, что модель загружена (`ollama pull qwen2.5:7b`) и сервис
  запущен (`ollama serve`).
- Метод `generate_rag_response()` **не** применяет
  `mask_text`/`mask_context_chunks` — маскирование уже выполняется на стороне
  индексирующего и UI-слоя, а строгий JSON-режим, который форсит масштабное
  маскирование в `classify_requirement`, для свободного RAG-ответа отключён
  намеренно (issue #73).
