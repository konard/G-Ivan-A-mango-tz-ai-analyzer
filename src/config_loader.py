"""Startup ``.env`` validation guard (BL-50, issue #194).

The guard is invoked from both CLI (``src/pipeline.py``) and UI
(``src/ui/app.py``) entry points **before** any consumer of
``os.environ`` is touched. It enforces three rules from the BL-50
contract:

1. If ``.env`` is missing **and** a sibling ``.env.txt`` exists, fail
   fast with an actionable message that asks the operator to
   ``ren .env.txt .env`` themselves. Notepad on Windows hides the
   extension and ships ``.txt`` silently — auto-renaming would mask
   that mistake, which is why no silent rename happens here.
2. If both ``.env`` and ``.env.txt`` are missing **and** ``.env.example``
   exists, copy ``.env.example`` to ``.env`` and continue. The example
   file is shipped in the repository and contains no secrets, so this
   makes first-launch deterministic on a clean ARM.
3. After ``.env`` is loaded, validate that ``OLLAMA_MODEL`` and
   ``OLLAMA_BASE_URL`` are non-empty strings. Empty values lead to
   silent HTTP 404 from Ollama; we surface that as a deterministic
   error instead.

Messages are user-facing Russian copy from the BL-50 backlog
(``docs/backlog/2026-05-20_backlog_arm-pilot-test-fixes_v1.md`` §4.2)
and reference ``docs/user_guide/04_troubleshooting.md`` for further
help. Logs go through the existing pipeline sanitiser (BL-23) — only
filenames are mentioned, never the file contents.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


logger = logging.getLogger(__name__)


REQUIRED_ENV_VARS: tuple[str, ...] = ("OLLAMA_MODEL", "OLLAMA_BASE_URL")
TROUBLESHOOTING_REF = "docs/user_guide/04_troubleshooting.md"


class EnvValidationError(RuntimeError):
    """Raised when the ``.env`` startup guard cannot continue.

    The CLI (``src/pipeline.py``) catches this and exits with a non-zero
    code; the Streamlit UI surfaces the message via ``st.error`` so the
    operator sees the same actionable hint inside the browser.
    """


@dataclass(frozen=True)
class EnvValidationResult:
    """Outcome of :func:`validate_env`.

    ``copied_from_example`` is True when ``.env`` was just generated
    from ``.env.example``; the caller may use it for an INFO log line.
    """

    env_path: Path
    copied_from_example: bool


def _find_project_root(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit
    # ``src/config_loader.py`` → repo root is two levels up.
    return Path(__file__).resolve().parents[1]


def _ensure_env_file(project_root: Path) -> bool:
    """Make sure ``project_root / '.env'`` exists.

    Returns True when the file was just created from ``.env.example``.
    Raises :class:`EnvValidationError` when ``.env.txt`` is present
    (silent rename is forbidden) or when there is no ``.env.example``
    to copy from.
    """
    env_path = project_root / ".env"
    if env_path.exists():
        return False

    env_txt_path = project_root / ".env.txt"
    if env_txt_path.exists():
        message = (
            "Обнаружен файл .env.txt вместо .env. Notepad на Windows скрывает "
            "расширение и сохраняет файл как .env.txt. Переименуйте его вручную "
            "командой: ren .env.txt .env (см. также: "
            f"{TROUBLESHOOTING_REF})."
        )
        logger.error(message)
        raise EnvValidationError(message)

    example_path = project_root / ".env.example"
    if not example_path.exists():
        message = (
            "Файл .env не найден, и .env.example отсутствует — невозможно "
            "автоматически создать .env. Создайте .env вручную (см. также: "
            f"{TROUBLESHOOTING_REF})."
        )
        logger.error(message)
        raise EnvValidationError(message)

    shutil.copyfile(example_path, env_path)
    logger.info("Создан .env из .env.example")
    return True


def _default_dotenv_loader() -> Callable[[Path], bool]:
    """Return a ``load_dotenv``-compatible callable.

    The dependency on ``python-dotenv`` is declared in ``requirements.txt``
    but we still degrade gracefully: a missing library means existing
    ``os.environ`` values (e.g. set via ``setx``) are honoured and only
    the empty-string validation step can flag a problem.
    """
    try:
        from dotenv import load_dotenv as _load_dotenv  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - dependency is in requirements.txt

        def _noop_loader(_path: Path) -> bool:
            return False

        return _noop_loader

    def _loader(path: Path) -> bool:
        return bool(_load_dotenv(path, override=False))

    return _loader


def _validate_required_vars(
    required: Iterable[str] = REQUIRED_ENV_VARS,
) -> None:
    missing: list[str] = [
        name for name in required if not (os.environ.get(name) or "").strip()
    ]
    if not missing:
        return
    joined = ", ".join(missing)
    message = (
        f"В .env отсутствуют или пустые обязательные переменные: {joined}. "
        "Заполните их по образцу из .env.example "
        f"(см. также: {TROUBLESHOOTING_REF})."
    )
    logger.error(message)
    raise EnvValidationError(message)


def validate_env(
    project_root: Optional[Path] = None,
    *,
    dotenv_loader: Optional[Callable[[Path], bool]] = None,
    required_vars: Iterable[str] = REQUIRED_ENV_VARS,
) -> EnvValidationResult:
    """Run the BL-50 startup guard.

    Parameters
    ----------
    project_root:
        Repository root. Defaults to the directory two levels above this
        module so ``streamlit run src/ui/app.py`` and ``python -m
        src.pipeline`` both pick the same ``.env``.
    dotenv_loader:
        Injection point for tests. Receives the ``.env`` :class:`Path`
        and returns the truthy/falsy success flag from ``load_dotenv``.
    required_vars:
        Variables that must be present and non-empty after loading
        ``.env``. Defaults to ``OLLAMA_MODEL`` + ``OLLAMA_BASE_URL`` per
        BL-50 §4.2.

    Returns
    -------
    EnvValidationResult
        Describes the ``.env`` path and whether it was just bootstrapped
        from ``.env.example``.
    """
    root = _find_project_root(project_root)
    copied = _ensure_env_file(root)
    env_path = root / ".env"

    loader = dotenv_loader or _default_dotenv_loader()
    loader(env_path)

    _validate_required_vars(required_vars)
    return EnvValidationResult(env_path=env_path, copied_from_example=copied)
