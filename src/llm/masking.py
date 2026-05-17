"""Data masking module for sensitive information.

This module provides regex-based masking for sensitive data patterns
before sending text to external LLM APIs. Patterns are loaded from
``configs/masking_rules.yaml``.

Supported patterns (as of v2):

- Email addresses
- Russian phone numbers (+7 format)
- IP addresses
- Internal domains (internal, corp, local)
- Legal entity names following Russian prefixes (ООО, АО, ПАО, ЗАО, НАО, ОАО)
- Surnames following the ИП (individual entrepreneur) prefix

Each pattern entry supports the following keys:

- ``name`` (str): Stable identifier used in debug logs.
- ``regex`` / ``pattern`` (str): Python regular expression. Backreferences
  (``\\1``, ``\\2``...) are supported in the replacement value via
  :func:`re.sub`.
- ``replacement`` (str): Replacement string. Defaults to ``"[MASKED]"``.
- ``description`` (str, optional): Human-readable note (not used by code).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_MASKING_CONFIG_PATH = "configs/masking_rules.yaml"


@dataclass(frozen=True)
class CompiledPattern:
    """A compiled masking rule with its stable identifier."""

    name: str
    pattern: re.Pattern[str]
    replacement: str


def _load_yaml(path: str) -> Dict[str, Any]:
    """Load YAML configuration file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content as dict, or empty dict if file not found/invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}


def _compile_masking_patterns(config: Dict[str, Any]) -> List[CompiledPattern]:
    """Compile regex patterns from masking configuration.

    Accepts both ``regex`` (preferred, used by the existing config) and
    ``pattern`` (alias) as the regex source key for compatibility.

    Args:
        config: Masking configuration dict with ``patterns`` key.

    Returns:
        List of :class:`CompiledPattern` instances. Invalid entries are
        skipped silently.
    """
    compiled: List[CompiledPattern] = []
    for index, entry in enumerate(config.get("patterns", []) or []):
        regex = entry.get("regex") or entry.get("pattern")
        replacement = entry.get("replacement", "[MASKED]")
        name = entry.get("name") or f"pattern_{index}"
        if not regex:
            continue
        try:
            compiled.append(
                CompiledPattern(
                    name=name,
                    pattern=re.compile(regex),
                    replacement=replacement,
                )
            )
        except re.error:
            logger.warning("Skipping invalid masking regex '%s'", name)
    return compiled


def _apply_patterns(
    text: str,
    patterns: List[CompiledPattern],
    *,
    context: Optional[str] = None,
) -> str:
    """Apply a sequence of compiled patterns to ``text``.

    Backreferences (``\\1``, ``\\2``...) in ``replacement`` are handled
    natively by :func:`re.sub`. Logging records the pattern name and
    number of substitutions only -- never the matched data.
    """
    masked = text
    for entry in patterns:
        masked, count = entry.pattern.subn(entry.replacement, masked)
        if count and logger.isEnabledFor(logging.DEBUG):
            suffix = f" in {context}" if context else ""
            logger.debug("Masked %s (%d match%s)%s", entry.name, count, "es" if count != 1 else "", suffix)
    return masked


class Masker:
    """Regex-based text masker for sensitive data.

    Loads masking rules from YAML config and caches compiled patterns
    for efficient repeated use.
    """

    def __init__(self, config_path: str = DEFAULT_MASKING_CONFIG_PATH) -> None:
        self.config_path = config_path
        self._patterns: Optional[List[CompiledPattern]] = None

    @property
    def patterns(self) -> List[CompiledPattern]:
        """Lazy-load and cache compiled patterns."""
        if self._patterns is None:
            config = _load_yaml(self.config_path)
            self._patterns = _compile_masking_patterns(config)
        return self._patterns

    def mask(self, text: str, *, context: Optional[str] = None) -> str:
        """Apply all masking rules to ``text``.

        Args:
            text: Input text that may contain sensitive data.
            context: Optional identifier (e.g. requirement id) attached to
                debug log records. The masked data itself is never logged.

        Returns:
            Text with sensitive patterns replaced by placeholders.
        """
        if not text:
            return text
        return _apply_patterns(text, self.patterns, context=context)


