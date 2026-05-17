"""Token-based chunker for knowledge-base documents.

The chunker tokenises text with the same tokenizer used by the embedding model
(``BAAI/bge-m3`` by default) so the resulting chunks line up with what the
embedder actually consumes. Per BL-06 (issue #92) and
``configs/embedding_config.yaml`` the L1 chunking defaults are:

* chunk size: 384–768 tokens (default 512)
* chunk overlap: 64 tokens (≈ 12.5 % of the window)
* model: ``BAAI/bge-m3``
* section-aware preprocessing on by default

All chunking parameters are read **only** from ``configs/embedding_config.yaml``
— ``knowledge_base/indexing/chunk_config.yaml`` is intentionally absent (the
duplicate config was removed as part of issue #45).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_CONFIG_PATH = "configs/embedding_config.yaml"
DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
MIN_CHUNK_SIZE = 384
MAX_CHUNK_SIZE = 768
DEFAULT_SECTION_AWARE = True

# Heading patterns used by section-aware splitting (BL-06). Each pattern must
# anchor at the start of a line; the matched text is preserved at the top of
# the first chunk of its section so BL-02 metadata extraction stays stable.
_SECTION_HEADING_PATTERNS = (
    # Markdown ATX headings: "# Title", "## Title", up to six levels.
    re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE),
    # Dotted numeric sections: "7.3.6 Title", "1.2 Title.", up to five levels.
    re.compile(
        r"^\s*\d+(?:\.\d+){0,4}\.?\s+[^\n]{1,200}$",
        re.MULTILINE,
    ),
    # Explicit "Раздел N" / "Section N" prefixes used in localised PDFs.
    re.compile(
        r"^\s*(?:Раздел|Section)\s+\d+(?:\.\d+){0,4}\s+[^\n]{1,200}$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # All-caps PDF headers: "НАСТРОЙКА SSO" / "SECURITY POLICY". At least five
    # characters of uppercase letters / spaces / digits to avoid matching short
    # acronyms inside running text.
    re.compile(r"^\s*[A-ZА-ЯЁ][A-ZА-ЯЁ0-9 \-]{4,}$", re.MULTILINE),
)


def load_chunk_config(config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH) -> Dict[str, Any]:
    """Read the chunking parameters from ``embedding_config.yaml``.

    Returns an empty dict if the file is missing or unreadable. Callers should
    apply :data:`DEFAULT_CHUNK_SIZE` / :data:`DEFAULT_CHUNK_OVERLAP` as fallbacks.
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning("Chunker config not found at %s; using defaults.", path)
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}


def _load_hf_tokenizer(model_name: str):
    """Load the Hugging Face tokenizer for ``model_name``.

    Raises:
        RuntimeError: When ``transformers`` is unavailable or the model cannot
            be downloaded. Strict mode: no silent fallback to whitespace
            tokenisation in production code paths.
    """
    try:
        from transformers import AutoTokenizer  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Tokenizer unavailable: the `transformers` package is required for "
            "the bge-m3 tokenizer. Install `sentence-transformers` to pull it in."
        ) from exc
    try:
        return AutoTokenizer.from_pretrained(model_name)
    except Exception as exc:  # noqa: BLE001 - rethrow as RuntimeError for callers
        raise RuntimeError(
            f"Tokenizer unavailable: could not load `{model_name}` ({exc})."
        ) from exc


def split_sections(text: str) -> List[str]:
    """Split ``text`` on heading boundaries while keeping each heading attached
    to the section it introduces.

    Returns the original text as a single-element list when no heading is
    detected. Empty / whitespace-only segments are dropped so the caller can
    iterate without filtering.

    The function is deterministic and does not depend on the tokenizer — it
    only finds heading line spans and slices the input string. The token
    window is applied separately by :meth:`TokenChunker.chunk`.
    """
    if not text:
        return []

    heading_starts: List[int] = []
    for pattern in _SECTION_HEADING_PATTERNS:
        for match in pattern.finditer(text):
            heading_starts.append(match.start())
    if not heading_starts:
        return [text]

    # Deduplicate and sort: a single line may match more than one heading
    # pattern (e.g. "## 7.3.6 Title" satisfies both the Markdown and dotted
    # numeric rules). We only need the unique cut points.
    cut_points = sorted(set(heading_starts))

    # If the document starts with body text before the first heading, keep
    # that preamble as its own section so we don't merge unrelated content.
    if cut_points[0] != 0:
        cut_points.insert(0, 0)

    sections: List[str] = []
    for idx, start in enumerate(cut_points):
        end = cut_points[idx + 1] if idx + 1 < len(cut_points) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            sections.append(chunk)
    return sections


