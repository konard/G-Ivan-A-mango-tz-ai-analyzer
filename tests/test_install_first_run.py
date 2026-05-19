from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts" / "install" / "clarify-setup.py"


spec = importlib.util.spec_from_file_location("clarify_setup", INSTALLER_PATH)
assert spec is not None and spec.loader is not None
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


def _seed_project(tmp_path: Path) -> Path:
    (tmp_path / ".env.example").write_text(
        "OLLAMA_MODEL=qwen2.5:7b\nOLLAMA_BASE_URL=http://localhost:11434\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


def _ctx(tmp_path: Path, runner=None, prompt=lambda _q: "n"):
    return installer.InstallContext(
        project_root=_seed_project(tmp_path),
        dry_run=True,
        runner=runner or (lambda command, cwd, dry_run: installer.CommandResult(command, skipped=dry_run)),
        prompt=prompt,
    )


def _read_events(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (root / "logs" / "install.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_fresh_project_creates_directories_env_and_structured_log(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)

    installer.ensure_directories(ctx)
    assert installer.ensure_env_file(ctx) == "CREATED"

    for relative in installer.DIRECTORIES:
        assert (tmp_path / relative).is_dir()
    assert (tmp_path / ".env").read_text(encoding="utf-8").startswith("OLLAMA_MODEL=qwen2.5:7b")

    events = _read_events(tmp_path)
    assert {event["step"] for event in events} >= {"directories", "env"}
    assert all("duration_s" in event and "status" in event for event in events)


def test_existing_env_is_not_overwritten_on_rerun(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("OLLAMA_MODEL=custom\nSECRET_TOKEN=keep-me\n", encoding="utf-8")

    assert installer.ensure_env_file(ctx) == "EXISTS"

    assert env_path.read_text(encoding="utf-8") == "OLLAMA_MODEL=custom\nSECRET_TOKEN=keep-me\n"


def test_env_txt_without_env_raises_actionable_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    (tmp_path / ".env.txt").write_text("OLLAMA_MODEL=qwen2.5:7b\n", encoding="utf-8")

    try:
        installer.ensure_env_file(ctx)
    except installer.InstallError as exc:
        assert exc.code == "ENV_TXT_FOUND"
        assert "ren .env.txt .env" in str(exc)
    else:
        raise AssertionError("Expected .env.txt to stop the installer")


def test_mocked_ollama_missing_model_records_declined_branch(tmp_path: Path, monkeypatch) -> None:
    commands: list[Sequence[str]] = []

    def runner(command: Sequence[str], cwd: Path, dry_run: bool):
        commands.append(command)
        if command[-1] == "list":
            return installer.CommandResult(command, stdout="NAME ID SIZE MODIFIED\n")
        return installer.CommandResult(command, stdout="ollama version 0.3.10\n")

    fake_ollama = tmp_path / "ollama.exe"
    fake_ollama.write_text("", encoding="utf-8")
    monkeypatch.setattr(installer, "resolve_ollama_binary", lambda env=None: fake_ollama)
    ctx = _ctx(tmp_path, runner=runner, prompt=lambda _q: "n")

    assert installer.check_ollama(ctx) == "MODEL_MISSING_USER_DECLINED"

    assert not any("pull" in command for command in commands)
    events = _read_events(tmp_path)
    assert events[-1]["step"] == "ollama"
    assert events[-1]["status"] == "MODEL_MISSING_USER_DECLINED"


def test_rerun_marks_existing_directories_and_env_as_existing(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)

    installer.ensure_directories(ctx)
    installer.ensure_env_file(ctx)
    statuses = installer.ensure_directories(ctx)
    env_status = installer.ensure_env_file(ctx)

    assert env_status == "EXISTS"
    assert all(status == "EXISTS" for _path, status in statuses)


def test_log_redacts_secret_details(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)

    installer.write_install_event(
        ctx,
        "env",
        "OK",
        details={"OPENROUTER_API_KEY": "real-key", "nested": {"CLIENT_SECRET": "real-secret"}},
    )

    log_text = (tmp_path / "logs" / "install.jsonl").read_text(encoding="utf-8")
    assert "real-key" not in log_text
    assert "real-secret" not in log_text
    assert "***REDACTED***" in log_text


def test_cmd_wrapper_invokes_python_script_and_forwards_arguments() -> None:
    wrapper = (ROOT / "scripts" / "install" / "clarify-setup.cmd").read_text(
        encoding="utf-8"
    )

    assert 'py -3.14 "%SCRIPT_DIR%clarify-setup.py"' in wrapper
    assert "%* --project-root" in wrapper
