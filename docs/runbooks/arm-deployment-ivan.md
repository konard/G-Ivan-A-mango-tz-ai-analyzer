# ARM Deployment Runbook for Ivan Gulienko

Инструкция описывает установку и отладку `clarify-engine-ai` на АРМ Ивана Гулиенко. Целевая среда: Windows 10/11 с русской локалью, Windows CMD (`cmd.exe`), Python 3.14 через `py` launcher, CPU-only Ollama и рабочий каталог `C:\Projects\clarify-engine-ai`.

## 1. Предварительные требования

Проверьте, что установлены Git for Windows, Python 3.14, Ollama for Windows и доступ к GitHub-репозиторию. Все команды ниже выполняются только в Windows CMD, не в PowerShell, WSL или Git Bash.

```cmd
git --version
```

```cmd
py -3.14 --version
```

```cmd
ollama --version
```

Минимально ожидаемые ресурсы для CPU-only запуска: 16 GiB RAM, 6 GiB свободного места под модель `qwen2.5:7b`, стабильная сеть для первичного скачивания зависимостей и модели. Первый LLM-запрос через Ollama может идти 60-90 секунд.

Создайте рабочий каталог:

```cmd
mkdir C:\Projects
```

Если CMD показывает кириллицу некорректно, переключите активную консоль в UTF-8 перед запуском Python-команд:

```cmd
chcp 65001
```

Файлы `.env`, `.yaml` и `.md` сохраняйте как UTF-8 без BOM. Это снижает риск `UnicodeDecodeError` на Windows с системной кодировкой cp1251.

## 2. Сценарий А: чистая установка

Клонируйте репозиторий:

```cmd
cd /d C:\Projects && git clone https://github.com/G-Ivan-A/clarify-engine-ai.git && cd /d C:\Projects\clarify-engine-ai
```

Создайте и активируйте виртуальное окружение:

```cmd
py -3.14 -m venv venv
```

```cmd
venv\Scripts\activate
```

Обновите базовые инструменты установки:

```cmd
py -m pip install --upgrade pip setuptools wheel
```

Установите зависимости проекта:

```cmd
py -m pip install --no-cache-dir -r requirements.txt
```

Для CPU-only среды дополнительно закрепите CPU-сборку PyTorch и наличие `torchvision`:

```cmd
py -m pip install --no-cache-dir torch torchvision>=0.18.0 --index-url https://download.pytorch.org/whl/cpu
```

Создайте `.env` из примера:

```cmd
copy .env.example .env
```

Откройте `.env` в редакторе и заполните доступные ключи. Для локального fallback оставьте или добавьте:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=180
```

Запустите Ollama daemon в отдельном окне CMD и оставьте это окно открытым:

```cmd
ollama serve
```

В основном окне CMD скачайте модель:

```cmd
ollama pull qwen2.5:7b
```

Прогрейте модель перед первым UI-запросом:

```cmd
ollama run qwen2.5:7b "Ответь одним словом: готов"
```

Проверьте Ollama API через `curl`:

```cmd
curl http://localhost:11434/api/tags
```

Если планируется запуск Streamlit UI, задайте `PYTHONPATH` в текущей CMD-сессии:

```cmd
set PYTHONPATH=C:\Projects\clarify-engine-ai
```

Проверьте импорт проекта:

```cmd
py -c "import src; print('OK')"
```

Соберите индекс базы знаний один раз после установки или после изменения `knowledge_base/`:

```cmd
py knowledge_base\indexing\build_index.py
```

Запустите UI:

```cmd
streamlit run src/ui/app.py
```

Откройте адрес, который покажет Streamlit, обычно `http://localhost:8501`. В режиме "Анализ ТЗ" загрузите тестовый файл из `test_data`, запустите анализ и скачайте отчет. В режиме "Консультация" задайте короткий вопрос по базе знаний и дождитесь ответа. На CPU-only Ollama первый ответ может занимать до 90 секунд.

## 3. Сценарий Б: запуск после перезагрузки

Откройте первое окно CMD и запустите Ollama:

```cmd
ollama serve
```

Откройте второе окно CMD, активируйте проект и окружение:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate
```

Задайте переменные для текущей сессии:

```cmd
set PYTHONPATH=C:\Projects\clarify-engine-ai
```

```cmd
set OLLAMA_TIMEOUT=180
```

Прогрейте модель:

```cmd
ollama run qwen2.5:7b "Готов"
```

Запустите Streamlit:

```cmd
streamlit run src/ui/app.py
```

## 4. Конфигурация под АРМ

Основные файлы конфигурации:

| Файл | Что проверять |
| --- | --- |
| `.env` | `GIGACHAT_CLIENT_ID`, `GIGACHAT_CLIENT_SECRET`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` |
| `configs/llm_config.yaml` | `pipeline.fallback_providers`, `ui.chat_fallback_providers`, `providers.ollama.timeout_seconds` |
| `configs/ui_config.yaml` | `ui.debug_error_details` для расширенной диагностики в UI |
| `configs/embedding_config.yaml` | `chunk_size` и `chunk_overlap`; после изменения нужна переиндексация |

Для CPU-only Ollama держите timeout не ниже 180 секунд:

```yaml
providers:
  ollama:
    model: "${OLLAMA_MODEL:qwen2.5:7b}"
    base_url: "${OLLAMA_BASE_URL:http://localhost:11434}"
    timeout_seconds: "${OLLAMA_TIMEOUT:180}"
```

