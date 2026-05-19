"""Contract tests for the BL-41 UI component layer (issue #168).

The tests pin two invariants that the refactor must preserve:

* All user-facing Russian copy lives in :mod:`src.ui.constants.LABELS` so
  translators or proof-readers can edit a single dict without touching
  business logic.
* The component helpers in :mod:`src.ui.components` expose stable callables
  that ``src.ui.app`` (and any future entry point) can compose without
  re-implementing rendering details.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Literal


def _ensure_streamlit_stub() -> None:
    """Provide a minimal stub so importing components never needs Streamlit."""
    stub = sys.modules.get("streamlit")
    if stub is None:
        stub = ModuleType("streamlit")
        sys.modules["streamlit"] = stub

    def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    class _Ctx:
        def __enter__(self) -> "_Ctx":
            return self

        def __exit__(self, *_exc: Any) -> Literal[False]:
            return False

    def _decorator(*_args: Any, **_kwargs: Any):
        def _wrap(fn):
            return fn

        return _wrap

    for attr in (
        "set_page_config",
        "title",
        "write",
        "header",
        "subheader",
        "caption",
        "info",
        "success",
        "warning",
        "error",
        "markdown",
        "divider",
        "selectbox",
        "button",
        "file_uploader",
        "download_button",
        "rerun",
        "link_button",
        "code",
        "json",
        "toggle",
        "slider",
        "text_area",
        "radio",
        "chat_input",
    ):
        if not hasattr(stub, attr):
            setattr(stub, attr, _noop)
    if not hasattr(stub, "session_state"):
        setattr(stub, "session_state", {})
    if not hasattr(stub, "sidebar"):
        setattr(stub, "sidebar", _Ctx())
    if not hasattr(stub, "expander"):
        setattr(stub, "expander", lambda *_a, **_kw: _Ctx())
    if not hasattr(stub, "spinner"):
        setattr(stub, "spinner", lambda *_a, **_kw: _Ctx())
    if not hasattr(stub, "chat_message"):
        setattr(stub, "chat_message", lambda *_a, **_kw: _Ctx())
    if not hasattr(stub, "cache_resource"):
        setattr(stub, "cache_resource", _decorator)
    if not hasattr(stub, "toast"):
        setattr(stub, "toast", _noop)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_ensure_streamlit_stub()


from src.ui import constants  # noqa: E402
from src.ui.components import (  # noqa: E402
    coerce_page,
    format_dependency_summary,
    render_chat_history,
    render_chunks,
    render_sidebar,
    render_status_legend,
    render_upload_zone,
    section_signature,
    truncate,
)
from src.ui.components.chat_interface import (  # noqa: E402
    latest_assistant_message_index,
)


# --------------------------------------------------------- LABELS contract --
def test_labels_dict_covers_every_required_ui_slot() -> None:
    """LABELS must include every key the orchestrator and components consume."""
    required_keys = {
        # page chrome
        "page_title",
        "page_subtitle",
        # sidebar
        "sidebar_header",
        "sidebar_mode_label",
        "sidebar_debug_label",
        "sidebar_debug_help",
        "sidebar_topk_label",
        "sidebar_topk_help",
        "sidebar_topk_info_expander",
        "sidebar_topk_warning_template",
        "sidebar_clear_history_button",
        "sidebar_clear_history_help",
        "sidebar_history_caption",
        "sidebar_fallback_caption",
        "sidebar_vector_store_caption",
        "sidebar_collection_caption",
        "sidebar_embedding_caption",
        "sidebar_no_env_warning",
        # analysis
        "analysis_query_label",
        "analysis_query_placeholder",
        "analysis_submit_button",
        "analysis_empty_query_warning",
        "analysis_intro_info",
        "analysis_response_header",
        "analysis_response_empty",
        "analysis_prompt_expander",
        # consultation
        "consultation_caption_template",
        "consultation_input_placeholder",
        "consultation_intro_info",
        # chunks viewer
        "chunks_header",
        "chunks_empty_info",
        "chunks_metadata_header",
        "chunks_full_text_header",
        "chunks_snippet_header",
        "chunks_legend_header",
        # export controls
        "export_format_label",
        "export_format_help",
        "export_mode_caption",
        "export_download_button_template",
        "export_chat_download_button",
        "export_router_error_template",
        # spinners
        "spinner_search",
        "spinner_llm",
        "spinner_retriever_init",
        "spinner_llm_init",
        # errors
        "error_initialisation",
        "error_no_saved_query",
        "error_retry_caption",
        "error_download_button",
        "error_remediation_expander",
        "error_remediation_default",
        "error_run_id_caption",
        # toasts
        "toast_history_cleared",
        "toast_search_success",
    }
    missing = required_keys - set(constants.LABELS)
    assert not missing, f"LABELS dict is missing keys: {sorted(missing)}"


def test_labels_values_are_non_empty_strings() -> None:
    """No empty placeholders sneak in — empty copy is worse than a bug."""
    for key, value in constants.LABELS.items():
        assert isinstance(value, str), f"LABELS[{key!r}] must be a string"
        assert value.strip(), f"LABELS[{key!r}] must not be empty"


def test_download_button_template_renders_with_format_label() -> None:
    """The export button stays compatible with test_ui_modes expectations."""
    rendered = constants.LABELS["export_download_button_template"].format(
        label=constants.EXPORT_FORMAT_LABELS["xlsx"]
    )
    assert rendered == "📥 Скачать отчет (.xlsx)"


def test_retry_caption_and_run_id_templates_format_cleanly() -> None:
    caption = constants.LABELS["error_retry_caption"].format(
        reason="OpenRouter timeout"
    )
    assert caption == "Причина: OpenRouter timeout"

    run_id_caption = constants.LABELS["error_run_id_caption"].format(
        run_id="abc-123"
    )
    assert run_id_caption == "run_id: abc-123"


def test_status_tooltips_cover_all_export_statuses() -> None:
    """Every status the LLM can emit must have a hover hint."""
    assert set(constants.STATUS_TOOLTIPS) >= {"Да", "Нет", "Частично", "НД"}


# ----------------------------------------------- component callable surface --
def test_component_package_exposes_expected_callables() -> None:
    """``from src.ui.components import X`` works for the documented surface."""
    callables = [
        coerce_page,
        format_dependency_summary,
        render_chat_history,
        render_chunks,
        render_sidebar,
        render_status_legend,
        render_upload_zone,
        section_signature,
        truncate,
    ]
    for fn in callables:
        assert callable(fn), f"{fn!r} is not callable"


def test_latest_assistant_message_index_handles_empty_history() -> None:
    assert latest_assistant_message_index([]) is None


def test_latest_assistant_message_index_finds_most_recent_turn() -> None:
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]
    assert latest_assistant_message_index(messages) == 3


def test_render_status_legend_degrades_gracefully_without_columns(monkeypatch) -> None:
    """Test stubs without ``st.columns`` must still get the tooltip legend."""
    import streamlit as st  # noqa: WPS433 — module-level stub

    captured: list[str] = []
    monkeypatch.setattr(st, "caption", lambda message: captured.append(message))
    monkeypatch.delattr(st, "columns", raising=False)

    render_status_legend()

    assert captured, "Fallback caption must be rendered when columns is missing"
    assert "Да" in captured[0] and "Нет" in captured[0]


def test_truncate_appends_ellipsis_when_text_exceeds_limit() -> None:
    long_text = "А" * 200
    truncated = truncate(long_text, limit=50)
    assert truncated.endswith("...")
    assert len(truncated) <= 53  # 50 chars + "..."


def test_truncate_returns_short_text_unchanged() -> None:
    assert truncate("короткий ответ", limit=50) == "короткий ответ"


def test_coerce_page_rejects_non_positive_values() -> None:
    assert coerce_page(0) is None
    assert coerce_page(-3) is None
    assert coerce_page("abc") is None
    assert coerce_page(None) is None
    assert coerce_page("7") == 7
    assert coerce_page(12) == 12


def test_section_signature_prefers_number_and_title() -> None:
    sig = section_signature({"section_number": "3.2", "section_title": "Безопасность"})
    assert sig == "§3.2 Безопасность"


def test_section_signature_returns_empty_when_no_metadata() -> None:
    assert section_signature({}) == ""


# ----------------------------------------------- BL-48.6 retrieval settings --
def test_resolve_retrieval_settings_reads_full_config() -> None:
    from src.ui.components.mode_selector import resolve_retrieval_settings

    config = {
        "ui": {
            "retrieval": {
                "top_k_min": 1,
                "top_k_max": 20,
                "top_k_default": 5,
                "top_k_production_max": 10,
                "top_k_label": "Глубина поиска по документации",
                "top_k_help": "help-line",
                "top_k_tooltip": "tooltip-body",
                "top_k_warning_template": "warn>{limit}",
            }
        }
    }
    settings = resolve_retrieval_settings(config)
    assert settings["top_k_min"] == 1
    assert settings["top_k_max"] == 20
    assert settings["top_k_default"] == 5
    assert settings["top_k_production_max"] == 10
    assert settings["label"] == "Глубина поиска по документации"
    assert settings["help"] == "help-line"
    assert settings["tooltip"] == "tooltip-body"
    assert settings["warning_template"] == "warn>{limit}"


def test_resolve_retrieval_settings_uses_defaults_for_empty_config() -> None:
    from src.ui.components.mode_selector import (
        DEFAULT_TOP_K,
        DEFAULT_TOP_K_MAX,
        DEFAULT_TOP_K_MIN,
        DEFAULT_TOP_K_PRODUCTION_MAX,
        resolve_retrieval_settings,
    )

    for cfg in ({}, {"ui": {}}, {"ui": {"retrieval": "not-a-dict"}}, None):
        settings = resolve_retrieval_settings(cfg)
        assert settings["top_k_min"] == DEFAULT_TOP_K_MIN
        assert settings["top_k_max"] == DEFAULT_TOP_K_MAX
        assert settings["top_k_default"] == DEFAULT_TOP_K
        assert settings["top_k_production_max"] == DEFAULT_TOP_K_PRODUCTION_MAX
        assert settings["label"]
        assert settings["warning_template"]


def test_resolve_retrieval_settings_clamps_default_within_range() -> None:
    """Default is clamped to ``[min, max]`` so a misconfigured value can't crash the slider."""
    from src.ui.components.mode_selector import resolve_retrieval_settings

    settings = resolve_retrieval_settings(
        {"ui": {"retrieval": {"top_k_min": 5, "top_k_max": 8, "top_k_default": 50}}}
    )
    assert settings["top_k_default"] == 8

    settings_low = resolve_retrieval_settings(
        {"ui": {"retrieval": {"top_k_min": 3, "top_k_max": 8, "top_k_default": "broken"}}}
    )
    # Coerce failure falls back to module default (5) which sits inside [3, 8].
    assert settings_low["top_k_default"] == 5


