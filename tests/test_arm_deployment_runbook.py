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


def test_runbook_mentions_bl55_first_response_latency() -> None:
    """BL-55 (issue #199): runbook §1 wording must stay in sync with spinner text.

    The user-facing spinner says «Первый ответ на CPU может занять 60–90 сек.»
    — the runbook is the authoritative source for that number, so it must
    contain the same «60–90 сек» phrasing (with the en-dash) and reference
    the BL-55 warmup button so operators know about both controls.
    """
    text = _read(RUNBOOK)

    assert "60–90" in text, (
        "Runbook must use the en-dash form '60–90' that matches the spinner "
        "text shipped in src/ui/constants.py (BL-55)."
    )
    assert "BL-55" in text
    assert "🔥 Прогреть модель" in text


def test_runbook_mentions_bl50_startup_guard() -> None:
    """BL-50 (issue #194): runbook must point at the startup guard.

    The Notepad → ``.env.txt`` warning has to stay, but the runbook
    should make it clear that the guard now catches that automatically.
    """
    text = _read(RUNBOOK)

    assert "BL-50" in text
    assert "startup-guard" in text or "startup guard" in text
    assert ".env.txt" in text


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
