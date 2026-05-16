"""Streamlit UI for the AI-powered tender requirements (TZ) analyzer.

Per issue #45 MUST 5 the UI provides three tabs:

1. ``🔍 Анализ ТЗ`` — upload a ``.xlsx`` / ``.docx`` file, run the full
   pipeline (parsing → RAG → LLM → validated export) with a progress bar and
   Success / Errors counters, download the resulting Excel report, and
   **re-run only error rows** (filtered by ``[Статус] == Ошибка``) using a
   button — no re-upload required.
2. ``📖 Концепция и БЗ`` — render ``docs/CONCEPT.md`` and link to GitHub Issues.
3. ``📋 Справка для БА`` — concise read-only quick-start for Business Analysts.

Notes on the retry workflow:

The retry button rebuilds a subset Excel containing only the rows that the
previous run marked as ``Ошибка``, runs the pipeline on that subset, and
patches the corresponding cells of the original result file in memory. The
pipeline itself is intentionally sequential (no parallelisation — see
``src/llm/client.py``), so retrying surfaces the same network policy.
"""

from __future__ import annotations

import io
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

import streamlit as st

try:
    import yaml
except ImportError:  # pragma: no cover - handled by requirements.txt
    yaml = None  # type: ignore[assignment]

from src.pipeline import PipelineStats, run_analysis

logger = logging.getLogger(__name__)

APP_VERSION = "0.3.0-mvp"
REPO_URL = "https://github.com/G-Ivan-A/clarify-engine-ai"
ISSUES_URL = f"{REPO_URL}/issues"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "llm_config.yaml"
CONCEPT_PATH = PROJECT_ROOT / "docs" / "CONCEPT.md"

ERROR_STATUS = "Ошибка"
STATUS_COLUMN = "[Статус]"
COMMENT_COLUMN = "[Комментарий]"
CONFIDENCE_COLUMN = "[Confidence]"
RUNID_COLUMN = "[RunID]"
RESULT_COLUMNS = [STATUS_COLUMN, COMMENT_COLUMN, CONFIDENCE_COLUMN, RUNID_COLUMN]