def test_resolve_retrieval_settings_ignores_malformed_max_lower_than_min() -> None:
    from src.ui.components.mode_selector import resolve_retrieval_settings

    settings = resolve_retrieval_settings(
        {"ui": {"retrieval": {"top_k_min": 4, "top_k_max": 2, "top_k_default": 3}}}
    )
    assert settings["top_k_max"] >= settings["top_k_min"]
    assert settings["top_k_default"] >= settings["top_k_min"]


def test_render_top_k_warning_triggers_above_production_max(monkeypatch) -> None:
    """Values above ``top_k_production_max`` must render a Streamlit warning."""
    import streamlit as st  # noqa: WPS433 — stub injected at import time
    from src.ui.components import mode_selector

    captured: list[str] = []
    monkeypatch.setattr(st, "warning", lambda message: captured.append(message))

    settings = {
        "top_k_production_max": 10,
        "warning_template": "⚠️ > {limit}",
    }
    mode_selector._render_top_k_warning(11, settings)
    mode_selector._render_top_k_warning(10, settings)
    mode_selector._render_top_k_warning(20, settings)

    assert captured == ["⚠️ > 10", "⚠️ > 10"]


def test_render_top_k_warning_skips_when_threshold_disabled(monkeypatch) -> None:
    import streamlit as st  # noqa: WPS433 — stub injected at import time
    from src.ui.components import mode_selector

    captured: list[str] = []
    monkeypatch.setattr(st, "warning", lambda message: captured.append(message))

    mode_selector._render_top_k_warning(
        20, {"top_k_production_max": 0, "warning_template": "x"}
    )
    assert captured == []