# Module-level cache for backward compatibility with the legacy procedural API.
_masking_cache: Dict[str, List[CompiledPattern]] = {}


def mask_text(
    text: str,
    config_path: str = DEFAULT_MASKING_CONFIG_PATH,
    _cache: Dict[str, List[CompiledPattern]] = _masking_cache,
    *,
    context: Optional[str] = None,
) -> str:
    """Apply regex masking rules from ``masking_rules.yaml`` to ``text``.

    This function maintains backward compatibility with existing imports
    from ``src.llm.client``. New code should prefer the :class:`Masker`
    class.

    Args:
        text: Input text that may contain sensitive data.
        config_path: Path to masking rules YAML config.
        _cache: Internal cache for compiled patterns.
        context: Optional context identifier passed to debug logging.

    Returns:
        Text with sensitive patterns replaced by placeholders.
    """
    if not text:
        return text
    if config_path not in _cache:
        _cache[config_path] = _compile_masking_patterns(_load_yaml(config_path))
    return _apply_patterns(text, _cache[config_path], context=context)


def mask_context_chunks(
    chunks: List[Dict[str, Any]],
    config_path: str = DEFAULT_MASKING_CONFIG_PATH,
) -> List[Dict[str, Any]]:
    """Apply masking to the ``text`` field of each context chunk.

    Args:
        chunks: List of context dicts with ``text`` and optional ``metadata``.
        config_path: Path to masking rules YAML config.

    Returns:
        New list of chunks with masked ``text`` fields.
    """
    if not chunks:
        return chunks
    masker = Masker(config_path=config_path)
    result = []
    for chunk in chunks:
        masked_chunk = dict(chunk)  # shallow copy
        if "text" in masked_chunk and masked_chunk["text"]:
            masked_chunk["text"] = masker.mask(
                masked_chunk["text"],
                context=str(masked_chunk.get("source") or "chunk"),
            )
        result.append(masked_chunk)
    return result


# --- BL-23: log sanitization (issue #87) --------------------------------------
# Fields preserved verbatim — they are needed for trace correlation across
# FR-08 logs and `reports/rag-*.json` artifacts, and they MUST NOT carry PII
# by construction (they are UUIDs / enums / identifiers).
_SANITIZE_PRESERVED_KEYS: tuple[str, ...] = (
    "run_id",
    "requirement_id",
    "level",
    "timestamp",
    "logger",
    "provider",
    "classification",
)
# String fields whose value is masked through the YAML regex set.
_SANITIZE_TEXT_FIELDS: tuple[str, ...] = (
    "message",
    "payload",
    "context",
    "answer",
    "question",
    "requirement_text",
    "user_prompt",
    "system_prompt",
)
# Environment variable name suffixes treated as secrets.
_SECRET_ENV_SUFFIXES: tuple[str, ...] = ("_API_KEY", "_TOKEN", "_SECRET", "_AUTH")
# Default truncation threshold for ``payload`` (32 KB per ADR-003 §4.3).
DEFAULT_PAYLOAD_TRUNCATE_BYTES: int = 32 * 1024
REDACTED_MARKER: str = "***REDACTED***"


def _looks_like_secret_env(key: str) -> bool:
    if not isinstance(key, str):
        return False
    upper = key.upper()
    return any(upper.endswith(suffix) for suffix in _SECRET_ENV_SUFFIXES)


def _truncate_payload(value: str, limit: int) -> str:
    encoded = value.encode("utf-8", errors="ignore")
    if len(encoded) <= limit:
        return value
    head = encoded[: max(0, limit - 32)].decode("utf-8", errors="ignore")
    return f"{head}…[TRUNCATED:{len(encoded)}B]"


def _sanitize_string(
    value: str,
    *,
    patterns: List[CompiledPattern],
    field_name: Optional[str] = None,
    truncate_bytes: int,
) -> str:
    """Apply regex masks and (for ``payload``) length-cap to a single string."""
    if not value:
        return value
    masked = _apply_patterns(value, patterns, context=field_name)
    if field_name == "payload":
        masked = _truncate_payload(masked, truncate_bytes)
    return masked


