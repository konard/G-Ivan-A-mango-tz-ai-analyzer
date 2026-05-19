"""BL-50 (issue #194) startup ``.env`` validation contract tests.

Covers the three scenarios listed in the issue DoD:

(a) ``.env.txt`` present, ``.env`` absent → fail with hint about ``ren``
    (no silent rename allowed).
(b) Only ``.env.example`` present → ``.env`` is bootstrapped and the
    declared variables become available.
(c) ``.env`` exists but ``OLLAMA_MODEL`` is empty → fail with hint.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

import pytest

from src.config_loader import (
    EnvValidationError,
    EnvValidationResult,
    REQUIRED_ENV_VARS,
    validate_env,
)


def _make_loader(values: dict[str, str]) -> Callable[[Path], bool]:
    """Stand-in for ``python-dotenv`` that writes ``values`` into ``os.environ``."""

    def _loader(_path: Path) -> bool:
        for key, value in values.items():
            os.environ[key] = value
        return True

    return _loader


@pytest.fixture(autouse=True)
def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_env_txt_without_env_raises_with_rename_hint(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / ".env.txt").write_text(
        "OLLAMA_MODEL=qwen2.5:7b\n", encoding="utf-8"
    )

    with caplog.at_level(logging.ERROR, logger="src.config_loader"):
        with pytest.raises(EnvValidationError) as excinfo:
            validate_env(project_root=tmp_path, dotenv_loader=_make_loader({}))

    message = str(excinfo.value)
    assert ".env.txt" in message
    assert "ren .env.txt .env" in message
    assert any("ren .env.txt .env" in record.message for record in caplog.records)
    # No silent rename — both files must remain on disk.
    assert (tmp_path / ".env.txt").exists()
    assert not (tmp_path / ".env").exists()


def test_only_env_example_creates_env_and_loads_variables(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    example = tmp_path / ".env.example"
    example.write_text(
        "OLLAMA_MODEL=qwen2.5:7b\nOLLAMA_BASE_URL=http://localhost:11434\n",
        encoding="utf-8",
    )

    loader = _make_loader(
        {
            "OLLAMA_MODEL": "qwen2.5:7b",
            "OLLAMA_BASE_URL": "http://localhost:11434",
        }
    )

    with caplog.at_level(logging.INFO, logger="src.config_loader"):
        result = validate_env(project_root=tmp_path, dotenv_loader=loader)

    assert isinstance(result, EnvValidationResult)
    assert result.copied_from_example is True
    assert result.env_path == tmp_path / ".env"
    assert result.env_path.exists()
    assert result.env_path.read_text(encoding="utf-8") == example.read_text(
        encoding="utf-8"
    )
    assert os.environ["OLLAMA_MODEL"] == "qwen2.5:7b"
    assert os.environ["OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert any(
        "Создан .env из .env.example" in record.message for record in caplog.records
    )


def test_empty_required_variable_raises_with_actionable_hint(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OLLAMA_MODEL=\nOLLAMA_BASE_URL=http://localhost:11434\n",
        encoding="utf-8",
    )

    loader = _make_loader(
        {"OLLAMA_MODEL": "", "OLLAMA_BASE_URL": "http://localhost:11434"}
    )

    with caplog.at_level(logging.ERROR, logger="src.config_loader"):
        with pytest.raises(EnvValidationError) as excinfo:
            validate_env(project_root=tmp_path, dotenv_loader=loader)

    message = str(excinfo.value)
    assert "OLLAMA_MODEL" in message
    assert ".env.example" in message
    assert "04_troubleshooting.md" in message
    assert any("OLLAMA_MODEL" in record.message for record in caplog.records)


def test_missing_env_and_example_raises(tmp_path: Path) -> None:
    with pytest.raises(EnvValidationError) as excinfo:
        validate_env(project_root=tmp_path, dotenv_loader=_make_loader({}))

    assert ".env.example" in str(excinfo.value)


def test_existing_env_is_used_when_variables_already_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text(
        "OLLAMA_MODEL=qwen2.5:7b\nOLLAMA_BASE_URL=http://localhost:11434\n",
        encoding="utf-8",
    )
    # Simulate ``.env`` already loaded into the parent process: the loader
    # itself is a no-op but variables are present in os.environ.
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    result = validate_env(
        project_root=tmp_path,
        dotenv_loader=lambda _path: True,
    )

    assert result.copied_from_example is False
    assert result.env_path == tmp_path / ".env"
