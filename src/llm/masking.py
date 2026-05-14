"""Data masking module for sensitive information.

This module provides regex-based masking for sensitive data patterns
before sending text to external LLM APIs. Patterns are loaded from
``configs/masking_rules.yaml``.

Supported patterns (as of v1):
- Email addresses
- Russian phone numbers (+7 format)
- IP addresses
- Internal domains (mango, internal, corp, local)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFAULT_MASKING_CONFIG_PATH = "configs/masking_rules.yaml"


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


def _compile_masking_patterns(
    config: Dict[str, Any],
) -> List[tuple[re.Pattern[str], str]]:
    """Compile regex patterns from masking configuration.
    
    Args:
        config: Masking configuration dict with 'patterns' key.
        
    Returns:
        List of (compiled_pattern, replacement) tuples.
    """
    compiled: List[tuple[re.Pattern[str], str]] = []
    for entry in config.get("patterns", []) or []:
        regex = entry.get("regex")
        replacement = entry.get("replacement", "[MASKED]")
        if not regex:
            continue
        try:
            compiled.append((re.compile(regex), replacement))
        except re.error:
            pass  # Skip invalid patterns silently
    return compiled


class Masker:
    """Regex-based text masker for sensitive data.
    
    Loads masking rules from YAML config and caches compiled patterns
    for efficient repeated use.
    """

    def __init__(self, config_path: str = DEFAULT_MASKING_CONFIG_PATH) -> None:
        self.config_path = config_path
        self._patterns: Optional[List[tuple[re.Pattern[str], str]]] = None

    @property
    def patterns(self) -> List[tuple[re.Pattern[str], str]]:
        """Lazy-load and cache compiled patterns."""
        if self._patterns is None:
            config = _load_yaml(self.config_path)
            self._patterns = _compile_masking_patterns(config)
        return self._patterns

    def mask(self, text: str) -> str:
        """Apply all masking rules to the input text.
        
        Args:
            text: Input text that may contain sensitive data.
            
        Returns:
            Text with sensitive patterns replaced by placeholders.
        """
        if not text:
            return text
        masked = text
        for pattern, replacement in self.patterns:
            masked = pattern.sub(replacement, masked)
        return masked


# Module-level cache for backward compatibility with existing API
_masking_cache: Dict[str, List[tuple[re.Pattern[str], str]]] = {}


def mask_text(
    text: str,
    config_path: str = DEFAULT_MASKING_CONFIG_PATH,
    _cache: Dict[str, List[tuple[re.Pattern[str], str]]] = _masking_cache,
) -> str:
    """Apply regex masking rules from ``masking_rules.yaml`` to ``text``.
    
    This function maintains backward compatibility with existing imports
    from ``src.llm.client``. New code should prefer the ``Masker`` class.
    
    Args:
        text: Input text that may contain sensitive data.
        config_path: Path to masking rules YAML config.
        _cache: Internal cache for compiled patterns.
        
    Returns:
        Text with sensitive patterns replaced by placeholders.
    """
    if not text:
        return text
    if config_path not in _cache:
        _cache[config_path] = _compile_masking_patterns(_load_yaml(config_path))
    masked = text
    for pattern, replacement in _cache[config_path]:
        masked = pattern.sub(replacement, masked)
    return masked


def mask_context_chunks(
    chunks: List[Dict[str, Any]],
    config_path: str = DEFAULT_MASKING_CONFIG_PATH,
) -> List[Dict[str, Any]]:
    """Apply masking to the 'text' field of each context chunk.
    
    Args:
        chunks: List of context dicts with 'text' and optional 'metadata'.
        config_path: Path to masking rules YAML config.
        
    Returns:
        New list of chunks with masked 'text' fields.
    """
    if not chunks:
        return chunks
    masker = Masker(config_path=config_path)
    result = []
    for chunk in chunks:
        masked_chunk = dict(chunk)  # shallow copy
        if "text" in masked_chunk and masked_chunk["text"]:
            masked_chunk["text"] = masker.mask(masked_chunk["text"])
        result.append(masked_chunk)
    return result