Постоянные переменные можно записать через `setx`, но они появятся только в новых окнах CMD:

```cmd
setx OLLAMA_BASE_URL "http://localhost:11434"
```

```cmd
setx OLLAMA_MODEL "qwen2.5:7b"
```

```cmd
setx OLLAMA_TIMEOUT "180"
```

## 5. Проверка установки

Быстрая проверка импортов:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && set PYTHONPATH=C:\Projects\clarify-engine-ai && py -c "import src; import yaml; print('OK')"
```

Проверка Ollama:

```cmd
curl http://localhost:11434/api/tags
```

Минимальный CLI smoke-test на тестовом ТЗ:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && set PYTHONPATH=C:\Projects\clarify-engine-ai && py -m src.pipeline --input test_data\sample_tz.xlsx --output output\sample_tz_report.xlsx
```

UI smoke-test:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && set PYTHONPATH=C:\Projects\clarify-engine-ai && streamlit run src/ui/app.py
```

Ожидаемый результат: Streamlit открывается без `ModuleNotFoundError`, режимы "Анализ ТЗ" и "Консультация" доступны, отчет скачивается через кнопку выгрузки, при ошибке появляется блок с причиной и кнопкой "📥 Скачать логи".

## 6. Сценарий В: ошибка в UI

Если UI показывает "Не удалось получить ответ", не перезапускайте все сразу. Сначала скачайте диагностический файл через кнопку "📥 Скачать логи" в блоке ошибки. Этот файл содержит маскированное описание ошибки, рекомендации и `run_id`.

Чтобы UI показывал расширенную подсказку по исправлению, включите debug-детали:

```yaml
ui:
  debug_error_details: true
```

Файл: `configs/ui_config.yaml`. После изменения сохраните файл как UTF-8 без BOM и перезапустите Streamlit.

Где смотреть дополнительные следы:

| Путь | Что внутри |
| --- | --- |
| `logs/pipeline.jsonl` | JSON-события pipeline с `run_id` и ошибками по требованиям |
| `logs/parser.log` | события парсинга входных файлов |
| `chroma_data/` | локальные данные ChromaDB, если используются старые индексы |
| `knowledge_base/vector_store/` | текущий векторный индекс базы знаний |
| `venv/` | локальное виртуальное окружение; при повреждении его проще пересоздать |

Типовые ошибки:

| Ошибка | Вероятная причина | Действие |
| --- | --- | --- |
| `Read timed out` | CPU-only Ollama не успела ответить или модель не прогрета | Выполнить `ollama run qwen2.5:7b "Готов"` и установить `set OLLAMA_TIMEOUT=180` |
| `UnicodeDecodeError` | YAML или `.env` сохранен в cp1251 или с некорректной BOM | Пересохранить файл как UTF-8 без BOM, затем перезапустить CMD и UI |
| `No module named 'torchvision'` | Не установлена optional vision-зависимость | Выполнить `py -m pip install --no-cache-dir torchvision>=0.18.0` |
| `Connection refused` или `Ollama is unreachable` | Не запущен daemon Ollama | Запустить отдельное окно CMD с `ollama serve` |
| `${VAR:default}` не подставляется как ожидалось | Переменная окружения не задана в текущем окне CMD | Временно задать прямое значение через `set VAR=value` или прописать значение в `.env` |
| `ModuleNotFoundError: src` | Не задан `PYTHONPATH` перед запуском UI | Выполнить `set PYTHONPATH=C:\Projects\clarify-engine-ai` |

Для обращения к разработчику приложите скачанный файл логов, точный текст ошибки из UI, `run_id`, версию Windows и результат команд:

```cmd
py -3.14 --version
```

```cmd
ollama list
```

```cmd
git rev-parse --short HEAD
```

## 7. Сценарий Г: обновление версии

Перед обновлением остановите Streamlit через `Ctrl+C`, но не удаляйте `.env`, `knowledge_base/`, `logs/` и пользовательские входные файлы.

Получите свежие изменения:

```cmd
cd /d C:\Projects\clarify-engine-ai && git pull
```

Активируйте окружение и обновите зависимости:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && py -m pip install --no-cache-dir -r requirements.txt --upgrade
```

Если изменялись `knowledge_base/` или `configs/embedding_config.yaml`, пересоберите индекс:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && set PYTHONPATH=C:\Projects\clarify-engine-ai && py knowledge_base\indexing\build_index.py
```

Проверьте установку после обновления:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && set PYTHONPATH=C:\Projects\clarify-engine-ai && py -m pytest tests\test_arm_deployment_runbook.py -q
```

Запустите UI:

```cmd
cd /d C:\Projects\clarify-engine-ai && venv\Scripts\activate && set PYTHONPATH=C:\Projects\clarify-engine-ai && streamlit run src/ui/app.py
```

## 8. Быстрый чек-лист для Ивана

- Windows CMD открыт через `cmd.exe`.
- Текущий каталог: `C:\Projects\clarify-engine-ai`.
- Виртуальное окружение активно: в начале строки есть `(venv)`.
- Выполнено `set PYTHONPATH=C:\Projects\clarify-engine-ai`.
- Ollama запущена в отдельном окне через `ollama serve`.
- Модель `qwen2.5:7b` есть в `ollama list`.
- `OLLAMA_TIMEOUT=180` задан в текущей сессии или в `.env`.
- UI запущен командой `streamlit run src/ui/app.py`.
- При ошибке скачан файл через "📥 Скачать логи" и сохранен `run_id`.
