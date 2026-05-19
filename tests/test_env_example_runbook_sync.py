"""Regression tests for BL-52 Ollama model drift."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"
RUNBOOK = ROOT / "docs" / "runbooks" / "arm-deployment-ivan.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_assignment(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=([^\s#]+)", text, flags=re.MULTILINE)
    assert match is not None, f"{name} assignment not found"
    return match.group(1)


def test_env_example_ollama_model_matches_runbook_model_and_pull_command() -> None:
    env_model = _extract_assignment(_read(ENV_EXAMPLE), "OLLAMA_MODEL")
    runbook_text = _read(RUNBOOK)
    runbook_model = _extract_assignment(runbook_text, "OLLAMA_MODEL")
    pull_match = re.search(r"^ollama pull ([^\s`]+)", runbook_text, flags=re.MULTILINE)
    assert pull_match is not None, "runbook ollama pull command not found"

    assert env_model == runbook_model == pull_match.group(1)


def test_env_example_documents_ollama_pull_sync_contract() -> None:
    text = _read(ENV_EXAMPLE)

    assert "arm-deployment-ivan.md" in text
    assert "ollama pull" in text
