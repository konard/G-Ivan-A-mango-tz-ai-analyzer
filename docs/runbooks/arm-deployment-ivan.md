# ARM Deployment Runbook for Ivan Gulienko

Инструкция описывает установку и отладку `clarify-engine-ai` на АРМ Ивана Гулиенко. Целевая среда: Windows 10/11 с русской локалью, Windows CMD (`cmd.exe`), Python 3.14 через `py` launcher, CPU-only Ollama и рабочий каталог `C:\Projects\clarify-engine-ai`.

## 0. Quick-start через Installer L1

Для первой установки вместо ручного выполнения команд из раздела 2 можно
запустить wizard из корня проекта:

```cmd
scripts\install\clarify-setup.cmd
```

Wizard выполняет шаги `[1/8]..[8/8]`: проверяет среду, создаёт runtime
директории, поднимает `venv`, создаёт `.env` из `.env.example`, проверяет
Ollama и модель `qwen2.5:7b`, запускает smoke import, создаёт ярлыки и
показывает итоговый URL `http://localhost:8501`. Повторный запуск
идемпотентен: существующие `.env`, `logs/`, `chroma_data/`,
`data/incoming/` и `data/output/` не перезаписываются.

Если рядом с проектом найден `.env.txt`, но отсутствует `.env`, wizard
останавливается и просит вручную выполнить:

```cmd
ren .env.txt .env
```

Загрузка модели через `ollama pull qwen2.5:7b` выполняется только после
явного подтверждения. Лог установки пишется в `logs\install.jsonl`; секреты
из `.env` туда не попадают. Для проверки без тяжёлых команд доступен режим:

```cmd
scripts\install\clarify-setup.cmd --dry-run
```

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

