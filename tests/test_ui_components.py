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

import logging
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
    MAX_UPLOAD_SIZE_BYTES,
    MAX_UPLOAD_SIZE_MB,
    SUPPORTED_EXTENSIONS,
    UploadValidationResult,
    coerce_page,
    format_dependency_summary,
    render_analysis_uploader,
    render_chat_history,
    render_chunks,
    render_sidebar,
    render_status_legend,
    render_upload_zone,
    section_signature,
    truncate,
    validate_uploaded_file,
)
from src.ui.components import analysis_uploader  # noqa: E402
from src.ui.components.chat_interface import (  # noqa: E402
    latest_assistant_message_index,
)


class _StubUpload:
    """Minimal stand-in for Streamlit's ``UploadedFile`` for tests."""

    def __init__(self, name: str, size: int = 0, data: bytes = b"") -> None:
        self.name = name
        self.size = size or len(data)
        self._data = data or b"\x00" * size

    def getvalue(self) -> bytes:
        return self._data

    def getbuffer(self) -> bytes:
        return self._data


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
        # analysis (legacy query-style flow, BL-54 opt-in)
        "analysis_query_label",
        "analysis_query_placeholder",
        "analysis_submit_button",
        "analysis_empty_query_warning",
        "analysis_intro_info",
        "analysis_response_header",
        "analysis_response_empty",
        "analysis_prompt_expander",
        # analysis (BL-54 upload flow, issue #196)
        "analysis_uploader_label",
        "analysis_uploader_help",
        "analysis_uploader_extension_error_template",
        "analysis_uploader_size_error_template",
        "analysis_run_button",
        "analysis_no_file_warning",
        "analysis_pipeline_error_template",
        "analysis_run_in_progress",
        "analysis_progress_template",
        "analysis_counter_template",
        "analysis_run_success_template",
        "analysis_download_button_template",
        "analysis_retry_button",
        "analysis_retry_help_template",
        "analysis_retry_no_errors_help",
        "analysis_retry_unavailable_help",
        "analysis_retry_in_progress",
        "analysis_retry_success_template",
        "analysis_retry_error_template",
        "analysis_intro_upload_info",
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
        # BL-55 warmup button (issue #199)
        "sidebar_warmup_button",
        "sidebar_warmup_help",
        "sidebar_warmup_in_progress",
        "sidebar_warmup_success",
        "sidebar_warmup_error",
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
        render_analysis_uploader,
        render_chat_history,
        render_chunks,
        render_sidebar,
        render_status_legend,
        render_upload_zone,
        section_signature,
        truncate,
        validate_uploaded_file,
    ]
    for fn in callables:
        assert callable(fn), f"{fn!r} is not callable"


# ---------------------------------- BL-54 analysis uploader (issue #196) --
def test_analysis_uploader_supported_constants_match_issue_contract() -> None:
    """`.xlsx` / `.docx` and a 10 МБ limit are pinned by NFR-09 + FR-01."""
    assert SUPPORTED_EXTENSIONS == ("xlsx", "docx")
    assert MAX_UPLOAD_SIZE_MB == 10
    assert MAX_UPLOAD_SIZE_BYTES == 10 * 1024 * 1024


def test_validate_uploaded_file_accepts_xlsx_under_limit() -> None:
    file = _StubUpload("requirements.xlsx", size=1024)
    result = validate_uploaded_file(file)
    assert isinstance(result, UploadValidationResult)
    assert result.ok is True
    assert result.file is file
    assert result.error_message is None


def test_validate_uploaded_file_does_not_collide_with_logrecord_filename(caplog) -> None:
    """INFO logging must not pass ``extra={'filename': ...}`` into logging."""
    file = _StubUpload("requirements.xlsx", size=1024)

    with caplog.at_level(logging.INFO, logger=analysis_uploader.logger.name):
        result = validate_uploaded_file(file)

    assert result.ok is True
    accepted = [
        record
        for record in caplog.records
        if getattr(record, "event", "") == "UPLOAD_ACCEPTED"
    ]
    assert accepted
    assert getattr(accepted[-1], "upload_filename") == "requirements.xlsx"


