"""Centralised prompt loader for the Clarify Engine prompt library (BL-08, issue #94).

Prompts are stored under ``prompts/`` as versioned files
(``<name>_v<MAJOR>.<MINOR>.<ext>``) so they can be audited, reviewed and
swapped without touching the Python source. Markdown is used for
free-form system prompts and JSON for structured artefacts such as
few-shot examples.

Three responsibilities live here:

1. Resolving ``(name, version)`` to a file on disk and reading it once.
2. Computing a SHA-256 hash of the raw bytes so that every classification /
   RAG run can be tied back to the exact prompt revision that was used
   (BL-23 audit trail, see ``docs/ADR/004-prompt-management.md``).
3. Emitting a structured ``INFO`` log record at load time — when callers
   supply ``run_id`` it is propagated via the ``extra`` mapping so the
   existing JSON logging configuration (``src/pipeline.py``) groups the
   load alongside the rest of the run's records.

The loader is intentionally thin: no Jinja templating, no environment
overrides, no remote fetch. The hidden side-effect of switching a prompt
is exactly one shell command (``git mv``) plus a row in
``prompts/prompt_changelog.md`` — this keeps the module easy to audit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS_DIR = Path("prompts")

# Markdown is the canonical format for system prompts; ``.txt`` is accepted
# as a fallback so a prompt that does not need any Markdown features can
# ship as plain text without changing call sites.
PROMPT_FILE_EXTENSIONS: Tuple[str, ...] = (".md", ".txt")

# ``system_classifier_v1.0`` — capture name and version separately so a
# path-based caller (legacy ``LLMClient(prompt_path=...)``) can still benefit
# from the SHA-256 audit log without supplying ``(name, version)`` explicitly.
_FILENAME_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_\-]*?)_v(?P<version>\d+\.\d+)(?P<ext>\.[A-Za-z0-9]+)$"
)


class PromptNotFoundError(FileNotFoundError):
    """Raised when no file matches the requested ``(name, version)`` pair."""


@dataclass(frozen=True)
class PromptInfo:
    """Loaded prompt with its provenance metadata.

    Attributes:
        name: Logical prompt name (``system_classifier``).
        version: Prompt version string (``v1.0``).
        path: Absolute path to the file on disk.
        content: Raw text content as read from the file.
        sha256: Hex SHA-256 digest of the *bytes* on disk — recorded in
            ``prompts/prompt_changelog.md`` for audit (BL-23).
    """

    name: str
    version: str
    path: Path
    content: str
    sha256: str

    def __str__(self) -> str:  # noqa: D401 - keep ``str(prompt)`` ergonomic
        return self.content


def compute_sha256(content: Union[str, bytes]) -> str:
    """Return the hex SHA-256 digest of ``content``.

    ``str`` inputs are encoded as UTF-8 so the digest matches what a fresh
    ``sha256sum`` on the file would produce.
    """
    if isinstance(content, str):
        data = content.encode("utf-8")
    else:
        data = content
    return hashlib.sha256(data).hexdigest()


def _candidate_filenames(name: str, version: str) -> List[str]:
    return [f"{name}_{version}{ext}" for ext in PROMPT_FILE_EXTENSIONS]


def _emit_load_log(
    kind: str,
    name: str,
    version: str,
    sha256: str,
    path: Path,
    run_id: Optional[str],
) -> None:
    extra: Dict[str, Any] = {
        "prompt_name": name,
        "prompt_version": version,
        "prompt_hash": sha256,
        "prompt_sha256": sha256,
    }
    if run_id:
        extra["run_id"] = run_id
    logger.info(
        "prompt_loader: loaded %s name=%s version=%s sha256=%s path=%s",
        kind,
        name,
        version,
        sha256,
        path,
        extra=extra,
    )


def load_prompt(
    name: str,
    version: str = "v1.0",
    *,
    prompts_dir: Union[str, Path] = DEFAULT_PROMPTS_DIR,
    run_id: Optional[str] = None,
) -> PromptInfo:
    """Load a versioned text prompt from ``prompts/``.

    Tries ``{name}_{version}.md`` first, then ``{name}_{version}.txt``.

    Args:
        name: Logical prompt name (``system_classifier``, ``system_rag``).
        version: Semantic version string with the ``v`` prefix (``v1.0``).
        prompts_dir: Override for the default ``prompts/`` location.
            Useful in tests and when the project is invoked from a
            different working directory.
        run_id: Optional pipeline run identifier. When supplied, the load
            log record carries ``run_id`` so it can be correlated with the
            rest of the run via the JSON formatter in ``src/pipeline.py``.

    Returns:
        :class:`PromptInfo` carrying the raw content and SHA-256 hash.

    Raises:
        PromptNotFoundError: when no file matches.
    """
    prompts_path = Path(prompts_dir)
    for filename in _candidate_filenames(name, version):
        candidate = prompts_path / filename
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            sha = compute_sha256(content)
            _emit_load_log("prompt", name, version, sha, candidate, run_id)
            return PromptInfo(
                name=name,
                version=version,
                path=candidate.resolve(),
                content=content,
                sha256=sha,
            )

    looked_for = ", ".join(_candidate_filenames(name, version))
    raise PromptNotFoundError(
        f"Prompt '{name}' (version='{version}') not found in '{prompts_path}'. "
        f"Looked for: {looked_for}."
    )


def load_few_shot_examples(
    name: str = "few_shot_examples",
    version: str = "v1.0",
    *,
    prompts_dir: Union[str, Path] = DEFAULT_PROMPTS_DIR,
    run_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Load few-shot examples from ``prompts/{name}_{version}.json``.

    Returns:
        ``(examples, sha256)``. ``examples`` is parsed JSON (typically a
        list of ``{"input": ..., "output": ...}`` dictionaries) and
        ``sha256`` is the digest of the on-disk file.

    Raises:
        PromptNotFoundError: when the JSON file is missing.
        json.JSONDecodeError: when the file is unparseable.
    """
    prompts_path = Path(prompts_dir)
    candidate = prompts_path / f"{name}_{version}.json"
    if not candidate.exists():
        raise PromptNotFoundError(
            f"Few-shot examples '{name}' (version='{version}') not found at "
            f"'{candidate}'."
        )
    raw = candidate.read_text(encoding="utf-8")
    examples = json.loads(raw)
    sha = compute_sha256(raw)
    _emit_load_log("few_shot", name, version, sha, candidate, run_id)
    return examples, sha


