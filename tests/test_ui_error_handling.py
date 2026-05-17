"""Regression tests for KB UI graceful degradation (BL-13, issue #106)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import pytest


def _ensure_streamlit_stub() -> None:
    """Provide a minimal Streamlit stub before importing ``src.ui.app``."""
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


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_ensure_streamlit_stub()

import streamlit as st  # noqa: E402

from src.llm.client import LLMError  # noqa: E402
from src.ui import app  # noqa: E402


class _Ctx:
    def __enter__(self) -> "_Ctx":
        return self

    def __exit__(self, *_exc: Any) -> Literal[False]:
        return False


def test_retrieve_and_answer_records_generic_error_and_retry_state(monkeypatch) -> None:
    """Provider failures must not leak raw exceptions/prompts into the UI."""
    st.session_state.clear()
    ui_errors: list[str] = []
    log_calls: list[dict[str, Any]] = []

    class FailingClient:
        def generate_rag_response(self, *_args: Any, **_kwargs: Any) -> str:
            raise LLMError("Traceback: provider 500 for raw prompt <question>secret</question>")

    class CapturingLogger:
        def info(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def error(self, *_args: Any, **kwargs: Any) -> None:
            log_calls.append(kwargs.get("extra", {}))

    monkeypatch.setattr(app.st, "error", lambda message: ui_errors.append(message))
    monkeypatch.setattr(app.st, "spinner", lambda *_a, **_kw: _Ctx())
    monkeypatch.setattr(
        app,
        "search_kb",
        lambda _query, _top_k: [{"source": "doc.pdf", "text": "context"}],
    )
    monkeypatch.setattr(app, "get_llm_client", lambda: FailingClient())
    monkeypatch.setattr(app, "get_rag_system_prompt", lambda: "system")
    monkeypatch.setattr(app, "logger", CapturingLogger())

    answer, chunks, prompt = app._retrieve_and_answer(
        query="Как настроить SIP?",
        top_k=1,
        history=None,
        mode=app.MODE_STATELESS,
        run_id="ui-run-123",
    )

    assert answer is None
    assert chunks == [{"source": "doc.pdf", "text": "context"}]
    assert "<question>Как настроить SIP?</question>" in prompt
    assert ui_errors == [app.UI_GENERATION_ERROR_TEXT]
    assert "Traceback" not in ui_errors[0]
    assert "<question>" not in ui_errors[0]
    assert st.session_state[app.SESSION_LAST_QUERY_KEY] == "Как настроить SIP?"
    assert st.session_state[app.SESSION_LAST_ERROR_KEY]["run_id"] == "ui-run-123"
    assert st.session_state[app.SESSION_LAST_ERROR_KEY]["error_type"] == "LLMError"
    assert log_calls[-1]["run_id"] == "ui-run-123"
    assert log_calls[-1]["error_type"] == "LLMError"
    assert log_calls[-1]["provider"]


def test_retry_button_queues_last_query_without_clearing_input(monkeypatch) -> None:
    """The retry button must replay ``last_query`` instead of reading the widget."""
    st.session_state.clear()
    st.session_state[app.SESSION_LAST_QUERY_KEY] = "исходный запрос"
    st.session_state[app.SESSION_LAST_ERROR_KEY] = {
        "mode": app.MODE_STATELESS,
        "message": app.UI_GENERATION_ERROR_TEXT,
        "run_id": "failed-run",
        "error_type": "LLMError",
    }

    class RerunRequested(RuntimeError):
        pass

    monkeypatch.setattr(app.st, "error", lambda *_a, **_kw: None)
    monkeypatch.setattr(app.st, "button", lambda *_a, **_kw: True)
    monkeypatch.setattr(app.st, "rerun", lambda: (_ for _ in ()).throw(RerunRequested()))

    with pytest.raises(RerunRequested):
        app._render_retry_notice(app.MODE_STATELESS)

    assert st.session_state[app.SESSION_LAST_QUERY_KEY] == "исходный запрос"
    assert st.session_state[app.SESSION_PENDING_QUERY_KEY] == "исходный запрос"
    assert st.session_state[app.SESSION_PENDING_MODE_KEY] == app.MODE_STATELESS
    assert st.session_state[app.SESSION_PROCESSING_KEY] is True


def test_run_analysis_mode_disables_controls_while_pending(monkeypatch) -> None:
    """The analysis input and submit button are disabled during processing."""
    st.session_state.clear()
    st.session_state[app.SESSION_PROCESSING_KEY] = True
    st.session_state[app.SESSION_PENDING_MODE_KEY] = app.MODE_STATELESS
    st.session_state[app.SESSION_PENDING_QUERY_KEY] = "queued"

    captured: dict[str, Any] = {}

    class StopAfterWidgets(RuntimeError):
        pass

    def fake_text_area(*_args: Any, **kwargs: Any) -> str:
        captured["text_area_disabled"] = kwargs.get("disabled")
        return "widget value"

    def fake_button(*_args: Any, **kwargs: Any) -> bool:
        captured["button_disabled"] = kwargs.get("disabled")
        return False

    monkeypatch.setattr(app, "_render_analysis_export_button", lambda: None)
    monkeypatch.setattr(app, "_render_retry_notice", lambda _mode: False)
    monkeypatch.setattr(app, "_render_analysis_result", lambda _debug: False)
    monkeypatch.setattr(
        app,
        "_process_pending_analysis",
        lambda _settings: (_ for _ in ()).throw(StopAfterWidgets()),
    )
    monkeypatch.setattr(app.st, "text_area", fake_text_area)
    monkeypatch.setattr(app.st, "button", fake_button)

    with pytest.raises(StopAfterWidgets):
        app._run_analysis_mode(settings={"top_k": 5, "debug": False})

    assert captured == {"text_area_disabled": True, "button_disabled": True}


def test_safe_error_logging_never_breaks_ui(monkeypatch) -> None:
    """Logger failures are isolated from the Streamlit flow."""

    class BrokenLogger:
        def error(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("logging backend is down")

    monkeypatch.setattr(app, "logger", BrokenLogger())

    app._safe_log_ui_error(
        run_id="run-safe",
        mode=app.MODE_STATELESS,
        provider="openrouter",
        exc=LLMError("provider failed"),
    )
