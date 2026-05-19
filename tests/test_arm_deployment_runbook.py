import sys
from pathlib import Path

import pytest

from src.config_loader import REQUIRED_ENV_VARS, validate_env


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "runbooks" / "arm-deployment-ivan.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_arm_deployment_runbook_exists_and_covers_issue_contract() -> None:
    text = _read(RUNBOOK)

    required_fragments = [
        "Windows CMD",
        "cmd.exe",
        "py -3.14 -m venv venv",
        "venv\\Scripts\\activate",
        "set PYTHONPATH=C:\\Projects\\clarify-engine-ai",
        "streamlit run src/ui/app.py",
        "ollama pull qwen2.5:7b",
        "OLLAMA_TIMEOUT=180",
        "debug_error_details: true",
        "📥 Скачать логи",
        "logs/pipeline.jsonl",
        "chroma_data/",
        "UnicodeDecodeError",
        "No module named 'torchvision'",
        "Read timed out",
    ]
    for fragment in required_fragments:
        assert fragment in text


def test_arm_deployment_runbook_covers_operational_scenarios() -> None:
    text = _read(RUNBOOK)

    scenarios = [
        "Сценарий А: чистая установка",
        "Сценарий Б: запуск после перезагрузки",
        "Сценарий В: ошибка в UI",
        "Сценарий Г: обновление версии",
    ]
    for scenario in scenarios:
        assert scenario in text

    assert "\\\n" not in text, "CMD commands must not use bash-style continuations"


def test_changelog_mentions_bl45_runbook() -> None:
    text = _read(CHANGELOG)

    assert (
        "DOCUMENTATION: BL-45 ARM deployment runbook for Windows CMD + CPU Ollama"
        in text
    )


def test_runbook_mentions_bl50_startup_guard() -> None:
    """BL-50 (issue #194): runbook must point at the startup guard.

    The Notepad → ``.env.txt`` warning has to stay, but the runbook
    should make it clear that the guard now catches that automatically.
    """
    text = _read(RUNBOOK)

    assert "BL-50" in text
    assert "startup-guard" in text or "startup guard" in text
    assert ".env.txt" in text


def test_runbook_documents_bl54_upload_smoke_section() -> None:
    """BL-54 (issue #196): the runbook must describe §2.8 file uploader smoke."""
    text = _read(RUNBOOK)

    required = [
        "2.8",
        "BL-54",
        "📎 Файл тендерного ТЗ",
        "🚀 Запустить анализ",
        "📥 Скачать отчёт",
        "analysis_query_mode",
    ]
    for fragment in required:
        assert fragment in text, f"runbook missing BL-54 fragment: {fragment}"