def test_validate_uploaded_file_accepts_docx_under_limit() -> None:
    file = _StubUpload("tz.docx", size=2_000_000)
    result = validate_uploaded_file(file)
    assert result.ok is True
    assert result.file is file


def test_validate_uploaded_file_rejects_csv_extension() -> None:
    file = _StubUpload("export.csv", size=100)
    result = validate_uploaded_file(file)
    assert result.ok is False
    assert result.file is None
    assert result.error_message and ".csv" in result.error_message
    assert ".xlsx" in result.error_message and ".docx" in result.error_message


def test_validate_uploaded_file_rejects_files_above_10mb() -> None:
    file = _StubUpload("huge.xlsx", size=MAX_UPLOAD_SIZE_BYTES + 1)
    result = validate_uploaded_file(file)
    assert result.ok is False
    assert result.error_message and "10" in result.error_message


def test_validate_uploaded_file_accepts_files_exactly_at_limit() -> None:
    file = _StubUpload("edge.xlsx", size=MAX_UPLOAD_SIZE_BYTES)
    result = validate_uploaded_file(file)
    assert result.ok is True


def test_validate_uploaded_file_returns_not_ok_for_none() -> None:
    result = validate_uploaded_file(None)
    assert result.ok is False
    assert result.file is None


def test_render_analysis_uploader_returns_validated_handle(monkeypatch) -> None:
    """Happy path: a valid upload is returned to the caller untouched."""
    import streamlit as st  # noqa: WPS433 — stub injected at import time

    valid = _StubUpload("input.xlsx", size=2048)
    monkeypatch.setattr(st, "file_uploader", lambda *_a, **_kw: valid)

    captured: list[str] = []
    monkeypatch.setattr(st, "error", lambda message: captured.append(message))

    handle = render_analysis_uploader()

    assert handle is valid
    assert captured == []


def test_render_analysis_uploader_shows_error_for_oversize_file(monkeypatch) -> None:
    import streamlit as st  # noqa: WPS433 — stub injected at import time

    too_big = _StubUpload("big.xlsx", size=MAX_UPLOAD_SIZE_BYTES + 1024)
    monkeypatch.setattr(st, "file_uploader", lambda *_a, **_kw: too_big)

    errors: list[str] = []
    monkeypatch.setattr(st, "error", lambda message: errors.append(message))

    handle = render_analysis_uploader()

    assert handle is None
    assert errors and "10" in errors[0]


def test_render_analysis_uploader_returns_none_when_nothing_uploaded(monkeypatch) -> None:
    import streamlit as st  # noqa: WPS433 — stub injected at import time

    monkeypatch.setattr(st, "file_uploader", lambda *_a, **_kw: None)
    monkeypatch.setattr(st, "error", lambda *_a, **_kw: None)

    handle = render_analysis_uploader()

    assert handle is None


def test_analysis_uploader_filename_is_sanitized_for_logs(monkeypatch) -> None:
    """BL-54 PII clause: filenames flow through ``sanitize_log_record``."""
    sanitized_record: dict = {}

    def _spy(record, **_kwargs):
        sanitized_record.update(record)
        return {"message": "[SANITIZED]"}

    monkeypatch.setattr(analysis_uploader, "sanitize_log_record", _spy)

    safe = analysis_uploader._safe_filename_for_log("alice@example.com.xlsx")
    assert safe == "[SANITIZED]"
    assert sanitized_record["message"] == "alice@example.com.xlsx"


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


# ----------------------------------------------- BL-55 warmup button (issue #199) --
def test_should_render_warmup_button_for_debug_mode_true() -> None:
    """BL-55: ``ui.debug_mode: true`` makes the button visible everywhere."""
    from src.ui.components.sidebar import should_render_warmup_button

    assert (
        should_render_warmup_button(
            {"ui": {"debug_mode": True}},
            base_url="https://remote.example.com",
        )
        is True
    )


