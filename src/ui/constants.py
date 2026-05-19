"""Russian UI text constants and session-state keys for the Streamlit UI.

BL-41 (issue #168) extracts every user-facing string from ``src/ui/app.py``
into this single module so the UI can be re-translated or proofread without
touching business logic. The mode identifiers, session-state keys, and export
metadata also live here because tests pin them through ``src.ui.app``
re-exports.
"""

from __future__ import annotations

from typing import Dict, List

# ----------------------------------------------------------------- modes --
MODE_STATELESS = "stateless"
MODE_CONSULTATION = "consultation"

MODE_LABELS: Dict[str, str] = {
    MODE_STATELESS: "📊 Анализ ТЗ",
    MODE_CONSULTATION: "💬 Консультация по документации",
}
MODE_ORDER: List[str] = [MODE_STATELESS, MODE_CONSULTATION]

MODE_HELP: Dict[str, str] = {
    MODE_STATELESS: (
        "Stateless проверка требований без истории диалога. "
        "Подходит для пакетного анализа ТЗ — минимум токенов и максимум скорости."
    ),
    MODE_CONSULTATION: (
        "Диалог с базой знаний с сохранением последних сообщений. "
        "Подходит для уточнений и follow-up вопросов."
    ),
}

# --------------------------------------------------------- session keys --
SESSION_LAST_QUERY_KEY = "last_query"
SESSION_LAST_ERROR_KEY = "last_error"
SESSION_PROCESSING_KEY = "is_processing"
SESSION_PENDING_QUERY_KEY = "pending_query"
SESSION_PENDING_MODE_KEY = "pending_mode"
SESSION_PENDING_RUN_ID_KEY = "pending_run_id"
SESSION_LAST_ANALYSIS_RESULT_KEY = "last_analysis_result"
SESSION_EXPORT_FORMAT_KEY = "analysis_export_format"

# --------------------------------------------------------- export meta --
EXPORT_FORMAT_LABELS: Dict[str, str] = {
    "xlsx": ".xlsx",
    "docx": ".docx",
    "md": ".md",
}
EXPORT_MIME_TYPES: Dict[str, str] = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown; charset=utf-8",
}

# ---------------------------------------------------- status tooltips --
# BL-41 (issue #168) — UX requirement: hover over a status cell explains the
# meaning to a business analyst. The dict is consumed by the results viewer
# component, which renders a legend right above the citations table.
STATUS_TOOLTIPS: Dict[str, str] = {
    "Да": "Требование полностью соответствует документации.",
    "Частично": "Требуется ручная проверка — есть несовпадения в формулировках или объёме.",
    "Нет": "Функциональность в документации не найдена.",
    "НД": "Недостаточно данных в базе знаний для однозначного решения.",
    "Ошибка": "Сбой пайплайна (сеть, провайдер LLM, валидация). Используйте «Повторить».",
}

# ---------------------------------------------------- generic UI text --
UI_GENERATION_ERROR_TEXT = "Не удалось получить ответ."
UI_GENERATION_ERROR_REASON = "Все провайдеры недоступны"
UI_SERVICE_UNAVAILABLE_TEXT = (
    "Сервис временно недоступен. Попробуйте позже."
)
RETRY_BUTTON_LABEL = "Повторить"