def load_llm_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load LLM provider config; return an empty dict on any failure."""
    if yaml is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def available_providers(config: dict[str, Any]) -> list[str]:
    providers = config.get("providers") or {}
    if isinstance(providers, dict) and providers:
        return list(providers.keys())
    fallback = config.get("fallback_providers") or []
    return [str(item) for item in fallback]


def _run_pipeline_on_upload(
    file_bytes: bytes,
    filename: str,
    progress_callback: Optional[Any] = None,
) -> Tuple[PipelineStats, bytes, str]:
    """Persist the upload to a temp file and execute the pipeline.

    Returns ``(stats, xlsx_bytes, run_id)``.
    """
    run_id = str(uuid.uuid4())
    suffix = Path(filename).suffix or ".xlsx"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f"input{suffix}"
        output_path = tmp_path / f"result_{run_id}.xlsx"
        input_path.write_bytes(file_bytes)

        if progress_callback:
            progress_callback(0.1, "Загружаем требования...")

        stats = run_analysis(
            input_file=str(input_path),
            output_file=str(output_path),
            run_id=run_id,
        )

        if progress_callback:
            progress_callback(1.0, "Готово")

        return stats, output_path.read_bytes(), run_id


def _retry_error_rows(
    source_bytes: bytes,
    source_filename: str,
    last_result_bytes: bytes,
    progress_callback: Optional[Any] = None,
) -> Tuple[PipelineStats, bytes, str, int]:
    """Re-run only rows whose status was ``Ошибка`` in ``last_result_bytes``.

    Returns ``(retry_stats, patched_result_bytes, retry_run_id, retried_count)``.
    The new bytes contain the original result with the error rows overwritten
    by the retry outcome (status / comment / confidence / RunID).
    """
    import pandas as pd  # local import: pandas is in requirements.txt

    full_df = pd.read_excel(io.BytesIO(last_result_bytes))
    if STATUS_COLUMN not in full_df.columns:
        raise RuntimeError(
            "Предыдущий результат не содержит колонку [Статус]; нечего повторять."
        )

    error_mask = full_df[STATUS_COLUMN].astype(str) == ERROR_STATUS
    error_indices = full_df.index[error_mask].tolist()
    if not error_indices:
        raise RuntimeError("В предыдущем результате нет строк со статусом «Ошибка».")

    source_df = pd.read_excel(io.BytesIO(source_bytes))
    subset_df = source_df.iloc[error_indices].reset_index(drop=True)

    retry_run_id = str(uuid.uuid4())
    suffix = Path(source_filename).suffix or ".xlsx"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        subset_input = tmp_path / f"retry_input{suffix}"
        subset_output = tmp_path / f"retry_result_{retry_run_id}.xlsx"
        subset_df.to_excel(subset_input, index=False)

        if progress_callback:
            progress_callback(0.1, f"Повторяем {len(error_indices)} ошибочных строк...")

        retry_stats = run_analysis(
            input_file=str(subset_input),
            output_file=str(subset_output),
            run_id=retry_run_id,
        )
        retry_df = pd.read_excel(subset_output)

    # Harmonise dtypes so an int → float promotion (e.g., legacy result files
    # where [Confidence] was inferred as int64 because every value was 0) does
    # not raise when we patch in fresh floats from the retry result.
    for col in RESULT_COLUMNS:
        if col in full_df.columns and col in retry_df.columns:
            target_dtype = retry_df[col].dtype
            if full_df[col].dtype != target_dtype:
                try:
                    full_df[col] = full_df[col].astype(target_dtype)
                except (TypeError, ValueError):
                    full_df[col] = full_df[col].astype(object)

    for new_idx, orig_idx in enumerate(error_indices):
        for col in RESULT_COLUMNS:
            if col in retry_df.columns:
                full_df.at[orig_idx, col] = retry_df.at[new_idx, col]

    output_buffer = io.BytesIO()
    full_df.to_excel(output_buffer, index=False)

    if progress_callback:
        progress_callback(1.0, "Готово")

    return retry_stats, output_buffer.getvalue(), retry_run_id, len(error_indices)


def _result_status_counts(result_bytes: bytes) -> dict[str, int]:
    """Count rows by status in the latest result file (best-effort)."""
    import pandas as pd

    try:
        df = pd.read_excel(io.BytesIO(result_bytes))
    except Exception:  # noqa: BLE001
        return {}
    if STATUS_COLUMN not in df.columns:
        return {}
    series = df[STATUS_COLUMN].astype(str)
    return {value: int((series == value).sum()) for value in series.unique() if value}


def render_sidebar(config: dict[str, Any]) -> None:
    with st.sidebar:
        st.header("ℹ️ О приложении")
        st.write(f"**Версия:** `{APP_VERSION}`")
        st.markdown(f"**Репозиторий:** [GitHub]({REPO_URL})")
        st.markdown(f"**Issue tracker:** [Issues]({ISSUES_URL})")

        st.divider()
        st.subheader("🩺 Статус системы")
        st.success("UI: OK")
        if CONFIG_PATH.exists():
            st.success("Config: загружен")
        else:
            st.warning("Config: не найден")
        if CONCEPT_PATH.exists():
            st.success("Концепция: доступна")
        else:
            st.warning("Концепция: отсутствует")

        active = config.get("active_provider")
        if active:
            st.caption(f"Активный провайдер по умолчанию: `{active}`")
        if config.get("use_test_data_mode"):
            st.caption("Режим: 🧪 тестовые данные (маскирование принудительно включено)")


def _show_counters(stats: PipelineStats) -> None:
    col_success, col_errors, col_total = st.columns(3)
    col_success.metric("✅ Успешно", stats.success)
    col_errors.metric("❌ Ошибки", stats.errors)
    col_total.metric("📦 Всего", stats.total)


def render_analysis_tab(config: dict[str, Any]) -> None:
    st.title("🤖 AI-анализ тендерных ТЗ")
    st.write(
        "Загрузите файл ТЗ в формате `.xlsx` или `.docx` и запустите анализ. "
        "Результат — Excel-файл с колонками "
        "`[Статус]`, `[Комментарий]`, `[Confidence]`, `[RunID]` "
        "(оригинальные колонки сохраняются)."
    )

    uploaded_file = st.file_uploader(
        "📎 Файл тендерного ТЗ",
        type=["xlsx", "docx"],
        help="Поддерживаются Excel (.xlsx) и Word (.docx) файлы.",
    )

    providers = available_providers(config)
    options = ["🪄 Автоматический выбор", *providers]
    default_provider = config.get("active_provider")
    default_index = (
        options.index(default_provider) if default_provider in options else 0
    )
    st.selectbox(
        "🧠 Модель / провайдер LLM",
        options=options,
        index=default_index,
        help="Список загружен из configs/llm_config.yaml. Фактическая последовательность fallback задаётся в конфиге.",
    )

    run_clicked = st.button("▶️ Запустить анализ", type="primary")

    if run_clicked:
        if uploaded_file is None:
            st.warning("Сначала загрузите файл ТЗ.")
            return

        source_bytes = uploaded_file.getvalue()
        progress = st.progress(0, text="Старт анализа...")

        def _update_progress(value: float, message: str) -> None:
            progress.progress(min(max(value, 0.0), 1.0), text=message)

        try:
            stats, report_bytes, run_id = _run_pipeline_on_upload(
                source_bytes,
                uploaded_file.name,
                progress_callback=_update_progress,
            )
        except Exception as exc:  # noqa: BLE001 - surface any pipeline error
            progress.empty()
            st.error(f"Не удалось выполнить анализ: {exc}")
            return

        progress.empty()
        st.session_state["last_run"] = {
            "source_filename": uploaded_file.name,
            "source_bytes": source_bytes,
            "result_filename": f"{Path(uploaded_file.name).stem}__result_{run_id}.xlsx",
            "result_bytes": report_bytes,
            "run_id": run_id,
            "stats": stats,
        }

    last_run = st.session_state.get("last_run")
    if not last_run:
        return

    stats: PipelineStats = last_run["stats"]
    st.success(
        f"Анализ завершён (run_id `{last_run['run_id']}`). "
        f"Всего: {stats.total}, успешно: {stats.success}, "
        f"ошибки: {stats.errors}, НД: {stats.nd}."
    )
    _show_counters(stats)

    status_counts = _result_status_counts(last_run["result_bytes"])
    error_rows = status_counts.get(ERROR_STATUS, 0)

    st.download_button(
        label="⬇️ Скачать результат (.xlsx)",
        data=io.BytesIO(last_run["result_bytes"]),
        file_name=last_run["result_filename"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    retry_disabled = error_rows == 0
    retry_help = (
        "В текущем результате нет строк со статусом «Ошибка»."
        if retry_disabled
        else f"Повторить пайплайн только для {error_rows} строк со статусом «Ошибка». Файл загружать заново не нужно."
    )
    if st.button(
        "🔁 Повторить только ошибки",
        disabled=retry_disabled,
        help=retry_help,
    ):
        retry_progress = st.progress(0, text="Готовим повтор...")

        def _retry_progress(value: float, message: str) -> None:
            retry_progress.progress(min(max(value, 0.0), 1.0), text=message)

        try:
            retry_stats, new_bytes, retry_run_id, retried = _retry_error_rows(
                source_bytes=last_run["source_bytes"],
                source_filename=last_run["source_filename"],
                last_result_bytes=last_run["result_bytes"],
                progress_callback=_retry_progress,
            )
        except Exception as exc:  # noqa: BLE001
            retry_progress.empty()
            st.error(f"Не удалось повторить ошибки: {exc}")
            return

        retry_progress.empty()
        # Refresh aggregate stats from the patched result. Total stays the same
        # as the original run; we recompute success/errors from the new file.
        new_counts = _result_status_counts(new_bytes)
        patched_stats = PipelineStats(
            run_id=last_run["run_id"],
            total=stats.total,
            success=sum(v for k, v in new_counts.items() if k not in {ERROR_STATUS}),
            errors=new_counts.get(ERROR_STATUS, 0),
            nd=new_counts.get("НД", 0),
            by_provider=dict(stats.by_provider),
        )
        st.session_state["last_run"] = {
            **last_run,
            "result_bytes": new_bytes,
            "result_filename": (
                f"{Path(last_run['source_filename']).stem}__retry_{retry_run_id}.xlsx"
            ),
            "stats": patched_stats,
        }
        st.success(
            f"Повтор завершён (retry run_id `{retry_run_id}`). "
            f"Повторено строк: {retried}, успешно после повтора: {retry_stats.success}, "
            f"осталось ошибок: {patched_stats.errors}."
        )
        st.rerun()


def render_docs_tab() -> None:
    st.header("📘 Концепция внедрения ИИ-анализатора")
    st.info(
        "Этот документ является единым источником истины "
        "(Single Source of Truth) для проекта."
    )

    if CONCEPT_PATH.exists():
        st.markdown(CONCEPT_PATH.read_text(encoding="utf-8"))
    else:
        st.error("❌ Файл `docs/CONCEPT.md` не найден.")

    st.divider()
    st.link_button("🐞 Сообщить о проблеме / предложить улучшение", ISSUES_URL)


def render_ba_help_tab() -> None:
    st.header("📋 Справка для бизнес-аналитика")
    st.markdown(
        """
