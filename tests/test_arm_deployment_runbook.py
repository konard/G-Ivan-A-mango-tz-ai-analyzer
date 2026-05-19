from pathlib import Path


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
