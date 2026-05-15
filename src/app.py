"""Streamlit UI for the AI-powered tender requirements (TZ) analyzer.

Provides two tabs:

1. ``🔍 Анализ ТЗ`` — upload a ``.xlsx`` / ``.docx`` file, pick a provider,
   run the full pipeline (parsing → RAG → LLM → validated export) with a
   live progress indicator, and download the resulting Excel report.
2. ``📖 Концепция и БЗ`` — render ``docs/CONCEPT.md`` and link to GitHub Issues.
"""

from __future__ import annotations

import io
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

import streamlit as st

try:
    import yaml
except ImportError:  # pragma: no cover - handled by requirements.txt
    yaml = None  # type: ignore[assignment]

from src.pipeline import PipelineStats, run_analysis

logger = logging.getLogger(__name__)

APP_VERSION = "0.2.0-mvp"
REPO_URL = "https://github.com/G-Ivan-A/mango-tz-ai-analyzer"
ISSUES_URL = f"{REPO_URL}/issues"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "llm_config.yaml"
CONCEPT_PATH = PROJECT_ROOT / "docs" / "CONCEPT.md"


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
) -> tuple[PipelineStats, bytes, str]:
    """Persist the upload to a temp file and execute the pipeline.

    Returns ``(stats, xlsx_bytes, run_id)`` so the UI can render counters and
    expose the resulting workbook for download.
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


def render_analysis_tab(config: dict[str, Any]) -> None:
    st.title("🤖 AI-анализ тендерных ТЗ")
    st.write(
        "Загрузите файл ТЗ в формате `.xlsx` или `.docx` и запустите анализ. "
        "Результат можно будет скачать в виде Excel-файла с колонками "
        "`[Статус]`, `[Комментарий]`, `[Цитаты]`, `[Confidence]`."
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

        progress = st.progress(0, text="Старт анализа...")

        def _update_progress(value: float, message: str) -> None:
            progress.progress(min(max(value, 0.0), 1.0), text=message)

        try:
            stats, report_bytes, run_id = _run_pipeline_on_upload(
                uploaded_file.getvalue(),
                uploaded_file.name,
                progress_callback=_update_progress,
            )
        except Exception as exc:  # noqa: BLE001 - surface any pipeline error
            progress.empty()
            st.error(f"Не удалось выполнить анализ: {exc}")
            return

        progress.empty()
        st.success(
            f"Анализ завершён (run_id `{run_id}`). "
            f"Всего: {stats.total}, успешно: {stats.success}, "
            f"ошибки: {stats.errors}, НД: {stats.nd}."
        )
        st.session_state["last_report"] = {
            "filename": f"{Path(uploaded_file.name).stem}__result_{run_id}.xlsx",
            "data": report_bytes,
        }

    last_report = st.session_state.get("last_report")
    if last_report:
        st.download_button(
            label="⬇️ Скачать результат (.xlsx)",
            data=io.BytesIO(last_report["data"]),
            file_name=last_report["filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


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


def main() -> None:
    st.set_page_config(
        page_title="Mango TZ AI Analyzer",
        page_icon="🤖",
        layout="wide",
    )

    config = load_llm_config()
    render_sidebar(config)

    tab_analysis, tab_docs = st.tabs(["🔍 Анализ ТЗ", "📖 Концепция и БЗ"])
    with tab_analysis:
        render_analysis_tab(config)
    with tab_docs:
        render_docs_tab()


if __name__ == "__main__":
    main()
