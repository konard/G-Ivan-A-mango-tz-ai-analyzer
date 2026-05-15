"""DOCX parser for tender requirements (ТЗ).

Extracts atomic requirements from a ``.docx`` file by walking paragraphs and
tables. Each non-empty text block (after trimming) becomes a requirement.
For tables, every cell is treated as an independent candidate.

The parser is intentionally permissive — it is designed for the MVP phase
where ТЗ layouts vary widely. Downstream the LLM classifier is responsible
for handling noisy fragments.

If ``python-docx`` is not installed, the parser raises :class:`ParserError`
so callers can degrade gracefully (e.g. ask the user to upload an ``.xlsx``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Union

from src.parsers.base_parser import BaseParser, ParserError

logger = logging.getLogger(__name__)


class DocxParser(BaseParser):
    """Parse requirements from a ``.docx`` file into a list of dicts."""

    def load_requirements(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Union[int, str]]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"DOCX file not found: {path}")
        if path.suffix.lower() != ".docx":
            raise ParserError(f"Expected a .docx file, got: {path.suffix}")

        try:
            from docx import Document  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise ParserError(
                "python-docx is required to parse .docx files. "
                "Install it with `pip install python-docx`."
            ) from exc

        try:
            document = Document(str(path))
        except Exception as exc:  # noqa: BLE001
            raise ParserError(f"Failed to read DOCX file {path}: {exc}") from exc

        candidates: List[str] = []
        for paragraph in document.paragraphs:
            candidates.append(self._normalize(paragraph.text))
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    candidates.append(self._normalize(cell.text))

        requirements: List[Dict[str, Union[int, str]]] = []
        seen: set[str] = set()
        for text in candidates:
            if not self._keep(text):
                continue
            if text in seen:
                continue
            seen.add(text)
            requirements.append({"id": len(requirements) + 1, "text": text})

        if not requirements:
            raise ParserError(f"DOCX file {path} did not yield any requirements")

        logger.info("Loaded %d requirements from %s", len(requirements), path)
        return requirements


def load_requirements(
    file_path: Union[str, Path],
) -> List[Dict[str, Union[int, str]]]:
    """Module-level helper used by the central parsers dispatcher."""
    return DocxParser().load_requirements(file_path)