def parse_prompt_filename(filename: str) -> Optional[Tuple[str, str]]:
    """Extract ``(name, version)`` from ``<name>_v<MAJOR>.<MINOR>.<ext>``.

    Returns ``None`` when the filename does not match the convention so
    callers can fall back to legacy path-based behaviour without raising.
    """
    match = _FILENAME_RE.match(Path(filename).name)
    if not match:
        return None
    return match.group("name"), f"v{match.group('version')}"


def load_prompt_from_path(
    path: Union[str, Path],
    *,
    run_id: Optional[str] = None,
) -> PromptInfo:
    """Load a prompt referenced by a file system path.

    The function is the bridge between the legacy ``LLMClient(prompt_path=...)``
    API and the new prompt library. Name and version are extracted from the
    filename when it matches ``<name>_v<MAJOR>.<MINOR>.<ext>``; otherwise the
    full filename (without extension) is used as the name and ``"unknown"``
    as the version, so audit logs still carry *something* identifying.

    Raises:
        PromptNotFoundError: when the file is missing.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise PromptNotFoundError(f"Prompt file not found: {file_path}")
    parsed = parse_prompt_filename(file_path.name)
    if parsed is not None:
        name, version = parsed
    else:
        name = file_path.stem
        version = "unknown"
    content = file_path.read_text(encoding="utf-8")
    sha = compute_sha256(content)
    _emit_load_log("prompt", name, version, sha, file_path, run_id)
    return PromptInfo(
        name=name,
        version=version,
        path=file_path.resolve(),
        content=content,
        sha256=sha,
    )


__all__ = [
    "DEFAULT_PROMPTS_DIR",
    "PROMPT_FILE_EXTENSIONS",
    "PromptInfo",
    "PromptNotFoundError",
    "compute_sha256",
    "load_few_shot_examples",
    "load_prompt",
    "load_prompt_from_path",
    "parse_prompt_filename",
]
