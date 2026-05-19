"""First-run installer wizard for Windows ARM workstations (BL-48).

The script is Windows-first, but the core contract is intentionally pure
Python and injectable so CI can test it without running pip, venv, or
Ollama. Heavy external operations are isolated in small helpers and can
be skipped with ``--dry-run``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence


DEFAULT_MODEL = "qwen2.5:7b"
STREAMLIT_URL = "http://localhost:8501"
LOG_PATH = Path("logs") / "install.jsonl"
DIRECTORIES = (
    Path("chroma_data"),
    Path("logs"),
    Path("knowledge_base") / "sources",
    Path("data") / "incoming",
    Path("data") / "output",
    Path("output"),
    Path("reports"),
)


class InstallError(RuntimeError):
    """Deterministic installer failure with a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CommandResult:
    command: Sequence[str]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    skipped: bool = False


@dataclass
class InstallContext:
    project_root: Path
    dry_run: bool = False
    yes: bool = False
    model: str = DEFAULT_MODEL
    runner: Callable[[Sequence[str], Path, bool], CommandResult] | None = None
    prompt: Callable[[str], str] = input
    events: list[dict[str, object]] = field(default_factory=list)

    @property
    def log_path(self) -> Path:
        return self.project_root / LOG_PATH


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: ("***REDACTED***" if "KEY" in key or "SECRET" in key else _redact(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def write_install_event(
    ctx: InstallContext,
    step: str,
    status: str,
    *,
    duration_s: float = 0.0,
    code: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    ctx.log_path.parent.mkdir(parents=True, exist_ok=True)
    event: dict[str, object] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "step": step,
        "status": status,
        "duration_s": round(duration_s, 3),
    }
    if code:
        event["code"] = code
    if details:
        event["details"] = _redact(details)
    ctx.events.append(event)
    with ctx.log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_step(
    ctx: InstallContext,
    command: Sequence[str],
    *,
    step: str,
    check: bool = True,
) -> CommandResult:
    started = time.monotonic()
    runner = ctx.runner or _default_runner
    result = runner(command, ctx.project_root, ctx.dry_run)
    status = "SKIPPED" if result.skipped else "OK"
    if check and result.returncode != 0:
        write_install_event(
            ctx,
            step,
            "ERROR",
            duration_s=time.monotonic() - started,
            code="COMMAND_FAILED",
            details={"command": list(command), "stderr": result.stderr},
        )
        raise InstallError("COMMAND_FAILED", f"Command failed: {' '.join(command)}")
    write_install_event(
        ctx,
        step,
        status,
        duration_s=time.monotonic() - started,
        details={"command": list(command)},
    )
    return result


def _default_runner(command: Sequence[str], cwd: Path, dry_run: bool) -> CommandResult:
    if dry_run:
        return CommandResult(command=command, skipped=True)
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _step_banner(index: int, title: str) -> None:
    print(f"\n[{index}/8] {title}")


def check_environment(ctx: InstallContext) -> dict[str, object]:
    _step_banner(1, "Проверка среды")
    started = time.monotonic()
    details = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git": bool(shutil.which("git")),
        "dry_run": ctx.dry_run,
    }
    print(f"  - Python ................................ OK ({details['python']})")
    print(f"  - git ................................... {'OK' if details['git'] else 'MISSING'}")
    write_install_event(ctx, "environment", "OK", duration_s=time.monotonic() - started, details=details)
    return details


def ensure_directories(ctx: InstallContext) -> list[tuple[str, str]]:
    _step_banner(2, "Создание структуры")
    started = time.monotonic()
    results: list[tuple[str, str]] = []
    for relative in DIRECTORIES:
        path = ctx.project_root / relative
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        status = "EXISTS" if existed else "CREATED"
        results.append((str(relative), status))
        print(f"  - {relative} ............................ {status}")
    write_install_event(
        ctx,
        "directories",
        "OK",
        duration_s=time.monotonic() - started,
        details={"directories": [{"path": path, "status": status} for path, status in results]},
    )
    return results


def ensure_venv(ctx: InstallContext) -> None:
    _step_banner(3, "Виртуальное окружение")
    venv_path = ctx.project_root / "venv"
    if venv_path.exists():
        print("  - venv .................................. EXISTS")
        write_install_event(ctx, "venv", "EXISTS", details={"path": "venv"})
        return
    py_launcher = "py" if os.name == "nt" else sys.executable
    command = [py_launcher, "-3.14", "-m", "venv", "venv"] if os.name == "nt" else [py_launcher, "-m", "venv", "venv"]
    run_step(ctx, command, step="venv")
    run_step(ctx, _python_in_venv(ctx, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"), step="pip-upgrade")
    run_step(ctx, _python_in_venv(ctx, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"), step="pip-requirements")


def _python_in_venv(ctx: InstallContext, *args: str) -> list[str]:
    executable = ctx.project_root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return [str(executable), *args]


def ensure_env_file(ctx: InstallContext) -> str:
    _step_banner(4, "Конфигурация .env")
    started = time.monotonic()
    env_path = ctx.project_root / ".env"
    env_txt_path = ctx.project_root / ".env.txt"
    if env_path.exists():
        print("  - .env .................................. EXISTS")
        write_install_event(ctx, "env", "EXISTS", duration_s=time.monotonic() - started)
        return "EXISTS"
    if env_txt_path.exists():
        message = "Обнаружен .env.txt без .env. Переименуйте вручную: ren .env.txt .env"
        write_install_event(ctx, "env", "ERROR", duration_s=time.monotonic() - started, code="ENV_TXT_FOUND")
        raise InstallError("ENV_TXT_FOUND", message)
    example_path = ctx.project_root / ".env.example"
    if not example_path.exists():
        write_install_event(ctx, "env", "ERROR", duration_s=time.monotonic() - started, code="ENV_EXAMPLE_MISSING")
        raise InstallError("ENV_EXAMPLE_MISSING", ".env.example not found; cannot create .env")
    shutil.copyfile(example_path, env_path)
    print("  - copy .env.example -> .env ............. OK")
    write_install_event(ctx, "env", "CREATED", duration_s=time.monotonic() - started)
    return "CREATED"


def resolve_ollama_binary(env: dict[str, str] | None = None) -> Path | None:
    found = shutil.which("ollama")
    if found:
        return Path(found)
    values = env or os.environ
    candidates = []
    local_app_data = values.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe")
    candidates.append(Path("C:/Program Files/Ollama/ollama.exe"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _models_from_ollama_list(output: str) -> set[str]:
    models: set[str] = set()
    for line in output.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.add(parts[0])
    return models


def check_ollama(ctx: InstallContext) -> str:
    _step_banner(5, "Ollama")
    started = time.monotonic()
    binary = resolve_ollama_binary()
    if binary is None:
        print("  - ollama ................................ MISSING")
        write_install_event(ctx, "ollama", "SKIPPED", duration_s=time.monotonic() - started, code="OLLAMA_MISSING")
        return "MISSING_BINARY"
    version = run_step(ctx, [str(binary), "--version"], step="ollama-version", check=False)
    models = run_step(ctx, [str(binary), "list"], step="ollama-list", check=False)
    installed = ctx.model in _models_from_ollama_list(models.stdout)
    if not installed:
        if ctx.yes or _confirm(ctx, f"Скачать модель {ctx.model} (~4.3 GiB)? [y/N]: "):
            run_step(ctx, [str(binary), "pull", ctx.model], step="ollama-pull")
            status = "MODEL_PULLED"
        else:
            status = "MODEL_MISSING_USER_DECLINED"
    else:
        status = "OK"
    write_install_event(
        ctx,
        "ollama",
        status,
        duration_s=time.monotonic() - started,
        details={"binary": str(binary), "model": ctx.model, "version_stdout": version.stdout},
    )
    print(f"  - model {ctx.model} ..................... {status}")
    return status


def _confirm(ctx: InstallContext, question: str) -> bool:
    answer = ctx.prompt(question).strip().lower()
    return answer in {"y", "yes", "д", "да"}


def run_smoke_import(ctx: InstallContext) -> None:
    _step_banner(6, "Smoke import")
    run_step(ctx, [sys.executable, "-c", "import src; print('OK')"], step="smoke-import")


def create_shortcuts(ctx: InstallContext) -> str:
    _step_banner(7, "Ярлыки")
    started = time.monotonic()
    if os.name != "nt":
        print("  - shortcuts ............................. SKIPPED (non-Windows)")
        write_install_event(ctx, "shortcuts", "SKIPPED", duration_s=time.monotonic() - started, code="NON_WINDOWS")
        return "SKIPPED"
    ps_script = (
        "$WshShell = New-Object -comObject WScript.Shell; "
        "$Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\Clarify Engine.lnk'); "
        f"$Shortcut.TargetPath = '{ctx.project_root}\\scripts\\install\\clarify-setup.cmd'; "
        f"$Shortcut.WorkingDirectory = '{ctx.project_root}'; "
        "$Shortcut.Save()"
    )
    run_step(ctx, ["powershell", "-NoProfile", "-Command", ps_script], step="shortcuts")
    return "CREATED"


def final_summary(ctx: InstallContext) -> None:
    _step_banner(8, "Готово")
    print(f"  URL:  {STREAMLIT_URL}")
    print(f"  Log:  {ctx.log_path}")
    write_install_event(ctx, "final", "OK", details={"url": STREAMLIT_URL, "log": str(ctx.log_path)})


def run_wizard(ctx: InstallContext) -> int:
    print("=" * 50)
    print("Clarify Engine AI - First-Run Setup")
    print("=" * 50)
    try:
        check_environment(ctx)
        ensure_directories(ctx)
        ensure_venv(ctx)
        ensure_env_file(ctx)
        check_ollama(ctx)
        run_smoke_import(ctx)
        create_shortcuts(ctx)
        final_summary(ctx)
    except InstallError as exc:
        print(f"ERROR [{exc.code}]: {exc}")
        return 1
    return 0


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".env.example").exists() and (candidate / "requirements.txt").exists():
            return candidate
    return current


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clarify Engine AI first-run setup")
    parser.add_argument("--project-root", type=Path, default=_find_project_root(Path.cwd()))
    parser.add_argument("--dry-run", action="store_true", help="Log planned commands without executing them")
    parser.add_argument("--yes", action="store_true", help="Confirm optional downloads such as ollama pull")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    ctx = InstallContext(
        project_root=args.project_root.resolve(),
        dry_run=args.dry_run,
        yes=args.yes,
        model=args.model,
    )
    return run_wizard(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