def test_top_k_tooltip_mentions_every_required_phrase() -> None:
    """The shipped tooltip must satisfy the BL-48.6 contract verbatim."""
    import yaml

    cfg = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "ui_config.yaml").read_text(
            encoding="utf-8"
        )
    )
    tooltip = str(cfg["ui"]["retrieval"]["top_k_tooltip"])
    # BL-48.6 DoD: tooltip must call out "для КАЖДОГО требования" and explain
    # the under-fill behaviour and give a numeric recommendation.
    assert "КАЖДОГО" in tooltip
    assert "не создавая искусственных" in tooltip
    assert "Рекомендация" in tooltip
    # Label must follow business terminology — no «чанк» word stays anywhere.
    assert "чанк" not in cfg["ui"]["retrieval"]["top_k_label"].lower()


def test_ui_config_retrieval_section_is_complete() -> None:
    """The shipped config must define every BL-48.6 key — defaults are a safety net only."""
    import yaml

    cfg = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "ui_config.yaml").read_text(
            encoding="utf-8"
        )
    )
    retrieval = cfg["ui"]["retrieval"]
    assert retrieval["top_k_min"] == 1
    assert retrieval["top_k_max"] == 20
    assert retrieval["top_k_default"] == 5
    assert retrieval["top_k_production_max"] == 10
    assert retrieval["top_k_label"].strip()
    assert retrieval["top_k_tooltip"].strip()
    assert "{limit}" in retrieval["top_k_warning_template"]