Минимально ожидаемые ресурсы для CPU-only запуска: 16 GiB RAM, 6 GiB свободного места под модель `qwen2.5:7b`, стабильная сеть для первичного скачивания зависимостей и модели. Первый LLM-запрос через Ollama может идти 60–90 секунд (BL-55, issue #199): это разовая плата за подъём модели в память, последующие запросы — 5–15 секунд. Спиннер UI и кнопка «🔥 Прогреть модель» в сайдбаре синхронизированы с этим текстом.

Создайте рабочий каталог:

```cmd
mkdir C:\Projects
```

Если CMD показывает кириллицу некорректно, переключите активную консоль в UTF-8 перед запуском Python-команд:

```cmd
chcp 65001
```

Файлы `.env`, `.yaml` и `.md` сохраняйте как UTF-8 без BOM. Это снижает риск `UnicodeDecodeError` на Windows с системной кодировкой cp1251.

> ⚠️ **Notepad на Windows скрывает расширение.** Если «Сохранить как» не переключить в `All Files (*.*)`, файл уходит на диск как `.env.txt`. С BL-50 (issue #194) startup-guard скажет вам об этом автоматически: при старте `streamlit run src/ui/app.py` или `python -m src.pipeline` появится сообщение «Обнаружен файл .env.txt» с готовой командой `ren .env.txt .env`. Никакого silent rename — переименование подтверждаете вы сами.

### 1.4a. Добавьте Ollama в PATH (BL-51)

Инсталлятор Ollama for Windows кладёт `ollama.exe` в `%LOCALAPPDATA%\Programs\Ollama`, но **не добавляет этот путь в системный PATH**. Без правки PATH команды `ollama serve`, `ollama pull qwen2.5:7b` и `ollama --version` в свежей CMD-сессии падают с `'ollama' is not recognized as an internal or external command`.

Добавьте Ollama в пользовательский PATH одной командой:

```cmd
setx PATH "%PATH%;%LOCALAPPDATA%\Programs\Ollama"
```

> ⚠️ **`setx` не меняет PATH в уже открытом окне CMD.** **Закройте текущее окно CMD и откройте новое** — иначе `ollama --version` всё ещё будет ошибкой. Это поведение Windows, а не дефект Ollama.

Проверьте, что `ollama` доступна без полного пути:

```cmd
where ollama
```

Ожидаемый вывод — строка вида `C:\Users\<you>\AppData\Local\Programs\Ollama\ollama.exe`. Если `where` отвечает `INFO: Could not find files for the given pattern(s)`, повторите `setx` или перезагрузите Windows.

`OllamaProvider` со стороны Python тоже сам определяет путь через `shutil.which("ollama")` с fallback на `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` и `C:\Program Files\Ollama\ollama.exe` (см. `src/llm/client.py::_resolve_ollama_executable`). Найденный путь логируется один раз при старте провайдера. Если ни PATH, ни стандартные пути не сработали, в логе появится подсказка с командой `setx PATH ...` — это и есть BL-51 guard.

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

> 💡 С BL-50 (issue #194) этот шаг можно пропустить: если `.env` отсутствует, startup-guard в `streamlit run src/ui/app.py` / `python -m src.pipeline` сам скопирует `.env.example` в `.env` и оставит вам подсказку в логе. Шаг с `copy` остаётся актуальным для тех, кто хочет сразу открыть файл в редакторе и заполнить ключи.

Откройте `.env` в редакторе и заполните доступные ключи. Для локального fallback оставьте или добавьте:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=180
```

> ⚠️ **BL-53 (issue #198): после правок `.env` или `configs/*.yaml` нужен полный рестарт Streamlit.** Нажмите `Ctrl+C` в окне, где запущен UI, снова выполните `streamlit run src/ui/app.py`, затем в браузере нажмите `Ctrl+Shift+R`. Кнопка Streamlit `Rerun` перечитает скрипт, но не гарантирует сброс уже загруженных `.env` / YAML-настроек в памяти процесса.

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

Откройте адрес, который покажет Streamlit, обычно `http://localhost:8501`. В режиме "Анализ ТЗ" загрузите тестовый файл из `test_data`, запустите анализ и скачайте отчет. В режиме "Консультация" задайте короткий вопрос по базе знаний и дождитесь ответа. На CPU-only Ollama первый ответ может занимать 60–90 секунд — это разовая плата за подъём модели в память, последующие запросы возвращаются за 5–15 секунд. С BL-55 (issue #199) текст спиннера «Спрашиваем LLM…» явно содержит это предупреждение, а в сайдбаре доступна кнопка **«🔥 Прогреть модель»** для прогрева локальной Ollama до первого вопроса.

### 2.8 Smoke-проверка «📊 Анализ ТЗ» (BL-54, issue #196)

В режиме «📊 Анализ ТЗ» должна сразу появиться форма загрузки файла:

1. Нажмите «📎 Файл тендерного ТЗ» и выберите `test_data\sample_tz.xlsx` (или `.docx` до 10 МБ — лимит NFR-09).
2. Выберите формат отчёта в радио-кнопке (`.xlsx` / `.docx` / `.md`).
3. Нажмите «🚀 Запустить анализ» — индикатор «Идёт анализ требований… NFR-03: ≤ 15 мин на CPU-only» должен исчезнуть успешным баннером.
4. Нажмите «📥 Скачать отчёт ({формат})» и убедитесь, что файл выгружается с `run_id` в имени.

Smoke-критерий: после `streamlit run src/ui/app.py` в стартовом состоянии видны uploader, радио форматов и неактивная кнопка «🚀 Запустить анализ» (BL-54). Если вместо них отображается старое поле ввода запроса — проверьте `configs/ui_config.yaml: ui.analysis_query_mode` (должно быть `false`).

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

> ⚠️ **BL-53 — перед тем как искать ошибку, проверьте кэш `.env` / `configs/*.yaml`.** Если вы недавно правили `.env` или `configs/*.yaml` и видите «прежнюю» ошибку (`Connection refused`, неверный ответ LLM, старая модель в логах) — Streamlit держит в памяти значения, прочитанные при старте. Нажатие `Rerun` в Streamlit перезапускает только Python-код страницы, а не процесс — `load_dotenv()` повторно не вызывается, YAML-конфиги не перечитываются. Выполните `Ctrl+C` → `streamlit run src/ui/app.py` заново → `Ctrl+Shift+R` в браузере (см. §2 предупреждение «BL-53 — кэш `.env` и `configs/*.yaml`»), и только потом ищите другую причину.

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
| `Connection refused` или `Ollama is unreachable` | Не запущен daemon Ollama **или** `ollama.exe` не в PATH | Запустить отдельное окно CMD с `ollama serve`; если команда `ollama` не найдена — пройти §1.4a (BL-51 guard: `setx PATH "%PATH%;%LOCALAPPDATA%\Programs\Ollama"` + перезапуск CMD) |
| `Не удалось найти исполняемый файл Ollama` | BL-51 guard не нашёл `ollama.exe` ни в PATH, ни по стандартным путям | Установить Ollama for Windows и выполнить §1.4a (`setx PATH ...` + перезапуск CMD) |
| `${VAR:default}` не подставляется как ожидалось | Переменная окружения не задана в текущем окне CMD | Временно задать прямое значение через `set VAR=value` или прописать значение в `.env` |
| `ModuleNotFoundError: src` | Не задан `PYTHONPATH` перед запуском UI | Выполнить `set PYTHONPATH=C:\Projects\clarify-engine-ai` |
| `Обнаружен файл .env.txt` | Notepad сохранил файл как `.env.txt` вместо `.env` | Выполнить `ren .env.txt .env` (см. BL-50, issue #194); guard остановит запуск, пока имя не исправлено |
| `В .env отсутствуют или пустые обязательные переменные` | `OLLAMA_MODEL` или `OLLAMA_BASE_URL` пустые в `.env` | Заполнить значения по образцу из `.env.example` (`qwen2.5:7b` / `http://localhost:11434`) |
| «Правка `.env` / `configs/*.yaml` не применилась» | Streamlit держит значения, прочитанные при старте процесса; `Rerun` повторно не вызывает `load_dotenv()` и не перечитывает YAML | См. §2 «BL-53 — кэш `.env` и `configs/*.yaml`»: `Ctrl+C` → `streamlit run src/ui/app.py` заново → `Ctrl+Shift+R` в браузере |

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
