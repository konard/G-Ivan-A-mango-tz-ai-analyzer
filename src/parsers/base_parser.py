"""Shared utilities and base classes for input file parsers.

The MVP parsers (Excel, DOCX) implement the simple contract::

    load_requirements(path) -> List[Dict[str, Any]]

returning dicts shaped as ``{"id": int, "text": str, "locator": dict}``.
``BaseParser`` and ``ParserError`` provide a thin extension point for the Pilot
stage when parsers may need shared configuration, logging or post-processing
pipelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Union


class ParserError(RuntimeError):
    """Raised when an input file cannot be parsed into requirements."""


class BaseParser(ABC):
    """Abstract base class for input-file parsers.

    Subclasses must implement :meth:`load_requirements`. The default text
    post-processing (trim, drop empty, min length) is shared so different
    formats stay consistent.
    """

    DEFAULT_MIN_LENGTH = 5

    def __init__(self, min_length: int = DEFAULT_MIN_LENGTH, trim: bool = True) -> None:
        self.min_length = int(min_length)
        self.trim = bool(trim)

    @abstractmethod
    def load_requirements(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:  # pragma: no cover - abstract
        ...

    def _normalize(self, text: str) -> str:
        if text is None:
            return ""
        text = str(text)
        if self.trim:
            text = text.strip()
        return text

    def _keep(self, text: str) -> bool:
        return bool(text) and len(text) >= self.min_length
