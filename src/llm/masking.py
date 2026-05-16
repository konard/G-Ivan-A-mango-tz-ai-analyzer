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