### Быстрый старт

1. **Загрузите файл ТЗ** в формате `.xlsx` (рекомендуется) или `.docx`.
   Требования читаются из колонки `Требование` (или первой подходящей).
2. **Нажмите «Запустить анализ»** — пайплайн выполнит:
   парсинг → поиск по базе знаний → классификация LLM → экспорт в Excel.
3. **Скачайте результат** через кнопку «⬇️ Скачать результат».
4. При наличии ошибок используйте **«🔁 Повторить только ошибки»**.
   Файл повторно загружать не нужно — повтор выполняется по `RunID`
   с применением экспоненциальной задержки (5с → 15с → 45с) и
   маскированием.

### Колонки результата

| Колонка | Что содержит |
|---|---|
| `[Статус]` | `Да` / `Частично` / `Нет` / `НД` / `Ошибка` |
| `[Комментарий]` | Краткое обоснование решения LLM |
| `[Confidence]` | Уверенность классификатора `0.0–1.0` |
| `[RunID]` | Идентификатор запуска (нужен для повтора) |

### Что делать со статусами

- **`Да`** — требование подтверждено документацией. Цитаты обязательны.
- **`Частично`** — есть частичное соответствие; обычно требует ревью БА.
- **`Нет`** — функциональность отсутствует.
- **`НД`** — данных в базе знаний недостаточно для решения.
  Рассмотрите расширение KB или ручную проверку.
