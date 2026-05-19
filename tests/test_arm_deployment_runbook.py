from pathlib import Path

import pytest

from src.config_loader import REQUIRED_ENV_VARS, validate_env


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "runbooks" / "arm-deployment-ivan.md"
USER_GUIDE_TROUBLESHOOTING = (
    ROOT / "docs" / "user_guide" / "04_troubleshooting.md"
)
CHANGELOG = ROOT / "CHANGELOG.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, header: str, next_headers: tuple[str, ...]) -> str:
    """Return the slice of ``text`` between ``header`` and the next section.

    Used by BL-53 tests to assert that the cache warning lives inside the
    target scenario (§2 / §6) and not somewhere else in the runbook.
    """
    start = text.index(header)
    end = len(text)
    for candidate in next_headers:
        idx = text.find(candidate, start + len(header))
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


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


def test_runbook_section_2_warns_about_env_yaml_cache() -> None:
    """BL-53 (issue #198): §2 must spell out the full restart checklist.

    Tester report §1.6 / Problem #4 — operator wastes 5–10 minutes
    chasing false errors after editing ``.env`` because Streamlit holds
    ``load_dotenv()`` / ``yaml.safe_load()`` results in memory until the
    process restarts. The runbook must therefore mention BL-53, point
    at both ``.env`` and ``configs/*.yaml``, and prescribe the
    ``Ctrl+C`` → ``streamlit run`` → ``Ctrl+Shift+R`` sequence.
    """
    text = _read(RUNBOOK)
    section_2 = _section(
        text,
        "## 2. Сценарий А: чистая установка",
        ("## 3.",),
    )

    assert "BL-53" in section_2
    assert ".env" in section_2
    assert "configs/*.yaml" in section_2
    assert "Ctrl+C" in section_2
    assert "streamlit run src/ui/app.py" in section_2
    assert "Ctrl+Shift+R" in section_2


def test_runbook_section_6_references_bl53_cache_warning() -> None:
    """BL-53 (issue #198): §6 diagnostic flow must redirect to §2.

    Before chasing «Connection refused» or «неверный ответ LLM», the
    operator must verify that Streamlit was restarted after the last
    ``.env`` / ``configs/*.yaml`` edit — Streamlit ``Rerun`` does not
    re-execute ``load_dotenv()``. The §6 entry must therefore name the
    BL-53 warning explicitly and repeat the restart checklist so the
    tester can find it without scrolling back.
    """
    text = _read(RUNBOOK)
    section_6 = _section(
        text,
        "## 6. Сценарий В: ошибка в UI",
        ("## 7.",),
    )

    assert "BL-53" in section_6
    assert "Rerun" in section_6
    assert "Ctrl+C" in section_6
    assert "streamlit run src/ui/app.py" in section_6
    assert "Ctrl+Shift+R" in section_6


def test_user_guide_troubleshooting_documents_env_yaml_cache() -> None:
    """BL-53 (issue #198): user guide must own the BA-facing version.

    The runbook targets the operator on the ARM; the user guide
    targets the business analyst hitting Streamlit. Both audiences
    need the same checklist, but the user guide also has to debunk
    the «обновил вкладку — должно сработать» assumption explicitly.
    """
    text = _read(USER_GUIDE_TROUBLESHOOTING)

    assert (
        "Изменения в `.env` / `configs/*.yaml` не применяются" in text
    )
    assert "Ctrl+C" in text
    assert "streamlit run src/ui/app.py" in text
    assert "Ctrl+Shift+R" in text
    # The «Rerun не достаточно» explanation is the load-bearing piece
    # of BL-53: without it operators keep retrying Rerun and reporting
    # phantom bugs.
    assert "Rerun" in text


def test_changelog_mentions_bl53_streamlit_cache() -> None:
    """BL-53 (issue #198): CHANGELOG must carry the DOCS marker.

    DoD requires a CHANGELOG entry of the form
    ``DOCS: BL-53 Streamlit .env cache documented`` so future
    contributors can trace the runbook / user guide changes back to
    the pilot report.
    """
    text = _read(CHANGELOG)

    assert "BL-53" in text
    assert "Streamlit" in text
    assert "issue #198" in text
