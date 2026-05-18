import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.client import _provider_timeout  # noqa: E402


def test_provider_timeout_reads_config_timeout(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT", "240")

    assert _provider_timeout({"timeout": 90}, 30) == 90


def test_provider_timeout_reads_config_timeout_seconds(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_TIMEOUT", "240")

    assert _provider_timeout({"timeout_seconds": "${OLLAMA_TIMEOUT:180}"}, 30) == 180


def test_provider_timeout_reads_provider_env(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)
    monkeypatch.setenv("PROVIDER_TIMEOUT", "75")

    assert _provider_timeout({}, 30) == 75


def test_provider_timeout_provider_specific_env_wins(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT", "180")
    monkeypatch.setenv("PROVIDER_TIMEOUT", "75")
    monkeypatch.setenv("LLM_PROVIDER_TIMEOUT", "60")

    assert _provider_timeout({}, 30) == 180


def test_provider_timeout_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)
    monkeypatch.delenv("PROVIDER_TIMEOUT", raising=False)
    monkeypatch.delenv("LLM_PROVIDER_TIMEOUT", raising=False)

    assert _provider_timeout({}, 30) == 30


def test_provider_timeout_invalid_values_fall_back(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_TIMEOUT", "not-an-int")

    assert _provider_timeout({"timeout": "also-not-an-int"}, 30) == 30
