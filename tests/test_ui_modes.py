"""Tests for the two-mode UI in :mod:`src.ui.app` (BL-07, issue #93).

Covers the contract pinned by the issue:

* `get_max_history_messages` reads `ui.max_history_messages` from
  `configs/llm_config.yaml` (defaults to 6 when missing/malformed).
* `trim_history` keeps **at most** N most recent messages and is a no-op
  when the buffer is already small enough.
* `format_history` produces a `Пользователь:` / `Ассистент:` transcript
  suitable for inlining into the user prompt.
* `build_user_prompt` omits the `<history>` block in stateless mode and
  injects it in consultation mode.
* `_ensure_mode_state` resets `st.session_state.messages` on mode switch.
* `_reset_history` clears the buffer on demand (sidebar button).

These tests reuse the lightweight Streamlit stub from
:mod:`tests.test_citation_links` so they run without a real Streamlit
install.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import ModuleType


def _ensure_streamlit_stub() -> None:
    """Provide a minimal stub for streamlit so :mod:`src.ui.app` can import."""
    stub = sys.modules.get("streamlit")
    if stub is None:
        stub = ModuleType("streamlit")
        sys.modules["streamlit"] = stub

    def _noop(*_args, **_kwargs):
        return None

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def _decorator(*_args, **_kwargs):
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
        stub.session_state = {}
    if not hasattr(stub, "sidebar"):
        stub.sidebar = _Ctx()
    if not hasattr(stub, "expander"):
        stub.expander = lambda *_a, **_kw: _Ctx()
    if not hasattr(stub, "spinner"):
        stub.spinner = lambda *_a, **_kw: _Ctx()
    if not hasattr(stub, "chat_message"):
        stub.chat_message = lambda *_a, **_kw: _Ctx()
    if not hasattr(stub, "cache_resource"):
        stub.cache_resource = _decorator


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_ensure_streamlit_stub()

import streamlit as st  # noqa: E402

from src.ui import app  # noqa: E402


# ----------------------------------------------------- max_history_messages --
def test_get_max_history_messages_defaults_to_six() -> None:
    assert app.get_max_history_messages({}) == 6
    assert app.get_max_history_messages({"ui": {}}) == 6


def test_get_max_history_messages_reads_config() -> None:
    assert app.get_max_history_messages({"ui": {"max_history_messages": 4}}) == 4
    assert app.get_max_history_messages({"ui": {"max_history_messages": 0}}) == 0


def test_get_max_history_messages_clamps_negative_and_malformed() -> None:
    assert app.get_max_history_messages({"ui": {"max_history_messages": -3}}) == 0
    assert app.get_max_history_messages({"ui": {"max_history_messages": "n/a"}}) == 6
    assert app.get_max_history_messages({"ui": "not-a-dict"}) == 6


def test_get_max_history_messages_reads_default_from_llm_config() -> None:
    """The shipped `configs/llm_config.yaml` must define `ui.max_history_messages = 6`."""
    config = app.load_llm_config()
    assert config.get("ui", {}).get("max_history_messages") == 6
    assert app.get_max_history_messages(config) == 6


def test_embedding_config_hash_tracks_file_bytes(tmp_path: Path) -> None:
    config_path = tmp_path / "embedding_config.yaml"
    config_path.write_bytes(b"model_name: test-model\n")

    first_hash = app.embedding_config_hash(config_path)
    assert first_hash == hashlib.md5(b"model_name: test-model\n").hexdigest()

    config_path.write_bytes(b"model_name: changed-model\n")
    second_hash = app.embedding_config_hash(config_path)

    assert second_hash == hashlib.md5(b"model_name: changed-model\n").hexdigest()
    assert second_hash != first_hash


# ------------------------------------------------------------- multi-hop cfg --
def test_resolve_multi_hop_settings_defaults_to_disabled() -> None:
    settings = app.resolve_multi_hop_settings({}, app.MODE_CONSULTATION)
    assert settings == {
        "enabled": False,
        "max_hops": 2,
        "min_confidence_to_stop": 0.8,
    }


def test_resolve_multi_hop_settings_hard_locks_analysis_mode() -> None:
    config = {
        "rag": {
            "multi_hop_enabled": True,
            "max_hops": 3,
            "min_confidence_to_stop": 0.6,
        }
    }
    settings = app.resolve_multi_hop_settings(config, app.MODE_STATELESS)
    assert settings["enabled"] is False
    assert settings["max_hops"] == 3
    assert settings["min_confidence_to_stop"] == 0.6


def test_resolve_multi_hop_settings_enables_only_consultation_mode() -> None:
    config = {
        "rag": {
            "multi_hop_enabled": True,
            "max_hops": 2,
            "min_confidence_to_stop": 0.9,
        }
    }
    settings = app.resolve_multi_hop_settings(config, app.MODE_CONSULTATION)
    assert settings["enabled"] is True
    assert settings["max_hops"] == 2
    assert settings["min_confidence_to_stop"] == 0.9


def test_shipped_llm_config_multi_hop_defaults_to_disabled() -> None:
    config = app.load_llm_config()
    settings = app.resolve_multi_hop_settings(config, app.MODE_CONSULTATION)
    assert settings["enabled"] is False


def test_search_vector_store_passes_query_arguments(monkeypatch) -> None:
    captured = {}
    chunks = [{"source": "doc.md", "text": "context", "score": 1.0}]

    class _Retriever:
        collection_name = "kb"
        persist_directory = "/tmp/chroma"
        config = {"query_expansion": {"enabled": False}}

        def search(self, query, *, top_k, use_parent_context=False):
            captured["query"] = query
            captured["top_k"] = top_k
            captured["use_parent_context"] = use_parent_context
            return chunks

    monkeypatch.setattr(app, "get_retriever", lambda *_args, **_kwargs: _Retriever())

    assert app.search_vector_store(
        "Как настроить SIP?",
        top_k=3,
        use_parent_context=False,
    ) == chunks
    assert captured == {
        "query": "Как настроить SIP?",
        "top_k": 3,
        "use_parent_context": False,
    }


# ---------------------------------------------------------------- trim_history --
def test_trim_history_keeps_last_n_messages() -> None:
    msgs = [{"role": "user", "content": str(i)} for i in range(10)]
    trimmed = app.trim_history(msgs, 6)
    assert len(trimmed) == 6
    assert [m["content"] for m in trimmed] == ["4", "5", "6", "7", "8", "9"]


def test_trim_history_is_noop_when_small() -> None:
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    assert app.trim_history(msgs, 6) == msgs


def test_trim_history_zero_or_negative_returns_empty() -> None:
    msgs = [{"role": "user", "content": "a"}]
    assert app.trim_history(msgs, 0) == []
    assert app.trim_history(msgs, -1) == []


def test_trim_history_does_not_mutate_input() -> None:
    msgs = [{"role": "user", "content": str(i)} for i in range(8)]
    snapshot = list(msgs)
    app.trim_history(msgs, 3)
    assert msgs == snapshot


# --------------------------------------------------------------- format_history --
def test_format_history_uses_russian_role_labels() -> None:
    rendered = app.format_history(
        [
            {"role": "user", "content": "Что такое SIP trunk?"},
            {"role": "assistant", "content": "Это виртуальный канал…"},
        ]
    )
    assert rendered == (
        "Пользователь: Что такое SIP trunk?\n"
        "Ассистент: Это виртуальный канал…"
    )


def test_format_history_skips_empty_messages() -> None:
    rendered = app.format_history(
        [
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": "Ответ"},
            {"role": "user", "content": ""},
        ]
    )
    assert rendered == "Ассистент: Ответ"


def test_format_history_handles_unknown_role() -> None:
    rendered = app.format_history([{"role": "system", "content": "ping"}])
    # Unknown roles default to «Пользователь» so the LLM still sees the line
    # — better than dropping it silently.
    assert rendered == "Пользователь: ping"


# -------------------------------------------------------------- build_user_prompt --
def _sample_chunks() -> list:
    return [
        {"source": "doc.pdf", "text": "Контент 1", "chunk_idx": 0},
        {"source": "doc.pdf", "text": "Контент 2", "chunk_idx": 1},
    ]


def test_build_user_prompt_omits_history_block_in_stateless_mode() -> None:
    prompt = app.build_user_prompt("Что такое X?", _sample_chunks())
    assert "<history>" not in prompt
    assert "<context>" in prompt
    assert "<question>Что такое X?</question>" in prompt


def test_build_user_prompt_omits_history_block_when_history_empty() -> None:
    prompt = app.build_user_prompt("Q", _sample_chunks(), history=[])
    assert "<history>" not in prompt


def test_build_user_prompt_injects_history_when_provided() -> None:
    history = [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуйте!"},
    ]
    prompt = app.build_user_prompt("Что дальше?", _sample_chunks(), history=history)
    assert "<history>" in prompt
    assert "Пользователь: Привет" in prompt
    assert "Ассистент: Здравствуйте!" in prompt
    # Order matters: context → history → question.
    assert prompt.index("<context>") < prompt.index("<history>") < prompt.index("<question>")


# ----------------------------------------------------- estimate_token_count --
def test_estimate_token_count_is_proportional_to_length() -> None:
    assert app.estimate_token_count("") == 0
    short = app.estimate_token_count("abcd")
    long = app.estimate_token_count("abcd" * 100)
    assert short >= 1
    assert long > short
    assert long == len("abcd" * 100) // app.TOKEN_CHAR_RATIO


# ------------------------------------------------------- mode-switch reset --
def test_ensure_mode_state_resets_history_on_switch() -> None:
    st.session_state.clear()
    st.session_state["messages"] = [{"role": "user", "content": "prev"}]
    st.session_state["ui_mode"] = app.MODE_CONSULTATION

    app._ensure_mode_state(app.MODE_STATELESS)
    assert st.session_state["ui_mode"] == app.MODE_STATELESS
    assert st.session_state["messages"] == []


def test_ensure_mode_state_keeps_history_when_mode_unchanged() -> None:
    st.session_state.clear()
    st.session_state["messages"] = [{"role": "user", "content": "keep"}]
    st.session_state["ui_mode"] = app.MODE_CONSULTATION

    app._ensure_mode_state(app.MODE_CONSULTATION)
    assert st.session_state["messages"] == [{"role": "user", "content": "keep"}]


def test_ensure_mode_state_initialises_messages_when_missing() -> None:
    st.session_state.clear()
    app._ensure_mode_state(app.MODE_CONSULTATION)
    assert st.session_state["messages"] == []
    assert st.session_state["ui_mode"] == app.MODE_CONSULTATION


def test_reset_history_clears_buffer() -> None:
    st.session_state.clear()
    st.session_state["messages"] = [{"role": "user", "content": "a"}]
    app._reset_history()
    assert st.session_state["messages"] == []


# --------------------------------------------------------------- export UI --
def test_build_analysis_export_row_uses_allowed_columns_only() -> None:
    row = app._build_analysis_export_row(
        "Q",
        "A",
        [{"source": "doc.pdf"}, {"source": "doc.pdf"}, {"source": "other.pdf"}],
    )
    assert row == {
        "id": 1,
        "Исходное требование": "Q",
        "[Статус]": "НД",
        "[Комментарий]": "A",
        "[Confidence]": 0.0,
        "[RunID]": "",
        "locator": {"type": "ui_query"},
        "ref": "doc.pdf; other.pdf",
    }


def test_analysis_export_button_disabled_without_rows(monkeypatch) -> None:
    calls = []
    radio_calls = []
    st.session_state.clear()

    monkeypatch.setattr(st, "download_button", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(st, "radio", lambda *args, **kwargs: radio_calls.append((args, kwargs)))

    app._render_analysis_export_button()

    assert st.session_state[app.SESSION_EXPORT_FORMAT_KEY] == "xlsx"
    assert radio_calls
    assert radio_calls[0][1]["disabled"] is True
    assert calls
    assert calls[0][0][0] == "📥 Скачать отчет (.xlsx)"
    assert calls[0][1]["disabled"] is True


def test_analysis_export_button_uses_selected_router_format(monkeypatch) -> None:
    calls = []
    st.session_state.clear()
    st.session_state[app.SESSION_EXPORT_FORMAT_KEY] = "md"
    st.session_state["analysis_export_rows"] = [
        {
            "id": 1,
            "Исходное требование": "Q",
            "[Статус]": "НД",
            "[Комментарий]": "A",
            "[Confidence]": 0.0,
            "[RunID]": "run-12345678",
            "locator": {"type": "ui_query"},
            "ref": "doc.pdf",
        }
    ]

    monkeypatch.setattr(st, "radio", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "download_button", lambda *args, **kwargs: calls.append((args, kwargs)))

    app._render_analysis_export_button()

    assert calls
    assert calls[0][0][0] == "📥 Скачать отчет (.md)"
    assert calls[0][1]["file_name"].endswith(".md")
    assert calls[0][1]["mime"] == "text/markdown; charset=utf-8"
    assert b"Q" in calls[0][1]["data"].getvalue()
    assert calls[0][1]["disabled"] is False


def test_analysis_export_button_shows_friendly_router_error(monkeypatch) -> None:
    calls = []
    errors = []
    st.session_state.clear()
    st.session_state[app.SESSION_EXPORT_FORMAT_KEY] = "docx"
    st.session_state["analysis_export_rows"] = [
        {
            "id": 1,
            "Исходное требование": "Q",
            "[Статус]": "unexpected",
            "[Комментарий]": "A",
            "[Confidence]": 0.0,
            "[RunID]": "run-12345678",
        }
    ]

    monkeypatch.setattr(st, "radio", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(st, "error", lambda message: errors.append(message))
    monkeypatch.setattr(st, "download_button", lambda *args, **kwargs: calls.append((args, kwargs)))

    app._render_analysis_export_button()

    assert errors
    assert errors[0].startswith("Ошибка генерации файла:")
    assert calls[0][0][0] == "📥 Скачать отчет (.docx)"
    assert calls[0][1]["disabled"] is True


def test_chat_export_button_enabled_with_history(monkeypatch) -> None:
    calls = []
    st.session_state.clear()
    st.session_state["messages"] = [{"role": "user", "content": "hello@example.com"}]

    monkeypatch.setattr(st, "download_button", lambda *args, **kwargs: calls.append((args, kwargs)))

    app._render_chat_export_button()

    assert calls
    assert calls[0][0][0] == "📥 Сохранить диалог (.md)"
    assert calls[0][1]["disabled"] is False
    assert b"[EMAIL]" in calls[0][1]["data"].getvalue()


# ---------------------------------------------------------- mode constants --
def test_mode_constants_match_issue_spec() -> None:
    """Sidebar labels must match the issue verbatim (emoji included)."""
    assert app.MODE_LABELS[app.MODE_STATELESS] == "📊 Анализ ТЗ"
    assert app.MODE_LABELS[app.MODE_CONSULTATION] == "💬 Консультация по документации"
    assert app.MODE_ORDER == [app.MODE_STATELESS, app.MODE_CONSULTATION]


# ------------------------------------------------- BL-48.6 retrieval slider --
def test_get_retrieval_settings_reads_shipped_ui_config() -> None:
    """The orchestrator must resolve the BL-48.6 slider contract from disk."""
    settings = app.get_retrieval_settings()
    assert settings["top_k_min"] == 1
    assert settings["top_k_max"] == 20
    assert settings["top_k_default"] == 5
    assert settings["top_k_production_max"] == 10
    assert "чанк" not in settings["label"].lower()
    assert "КАЖДОГО" in settings["tooltip"]


def test_get_retrieval_settings_accepts_inline_override() -> None:
    settings = app.get_retrieval_settings(
        {"ui": {"retrieval": {"top_k_max": 12, "top_k_default": 6}}}
    )
    assert settings["top_k_max"] == 12
    assert settings["top_k_default"] == 6


def test_render_sidebar_forwards_retrieval_settings(monkeypatch) -> None:
    """Slider config flows through ``app.render_sidebar`` into the component."""
    captured: dict = {}

    def _fake_component(
        retriever_info,
        *,
        max_history_messages,
        env_path,
        retrieval_settings,
    ):
        captured["retrieval_settings"] = retrieval_settings
        captured["env_path"] = env_path
        captured["max_history_messages"] = max_history_messages
        return {"mode": app.MODE_STATELESS, "debug": False, "top_k": 5, "clear_history": False}

    monkeypatch.setattr(app, "_render_sidebar_component", _fake_component)

    override = {
        "top_k_min": 1,
        "top_k_max": 14,
        "top_k_default": 7,
        "top_k_production_max": 9,
        "label": "L",
        "help": "H",
        "tooltip": "T",
        "warning_template": "⚠️ {limit}",
    }
    app.render_sidebar(
        None,
        max_history_messages=6,
        retrieval_settings=override,
    )
    assert captured["retrieval_settings"] == override
    assert captured["max_history_messages"] == 6


def test_search_kb_wraps_parent_context_after_child_retrieval(monkeypatch) -> None:
    class _Retriever:
        collection_name = "kb"
        persist_directory = "/tmp/chroma"
        parent_context_max_chars = 1000

        def __init__(self) -> None:
            self.calls = []

        def search(self, query, **kwargs):
            self.calls.append((query, kwargs))
            return [
                {
                    "text": "child one",
                    "source": "doc.md",
                    "score": 0.9,
                    "metadata": {
                        "parent_id": "doc.md::section",
                        "parent_text": "Parent section text",
                        "chunk_idx": 1,
                    },
                },
                {
                    "text": "child two",
                    "source": "doc.md",
                    "score": 0.8,
                    "metadata": {
                        "parent_id": "doc.md::section",
                        "parent_text": "Parent section text",
                        "chunk_idx": 2,
                    },
                },
            ]

    retriever = _Retriever()
    monkeypatch.setattr(app, "get_retriever", lambda *_args, **_kwargs: retriever)

    chunks = app.search_kb(
        "Q",
        5,
        use_parent_context=True,
        ui_mode=app.MODE_CONSULTATION,
        llm_config={"rag": {"multi_hop_enabled": False}},
        enable_query_expansion=False,
    )

    assert retriever.calls == [
        ("Q", {"use_parent_context": False, "top_k": 5}),
    ]
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Parent section text"
    assert chunks[0]["metadata"]["parent_context"] is True


def test_retrieve_and_answer_enables_parent_context_for_consultation(monkeypatch) -> None:
    captured = {}

    class _Client:
        def generate_rag_response(self, *_args, **_kwargs):
            return "answer"

    def _search(
        query,
        top_k,
        *,
        use_parent_context=False,
        ui_mode=app.MODE_STATELESS,
        llm_config=None,
        enable_query_expansion=False,
    ):
        captured["use_parent_context"] = use_parent_context
        captured["ui_mode"] = ui_mode
        captured["multi_hop"] = app.resolve_multi_hop_settings(
            llm_config or {}, ui_mode
        )["enabled"]
        captured["enable_query_expansion"] = enable_query_expansion
        return [{"source": "doc.md", "text": "context", "score": 1.0}]

    monkeypatch.setattr(app, "search_kb", _search)
    monkeypatch.setattr(
        app,
        "load_llm_config",
        lambda: {"rag": {"multi_hop_enabled": True}},
    )
    monkeypatch.setattr(app, "get_llm_client", lambda: _Client())
    monkeypatch.setattr(app, "get_rag_system_prompt", lambda: "system")
    monkeypatch.setattr(app, "_safe_log_prompt_built", lambda **_kwargs: None)

    answer, chunks, prompt = app._retrieve_and_answer(
        query="Q",
        top_k=5,
        history=[],
        mode=app.MODE_CONSULTATION,
        run_id="run",
    )

    assert answer == "answer"
    assert chunks
    assert "<context>" in prompt
    assert captured["use_parent_context"] is True
    assert captured["ui_mode"] == app.MODE_CONSULTATION
    assert captured["multi_hop"] is True
    assert captured["enable_query_expansion"] is True
    assert app.DEFAULT_MAX_HISTORY_MESSAGES == 6


def test_retrieve_and_answer_ignores_multi_hop_in_analysis_mode(monkeypatch) -> None:
    captured = {}

    class _Client:
        def generate_rag_response(self, *_args, **_kwargs):
            return "answer"

    def _search(
        query,
        top_k,
        *,
        use_parent_context=False,
        ui_mode=app.MODE_STATELESS,
        llm_config=None,
        enable_query_expansion=False,
    ):
        captured["use_parent_context"] = use_parent_context
        captured["ui_mode"] = ui_mode
        captured["multi_hop"] = app.resolve_multi_hop_settings(
            llm_config or {}, ui_mode
        )["enabled"]
        captured["enable_query_expansion"] = enable_query_expansion
        return [{"source": "doc.md", "text": "context", "score": 1.0}]

    monkeypatch.setattr(app, "search_kb", _search)
    monkeypatch.setattr(
        app,
        "load_llm_config",
        lambda: {"rag": {"multi_hop_enabled": True}},
    )
    monkeypatch.setattr(app, "get_llm_client", lambda: _Client())
    monkeypatch.setattr(app, "get_rag_system_prompt", lambda: "system")
    monkeypatch.setattr(app, "_safe_log_prompt_built", lambda **_kwargs: None)

    answer, chunks, prompt = app._retrieve_and_answer(
        query="Q",
        top_k=5,
        history=None,
        mode=app.MODE_STATELESS,
        run_id="run",
    )

    assert answer == "answer"
    assert chunks
    assert "<history>" not in prompt
    assert captured["use_parent_context"] is False
    assert captured["ui_mode"] == app.MODE_STATELESS
    assert captured["multi_hop"] is False
    assert "<context>" in prompt
    assert captured["enable_query_expansion"] is False