# --------------------------------------------------- consolidated LABELS --
# A single dict the components can spread into Streamlit widgets so opechatki
# in the Russian copy are fixed in one place. Keys are stable identifiers;
# values are display strings.
LABELS: Dict[str, str] = {
    # Page chrome
    "page_title": "Clarify Engine — поиск по базе знаний",
    "page_subtitle": (
        "Задайте вопрос по индексированной документации — система достанет "
        "релевантные фрагменты и попросит LLM подготовить ответ со ссылками."
    ),
    # Sidebar
    "sidebar_header": "Настройки",
    "sidebar_mode_label": "Режим работы",
    "sidebar_debug_label": "Режим отладки",
    "sidebar_debug_help": (
        "Показывать сырые метаданные чанков и промпт, отправленный в LLM."
    ),
    # BL-48.6 (issue #184): бизнес-формулировка вместо «чанков». Реальный label
    # и tooltip берутся из `configs/ui_config.yaml`; здесь — фоллбек, чтобы
    # сайдбар не падал при пустом конфиге.
    "sidebar_topk_label": "Макс. число источников для проверки",
    "sidebar_topk_help": (
        "Глубина поиска: сколько релевантных разделов документации система "
        "берёт для КАЖДОГО атомарного требования."
    ),
    "sidebar_topk_info_expander": "ℹ️ Что такое «макс. число источников»",
    "sidebar_topk_warning_template": (
        "⚠️ Значения выше {limit} могут увеличить время обработки и расход "
        "токенов."
    ),
    "sidebar_clear_history_button": "🧹 Очистить историю",
    "sidebar_clear_history_help": (
        "Удаляет все сохранённые сообщения текущей консультации."
    ),
    "sidebar_history_caption": "История: {len} / {max} сообщений",
    "sidebar_fallback_caption": (
        "LLM fallback chain: **GigaChat → OpenRouter → Ollama**"
    ),
    "sidebar_vector_store_caption": "Vector store: `{path}`",
    "sidebar_collection_caption": "Коллекция: `{name}`",
    "sidebar_embedding_caption": "Модель эмбеддингов: `{name}`",
    "sidebar_no_env_warning": (
        "`.env` не найден в корне репозитория — скопируйте `.env.example` "
        "в `.env` и заполните ключи API для вызовов LLM."
    ),
    # Analysis mode
    "analysis_query_label": "Запрос к базе знаний",
    "analysis_query_placeholder": (
        "Сформулируйте вопрос или вставьте требование из ТЗ…"
    ),
    "analysis_submit_button": "🔎 Найти и спросить LLM",
    "analysis_empty_query_warning": "Введите запрос перед поиском.",
    "analysis_intro_info": (
        "Сформулируйте вопрос и нажмите **🔎 Найти и спросить LLM**, чтобы "
        "получить ответ с цитатами из базы знаний."
    ),
    "analysis_response_header": "Ответ LLM",
    "analysis_response_empty": "_(пустой ответ модели)_",
    "analysis_prompt_expander": "Промпт, отправленный в LLM",
    # Consultation mode
    "consultation_caption_template": (
        "Режим консультации: ассистент помнит последние {max} сообщений. "
        "Используйте **🧹 Очистить историю** в сайдбаре, чтобы начать диалог "
        "заново."
    ),
    "consultation_input_placeholder": "Задайте вопрос по документации…",
    "consultation_intro_info": (
        "Введите вопрос ниже, чтобы начать консультацию по базе знаний."
    ),
    "consultation_history_cleared_toast": "История консультации очищена.",
    # Chunks viewer
    "chunks_header": "Источники",
    "chunks_empty_info": "Подходящих фрагментов не найдено.",
    "chunks_metadata_header": "**Метаданные**",
    "chunks_full_text_header": "**Полный текст фрагмента**",
    "chunks_snippet_header": "**Фрагмент**",
    "chunks_legend_header": "**Условные обозначения статусов:**",
    # Export controls
    "export_format_label": "Формат отчета",
    "export_format_help": (
        "ℹ️ Excel — для дальнейшего анализа в таблице, Word — для печатного "
        "отчета, Markdown — для git/CI."
    ),
    "export_mode_caption": "Режим сохранения: create_new",
    "export_download_button_template": "📥 Скачать отчет ({label})",
    "export_chat_download_button": "📥 Сохранить диалог (.md)",
    "export_router_error_template": "Ошибка генерации файла: {error}",
    # Spinners
    "spinner_search": "Ищем релевантные фрагменты в базе знаний…",
    "spinner_llm": "Спрашиваем LLM (GigaChat → OpenRouter → Ollama)…",
    "spinner_retriever_init": "Инициализация поискового движка (BM25 + bge-m3 + ChromaDB)…",
    "spinner_llm_init": "Инициализация LLM-клиента…",
    # Errors
    "error_initialisation": "Не удалось подготовить поиск по базе знаний.",
    "error_no_saved_query": "Нет сохранённого запроса для повторной попытки.",
    "error_retry_caption": "Причина: {reason}",
    "error_download_button": "📥 Скачать логи",
    "error_remediation_expander": "ℹ️ Как исправить",
    "error_remediation_default": (
        "Проверьте конфигурацию провайдеров и серверные логи по run_id."
    ),
    "error_run_id_caption": "run_id: {run_id}",
    # Toasts
    "toast_history_cleared": "🧹 История консультации очищена",
    "toast_search_success": "✅ Ответ готов",
}