def test_should_render_warmup_button_hidden_for_remote_without_debug() -> None:
    """BL-55: remote ``OLLAMA_BASE_URL`` + ``debug_mode=false`` hides the button."""
    from src.ui.components.sidebar import should_render_warmup_button

    assert (
        should_render_warmup_button(
            {"ui": {"debug_mode": False}},
            base_url="https://remote.example.com",
        )
        is False
    )
    # Empty / missing config behaves the same as debug_mode=false.
    assert (
        should_render_warmup_button(None, base_url="https://remote.example.com")
        is False
    )


def test_should_render_warmup_button_for_localhost_base_url() -> None:
    """BL-55: localhost / 127.0.0.1 make the button visible without debug_mode."""
    from src.ui.components.sidebar import should_render_warmup_button

    for url in (
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "https://localhost",
        "localhost:11434",  # missing scheme — still recognised as local
    ):
        assert (
            should_render_warmup_button({"ui": {"debug_mode": False}}, base_url=url)
            is True
        ), f"{url!r} must be treated as a local Ollama endpoint"


def test_trigger_warmup_posts_expected_payload_to_api_generate(monkeypatch) -> None:
    """BL-55: warmup must hit ``/api/generate`` with the fixed PII-free prompt."""
    from src.ui.components import sidebar

    captured: dict[str, Any] = {}

    class _StubResponse:
        status_code = 200
        ok = True

    def _fake_post(url, json=None, timeout=None, **_kwargs):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _StubResponse()

    result = sidebar.trigger_warmup(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        post=_fake_post,
    )

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"] == {
        "model": "qwen2.5:7b",
        "prompt": "ok",
        "keep_alive": "10m",
    }
    assert captured["timeout"] == sidebar.WARMUP_TIMEOUT_SECONDS
    assert result["ok"] is True
    assert result["status"] == 200


def test_trigger_warmup_reports_failure_without_raising() -> None:
    """BL-55: connection errors must surface as ``ok=False`` not as a traceback."""
    from src.ui.components import sidebar

    def _boom(*_args, **_kwargs):
        raise ConnectionError("connection refused")

    result = sidebar.trigger_warmup(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        post=_boom,
    )
    assert result["ok"] is False
    assert "refused" in (result.get("error") or "").lower()
    assert result["url"].endswith("/api/generate")


def test_render_warmup_button_returns_none_when_hidden() -> None:
    """BL-55: hidden button must short-circuit before touching ``st.button``."""
    from src.ui.components import sidebar

    sentinel_called: list[bool] = []

    def _post(*_args, **_kwargs):
        sentinel_called.append(True)
        return None

    result = sidebar.render_warmup_button(
        {"ui": {"debug_mode": False}},
        base_url="https://remote.example.com",
        post=_post,
        background=False,
    )
    assert result is None
    assert sentinel_called == []


def test_render_warmup_button_triggers_warmup_on_click(monkeypatch) -> None:
    """BL-55: clicking the button calls ``post`` with the warmup payload."""
    import streamlit as st  # noqa: WPS433 — stub injected at import time
    from src.ui.components import sidebar

    monkeypatch.setattr(st, "button", lambda *_a, **_kw: True)
    success_calls: list[str] = []
    monkeypatch.setattr(st, "success", lambda msg: success_calls.append(msg))
    error_calls: list[str] = []
    monkeypatch.setattr(st, "error", lambda msg: error_calls.append(msg))

    posted: dict[str, Any] = {}

    class _StubResponse:
        status_code = 200
        ok = True

    def _post(url, json=None, timeout=None, **_kw):
        posted["url"] = url
        posted["json"] = json
        return _StubResponse()

    result = sidebar.render_warmup_button(
        {"ui": {"debug_mode": True}},
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        post=_post,
        background=False,
    )

    assert result is not None
    assert result["ok"] is True
    assert posted["json"]["prompt"] == "ok"
    assert posted["json"]["keep_alive"] == "10m"
    assert posted["url"] == "http://localhost:11434/api/generate"
    assert success_calls, "Success label must be shown when warmup succeeds"
    assert error_calls == []


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