class TokenChunker:
    """Split text into overlapping chunks aligned with a Hugging Face tokenizer.

    Args:
        chunk_size: Tokens per chunk. Must lie within
            ``[MIN_CHUNK_SIZE, MAX_CHUNK_SIZE]`` (384–768) per BL-06 guardrails.
        chunk_overlap: Tokens of overlap between consecutive chunks. Must be
            strictly less than ``chunk_size``.
        model_name: Embedding model name used to fetch the matching tokenizer.
        tokenizer: Optional pre-built tokenizer. When ``None`` the tokenizer is
            lazily loaded from Hugging Face on first use.
        section_aware: When ``True`` the input is first split on heading
            boundaries (see :func:`split_sections`) and each section is then
            token-windowed independently. Headings stay attached to the body
            of their section, so BL-02 section metadata stays stable.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        model_name: str = DEFAULT_MODEL,
        tokenizer: Optional[Any] = None,
        section_aware: bool = DEFAULT_SECTION_AWARE,
    ) -> None:
        if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
            raise ValueError(
                f"chunk_size must be within [{MIN_CHUNK_SIZE}, {MAX_CHUNK_SIZE}] "
                f"tokens (got {chunk_size})."
            )
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be non-negative and strictly smaller than chunk_size."
            )
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = int(chunk_overlap)
        self.model_name = model_name
        self.section_aware = bool(section_aware)
        self._tokenizer = tokenizer

    @classmethod
    def from_config(
        cls,
        config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
        tokenizer: Optional[Any] = None,
    ) -> "TokenChunker":
        cfg = load_chunk_config(config_path)
        chunk_size = int(cfg.get("chunk_size", DEFAULT_CHUNK_SIZE))
        chunk_overlap = int(cfg.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP))
        model_name = str(cfg.get("model_name", DEFAULT_MODEL))
        section_aware = bool(cfg.get("section_aware_chunking", DEFAULT_SECTION_AWARE))
        return cls(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=model_name,
            tokenizer=tokenizer,
            section_aware=section_aware,
        )

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self._tokenizer = _load_hf_tokenizer(self.model_name)
        return self._tokenizer

    def _encode(self, text: str) -> Sequence[int]:
        tok = self.tokenizer
        encode = getattr(tok, "encode", None)
        if encode is None:
            raise RuntimeError("Tokenizer does not expose an `encode` method")
        return encode(text, add_special_tokens=False)

    def _decode(self, token_ids: Sequence[int]) -> str:
        tok = self.tokenizer
        decode = getattr(tok, "decode", None)
        if decode is None:
            raise RuntimeError("Tokenizer does not expose a `decode` method")
        return decode(list(token_ids), skip_special_tokens=True)

    def _chunk_segment(self, text: str) -> List[str]:
        """Apply the token window to a single (already section-split) segment."""
        token_ids = list(self._encode(text))
        if not token_ids:
            return []
        step = max(1, self.chunk_size - self.chunk_overlap)
        chunks: List[str] = []
        start = 0
        while start < len(token_ids):
            end = min(start + self.chunk_size, len(token_ids))
            slice_ids = token_ids[start:end]
            decoded = self._decode(slice_ids).strip()
            if decoded:
                chunks.append(_normalize_whitespace(decoded))
            if end >= len(token_ids):
                break
            start += step
        return chunks

    def chunk(self, text: str) -> List[str]:
        """Return overlapping ``chunk_size``-token slices of ``text``.

        When :attr:`section_aware` is ``True`` the input is first cut on
        heading boundaries and each resulting section is windowed separately
        so the heading stays at the top of its first chunk. Empty input
        yields an empty list. Whitespace-only chunks are dropped.
        """
        if not text or not text.strip():
            return []
        segments = split_sections(text) if self.section_aware else [text]
        chunks: List[str] = []
        for segment in segments:
            chunks.extend(self._chunk_segment(segment))
        return chunks


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(
    text: str,
    config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
    tokenizer: Optional[Any] = None,
) -> List[str]:
    """Convenience wrapper: load config, instantiate :class:`TokenChunker`, chunk."""
    return TokenChunker.from_config(config_path=config_path, tokenizer=tokenizer).chunk(text)