def test_runbook_section_2_8_executes_automatically(monkeypatch) -> None:
    """Smoke case: BL-54 runbook §2.8 is automatically verifiable.

    Mirrors the manual checklist (uploader visible, format radio
    rendered, run button rendered, download button activates after a
    pipeline run) by driving ``_run_analysis_upload_mode`` against the
    streamlit stub from ``tests.test_ui_modes``.
    """
    # Re-use the streamlit stub bootstrapped by tests/test_ui_modes.py — it
    # already provides every widget the upload flow touches.
    sys.path.insert(0, str(ROOT))
    import tests.test_ui_modes as ui_modes_tests
    from src.ui import app
    import streamlit as st

    st.session_state.clear()
    uploaded = ui_modes_tests._StubUpload("tz.xlsx", data=b"requirements")

    recorded = {
        "file_uploader": [],
        "radio": [],
        "button": [],
        "download_button": [],
    }
    monkeypatch.setattr(
        st,
        "file_uploader",
        lambda *args, **kwargs: (
            recorded["file_uploader"].append((args, kwargs)) or uploaded
        ),
    )

    def _radio(*args, **kwargs):
        recorded["radio"].append((args, kwargs))
        st.session_state[kwargs.get("key", "")] = "xlsx"
        return "xlsx"

    monkeypatch.setattr(st, "radio", _radio)
    monkeypatch.setattr(st, "info", lambda *_a, **_kw: None)
    monkeypatch.setattr(st, "success", lambda *_a, **_kw: None)
    monkeypatch.setattr(st, "warning", lambda *_a, **_kw: None)
    monkeypatch.setattr(st, "error", lambda *_a, **_kw: None)

    # Pretend the user clicked the run button on this render pass.
    button_calls: list = []

    def _button(*args, **kwargs):
        button_calls.append((args, kwargs))
        return len(button_calls) == 1

    monkeypatch.setattr(st, "button", _button)

    def _execute(file, *, output_format):
        st.session_state[app.SESSION_ANALYSIS_LAST_RUN_KEY] = {
            "run_id": "smoke-run",
            "filename": "tz__result_smoke-run.xlsx",
            "report_bytes": b"smoke-report",
            "stats": {"total": 1, "success": 1, "errors": 0, "nd": 0},
            "format": output_format,
            "duration_seconds": 1.0,
        }

    monkeypatch.setattr(app, "_execute_analysis_pipeline", _execute)
    monkeypatch.setattr(
        st,
        "download_button",
        lambda *args, **kwargs: recorded["download_button"].append((args, kwargs)),
    )

    app._run_analysis_upload_mode()

    # §2.8 expectations: file uploader visible.
    assert recorded["file_uploader"], "runbook §2.8: uploader must render"
    uploader_args, _ = recorded["file_uploader"][0]
    assert uploader_args[0] == "📎 Файл тендерного ТЗ"
    # §2.8 expectations: format radio rendered.
    assert recorded["radio"], "runbook §2.8: format radio must render"
    # §2.8 expectations: run button rendered.
    run_button_args = [c for c in button_calls if c[0][0] == "🚀 Запустить анализ"]
    assert run_button_args, "runbook §2.8: «🚀 Запустить анализ» must render"
    # §2.8 expectations: download активен after a successful run.
    assert recorded["download_button"], "runbook §2.8: download must render"
    download_kwargs = recorded["download_button"][0][1]
    assert download_kwargs["disabled"] is False
    assert download_kwargs["file_name"].endswith(".xlsx")


def test_runbook_documents_bl51_ollama_path_guard() -> None:
    """BL-51 (issue #195): runbook must include the ``setx PATH`` step and §6 note.

    Pins three contract points so the ARM regression (Ollama installed under
    ``%LOCALAPPDATA%`` but not on PATH) cannot slip out of the runbook:

    1. §1.4a section header with the ``setx PATH`` command.
    2. Explicit warning that CMD must be restarted for ``setx`` to take effect.
    3. §6 troubleshooting row links ``Connection refused`` to the BL-51 guard.
    """
    text = _read(RUNBOOK)

    assert "1.4a" in text and "BL-51" in text
    assert 'setx PATH "%PATH%;%LOCALAPPDATA%\\Programs\\Ollama"' in text
    assert "перезапустите CMD" in text or "Закройте текущее окно CMD" in text
    assert "BL-51 guard" in text


def test_startup_guard_recreates_env_from_example_after_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke case for the runbook: removing ``.env`` is recoverable.

    Mirrors the runbook scenario "operator deleted ``.env`` accidentally
    after a botched edit" — running the startup guard recreates ``.env``
    from ``.env.example`` so ``streamlit run`` / ``python -m
    src.pipeline`` continue to work without manual ``copy``.
    """
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    (tmp_path / ".env.example").write_text(
        "OLLAMA_MODEL=qwen2.5:7b\nOLLAMA_BASE_URL=http://localhost:11434\n",
        encoding="utf-8",
    )
    assert not (tmp_path / ".env").exists()

    def _loader(_path: Path) -> bool:
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return True

    result = validate_env(project_root=tmp_path, dotenv_loader=_loader)

    assert result.copied_from_example is True
    assert (tmp_path / ".env").exists()