def _sanitize_value(
    value: Any,
    *,
    patterns: List[CompiledPattern],
    field_name: Optional[str],
    truncate_bytes: int,
) -> Any:
    """Recursive sanitiser used by :func:`sanitize_log_record`.

    - Preserves dict/list nesting (returns new containers, never mutates).
    - Applies masking only to string leaves.
    - Recognises the ``chunks`` list (or any list of dicts with a ``text``
      key) and masks chunk text without disturbing other metadata.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_string(
            value,
            patterns=patterns,
            field_name=field_name,
            truncate_bytes=truncate_bytes,
        )
    if isinstance(value, dict):
        masked: Dict[str, Any] = {}
        for key, sub in value.items():
            if key in _SANITIZE_PRESERVED_KEYS:
                masked[key] = sub
                continue
            if _looks_like_secret_env(key):
                masked[key] = REDACTED_MARKER
                continue
            masked[key] = _sanitize_value(
                sub,
                patterns=patterns,
                field_name=key if isinstance(key, str) else None,
                truncate_bytes=truncate_bytes,
            )
        return masked
    if isinstance(value, list):
        return [
            _sanitize_value(
                item,
                patterns=patterns,
                field_name=field_name,
                truncate_bytes=truncate_bytes,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _sanitize_value(
                item,
                patterns=patterns,
                field_name=field_name,
                truncate_bytes=truncate_bytes,
            )
            for item in value
        )
    # Unknown types are converted to string then masked, never logged raw.
    return _sanitize_string(
        str(value),
        patterns=patterns,
        field_name=field_name,
        truncate_bytes=truncate_bytes,
    )


def sanitize_log_record(
    record: Dict[str, Any],
    *,
    config_path: str = DEFAULT_MASKING_CONFIG_PATH,
    truncate_bytes: int = DEFAULT_PAYLOAD_TRUNCATE_BYTES,
) -> Dict[str, Any]:
    """Sanitise a log/report record before serialisation.

    BL-23 alias for ADR-003 §4.3 ``sanitize_for_log()``. The function:

    - Applies every regex from ``configs/masking_rules.yaml`` to string leaves
      of the record (``message``, ``payload``, ``context``, ``answer``,
      ``question``, ``requirement_text`` and any nested ``chunks[*].text``).
    - Redacts environment-variable values whose key looks like a secret
      (``*_API_KEY``, ``*_TOKEN``, ``*_SECRET``, ``*_AUTH``) — typical entries
      in ``extra={"env": {...}}`` blocks.
    - Truncates the ``payload`` field once it exceeds ``truncate_bytes``
      (defaults to 32 KB) to prevent CI artefact explosion.
    - Preserves trace identifiers (``run_id``, ``requirement_id``, ``level``,
      ``timestamp``, ``logger``, ``provider``, ``classification``) verbatim.

    Args:
        record: The log-record dict to sanitise. The input is not mutated.
        config_path: Path to masking rules YAML config.
        truncate_bytes: Max payload size in bytes before truncation.

    Returns:
        A new dict with sensitive fragments replaced by mask tokens.
    """
    if not isinstance(record, dict):
        raise TypeError(
            "sanitize_log_record expects a dict; got " + type(record).__name__
        )
    if config_path not in _masking_cache:
        _masking_cache[config_path] = _compile_masking_patterns(_load_yaml(config_path))
    patterns = _masking_cache[config_path]
    sanitized: Dict[str, Any] = {}
    for key, value in record.items():
        if key in _SANITIZE_PRESERVED_KEYS:
            sanitized[key] = value
            continue
        if _looks_like_secret_env(key):
            sanitized[key] = REDACTED_MARKER
            continue
        sanitized[key] = _sanitize_value(
            value,
            patterns=patterns,
            field_name=key if isinstance(key, str) else None,
            truncate_bytes=truncate_bytes,
        )
    return sanitized
