"""Streamlit UI for the AI-powered tender requirements (TZ) analyzer.

Provides two tabs:
1. Analysis — file upload, model selection, pipeline trigger, result download.
2. Concept & KB — renders ``docs/CONCEPT.md`` as the single source of truth.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import yaml
except ImportError:  # pragma: no cover - handled by requirements.txt
    yaml = None  # type: ignore[assignment]


APP_VERSION = "0.1.0-mvp"
REPO_URL = "https://github.com/G-Ivan-A/mango-tz-ai-analyzer"
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


def run_analysis_pipeline(file_bytes: bytes, filename: str, provider: str) -> bytes:
    """Stub for the Issue #5 analysis pipeline.

    Returns a placeholder report tied to the uploaded file and selected model
    so the UI flow (upload → run → download) is fully exercisable today.
    """
    time.sleep(2)
    report = (
        "Mango TZ AI Analyzer — preliminary report (stub)\n"
        f"Source file: {filename}\n"
        f"Source size (bytes): {len(file_bytes)}\n"
        f"Model / provider: {provider}\n"
        "Status: pipeline integration pending (Issue #5).\n"
    )
    return report.encode("utf-8")


def render_sidebar(config: dict[str, Any]) -> None:
    with st.sidebar:
        st.header("ℹ️ О приложении")
        st.write(f"**Версия:** `{APP_VERSION}`")
        st.markdown(f"**Репозиторий:** [GitHub]({REPO_URL})")
        st.markdown(f"**Issue tracker:** [Issues]({REPO_URL}/issues)")

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
            st.caption("Режим: 🧪 тестовые данные")


def render_analysis_tab(config: dict[str, Any]) -> None:
    st.title("🤖 AI-анализ тендерных ТЗ")
    st.write(
        "Загрузите файл ТЗ в формате `.xlsx` или `.docx`, выберите модель и "
        "запустите анализ. Результат можно будет скачать."
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
    selected = st.selectbox(
        "🧠 Модель / провайдер LLM",
        options=options,
        index=default_index,
        help="Список загружен из configs/llm_config.yaml.",
    )

    run_clicked = st.button("▶️ Запустить анализ", type="primary")

    if run_clicked:
        if uploaded_file is None:
            st.warning("Сначала загрузите файл ТЗ.")
            return
        provider_label = (
            (config.get("active_provider") or "auto")
            if selected.startswith("🪄")
            else selected
        )
        with st.spinner("Обрабатываем ТЗ — это может занять до пары минут..."):
            try:
                report_bytes = run_analysis_pipeline(
                    uploaded_file.getvalue(), uploaded_file.name, provider_label
                )
            except Exception as exc:  # noqa: BLE001 - surface any pipeline error
                st.error(f"Не удалось выполнить анализ: {exc}")
                return

        st.success("Анализ завершён.")
        st.session_state["last_report"] = {
            "filename": f"{Path(uploaded_file.name).stem}__report.txt",
            "data": report_bytes,
        }

    last_report = st.session_state.get("last_report")
    if last_report:
        st.download_button(
            label="⬇️ Скачать отчёт",
            data=io.BytesIO(last_report["data"]),
            file_name=last_report["filename"],
            mime="text/plain",
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