- **`Ошибка`** — сбой пайплайна (сеть, провайдер, валидация).
  Используйте кнопку повтора. Если ошибки повторяются — сообщите PO.

### Что НЕ делает MVP

- Параллельные запросы к LLM (вызовы строго последовательные).
- Inline-редактирование результатов (только чтение и скачивание).
- Экспорт `.docx`.
- Маскирование ФИО / ООО / ИП (отложено; маскируются только
  Email, Телефон, IP, Внутренний домен).
- Интеграция с SharePoint / внешними источниками KB.

### Куда жаловаться

- Технические сбои → откройте issue в репозитории (ссылка в боковой панели).
- Качество классификации → отметьте строку в Excel и передайте PO.
        """
    )


def main() -> None:
    st.set_page_config(
        page_title="Clarify Engine AI",
        page_icon="🤖",
        layout="wide",
    )

    config = load_llm_config()
    render_sidebar(config)

    tab_analysis, tab_docs, tab_ba = st.tabs(
        ["🔍 Анализ ТЗ", "📖 Концепция и БЗ", "📋 Справка для БА"]
    )
    with tab_analysis:
        render_analysis_tab(config)
    with tab_docs:
        render_docs_tab()
    with tab_ba:
        render_ba_help_tab()


if __name__ == "__main__":
    main()
