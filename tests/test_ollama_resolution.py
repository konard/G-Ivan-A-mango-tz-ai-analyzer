"""Unit tests for BL-51 ``_resolve_ollama_executable`` (issue #195).

The contract is described in
``docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`` §4.3 and the
ARM runbook §1.4a. These tests pin the three deterministic branches so the
ARM regression (Ollama installed under ``%LOCALAPPDATA%`` but not on PATH)
stays caught by CI rather than by a tester on a fresh АРМ.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import pytest

import src.llm.client as client


@pytest.fixture(autouse=True)
def _reset_one_shot_logging_guard() -> None:
    """Clear the module-level "already logged" flag between tests."""
    client._ollama_executable_logged = False
    yield
    client._ollama_executable_logged = False


def test_resolve_falls_back_to_local_appdata_when_not_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``shutil.which`` miss + Windows default install path present → use it."""
    expected = os.path.expanduser(
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    )

    def fake_which(name: str) -> Optional[str]:
        assert name == "ollama"
        return None

    def fake_isfile(path: str) -> bool:
        return path == expected

    resolved = client._resolve_ollama_executable(
        which=fake_which,
        path_exists=fake_isfile,
    )

    assert resolved == expected


def test_resolve_returns_path_lookup_when_which_finds_executable() -> None:
    """``shutil.which`` hit short-circuits the Windows fallback search."""

    def fake_which(name: str) -> Optional[str]:
        assert name == "ollama"
        return "/usr/bin/ollama"

    def fake_isfile(_path: str) -> bool:  # pragma: no cover - must not be called
        raise AssertionError("path_exists must not be consulted when which() hits")

    resolved = client._resolve_ollama_executable(
        which=fake_which,
        path_exists=fake_isfile,
    )

    assert resolved == "/usr/bin/ollama"


def test_resolve_raises_with_instruction_when_neither_source_finds_it() -> None:
    """Both PATH and Windows fallbacks empty → deterministic, actionable error."""

    def fake_which(_name: str) -> Optional[str]:
        return None

    def fake_isfile(_path: str) -> bool:
        return False

    with pytest.raises(RuntimeError) as excinfo:
        client._resolve_ollama_executable(
            which=fake_which,
            path_exists=fake_isfile,
        )

    message = str(excinfo.value)
    assert "setx PATH" in message
    assert r"%LOCALAPPDATA%\Programs\Ollama" in message
    assert "docs/runbooks/arm-deployment-ivan.md" in message


def test_log_once_records_resolved_path_at_info(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_log_ollama_executable_once`` emits a single INFO line with the path."""
    monkeypatch.setattr(client, "_resolve_ollama_executable", lambda: "/usr/bin/ollama")

    with caplog.at_level(logging.INFO, logger="src.llm.client"):
        client._log_ollama_executable_once()
        client._log_ollama_executable_once()

    matching = [r for r in caplog.records if "Ollama executable resolved" in r.message]
    assert len(matching) == 1, "BL-51: executable path must be logged exactly once"
    assert "/usr/bin/ollama" in matching[0].getMessage()


def test_log_once_warns_but_does_not_raise_when_executable_missing(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing executable must not break the HTTP call path — warn only."""

    def _raise() -> str:
        raise RuntimeError(client._OLLAMA_NOT_FOUND_MESSAGE)

    monkeypatch.setattr(client, "_resolve_ollama_executable", _raise)

    with caplog.at_level(logging.WARNING, logger="src.llm.client"):
        client._log_ollama_executable_once()

    matching = [
        r
        for r in caplog.records
        if "Ollama executable lookup failed" in r.message
    ]
    assert matching, "Lookup failure must surface as a warning, not an exception"
