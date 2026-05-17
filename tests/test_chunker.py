"""Unit tests for ``src/rag/chunker.py`` (BL-06, issue #92).

These tests pin the L1 chunking contract (512 / 64, section-aware splitting,
guardrails 384–768) introduced by issue #92. They use a deterministic
whitespace tokenizer so the tests stay hermetic — no network access to
Hugging Face is required to run them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence

import pytest

from src.rag import chunker as chunker_mod
from src.rag.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SECTION_AWARE,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    TokenChunker,
    chunk_text,
    load_chunk_config,
    split_sections,
)


class _WhitespaceTokenizer:
    """Deterministic tokenizer that splits on whitespace.

    Used in tests instead of the real bge-m3 tokenizer so the suite runs
    without network access. ``encode``/``decode`` round-trip via a small
    in-memory vocabulary.
    """

    def __init__(self) -> None:
        self._vocab: List[str] = []
        self._index: dict[str, int] = {}

    def _token_id(self, token: str) -> int:
        if token not in self._index:
            self._index[token] = len(self._vocab)
            self._vocab.append(token)
        return self._index[token]

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        tokens = re.findall(r"\S+", text)
        return [self._token_id(tok) for tok in tokens]

    def decode(
        self, token_ids: Sequence[int], skip_special_tokens: bool = True
    ) -> str:
        return " ".join(self._vocab[i] for i in token_ids)


# ---------------------------------------------------------------- defaults --


def test_l1_defaults_match_bl06_contract() -> None:
    """Defaults must align with the L1 targets locked in by issue #92."""
    assert DEFAULT_CHUNK_SIZE == 512
    assert DEFAULT_CHUNK_OVERLAP == 64
    assert MIN_CHUNK_SIZE == 384
    assert MAX_CHUNK_SIZE == 768
    assert DEFAULT_SECTION_AWARE is True


def test_default_chunker_uses_l1_targets() -> None:
    chunker = TokenChunker(tokenizer=_WhitespaceTokenizer())
    assert chunker.chunk_size == 512
    assert chunker.chunk_overlap == 64
    assert chunker.section_aware is True


# -------------------------------------------------------------- guardrails --


@pytest.mark.parametrize("size", [383, 769, 250, 50, 0])
def test_chunk_size_outside_guardrails_rejected(size: int) -> None:
    with pytest.raises(ValueError, match="chunk_size must be within"):
        TokenChunker(chunk_size=size, tokenizer=_WhitespaceTokenizer())


@pytest.mark.parametrize("size", [384, 512, 768])
def test_chunk_size_inside_guardrails_accepted(size: int) -> None:
    chunker = TokenChunker(
        chunk_size=size,
        chunk_overlap=min(64, size - 1),
        tokenizer=_WhitespaceTokenizer(),
    )
    assert chunker.chunk_size == size


def test_overlap_must_be_strictly_less_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        TokenChunker(
            chunk_size=512,
            chunk_overlap=512,
            tokenizer=_WhitespaceTokenizer(),
        )


# ------------------------------------------------------------- chunking ---


def _make_tokens(count: int) -> str:
    """Build a synthetic body of ``count`` whitespace tokens."""
    return " ".join(f"tok{i}" for i in range(count))


def test_chunk_returns_empty_for_empty_input() -> None:
    chunker = TokenChunker(tokenizer=_WhitespaceTokenizer(), section_aware=False)
    assert chunker.chunk("") == []
    assert chunker.chunk("   \n\t  ") == []


def test_chunk_respects_window_and_overlap() -> None:
    """A 1200-token body should slice into windows of 512 with step 448."""
    chunker = TokenChunker(
        chunk_size=512,
        chunk_overlap=64,
        section_aware=False,
        tokenizer=_WhitespaceTokenizer(),
    )
    text = _make_tokens(1200)
    chunks = chunker.chunk(text)
    # step = 512 - 64 = 448. Starts at 0, 448, 896. Last window 896..1200 (304 tokens).
    assert len(chunks) == 3
    assert chunks[0].startswith("tok0 tok1")
    assert chunks[0].endswith(f"tok{512 - 1}")
    # Overlap: the second chunk must repeat the last 64 tokens of the first.
    overlap_start = 512 - 64
    assert chunks[1].startswith(f"tok{overlap_start}")


def test_short_input_yields_single_chunk() -> None:
    chunker = TokenChunker(
        chunk_size=512,
        chunk_overlap=64,
        section_aware=False,
        tokenizer=_WhitespaceTokenizer(),
    )
    text = _make_tokens(100)
    chunks = chunker.chunk(text)
    assert len(chunks) == 1
    assert chunks[0].startswith("tok0")
    assert chunks[0].endswith("tok99")


# --------------------------------------------------- section-aware splits --


def test_split_sections_returns_input_when_no_headings() -> None:
    text = "Just running text without any heading markers."
    assert split_sections(text) == [text]


def test_split_sections_handles_markdown_headings() -> None:
    text = (
        "Intro paragraph before any heading.\n\n"
        "# Title One\n"
        "Body of section one.\n\n"
        "## Title Two\n"
        "Body of section two."
    )
    sections = split_sections(text)
    assert len(sections) == 3
    assert sections[0].startswith("Intro paragraph")
    assert sections[1].startswith("# Title One")
    assert "Body of section one" in sections[1]
    assert sections[2].startswith("## Title Two")
    assert "Body of section two" in sections[2]


def test_split_sections_handles_dotted_numeric_headings() -> None:
    text = (
        "7.3.6 Настройка SSO\n"
        "Откройте Личный кабинет.\n\n"
        "7.3.7 Проверка SSO\n"
        "Выполните вход через корпоративный портал."
    )
    sections = split_sections(text)
    assert len(sections) == 2
    assert sections[0].startswith("7.3.6 Настройка SSO")
    assert "Личный кабинет" in sections[0]
    assert sections[1].startswith("7.3.7 Проверка SSO")
    assert "корпоративный портал" in sections[1]


def test_split_sections_handles_caps_pdf_headers() -> None:
    text = (
        "Some body text.\n"
        "НАСТРОЙКА SSO\n"
        "Описание шагов настройки.\n"
        "SECURITY POLICY\n"
        "Описание политики безопасности."
    )
    sections = split_sections(text)
    # Preamble + two CAPS sections.
    assert len(sections) == 3
    assert sections[1].startswith("НАСТРОЙКА SSO")
    assert sections[2].startswith("SECURITY POLICY")


def test_section_aware_chunker_keeps_heading_with_section() -> None:
    """Heading must stay attached to the top of its first chunk."""
    heading = "7.3.6 Настройка SSO"
    body = _make_tokens(20)
    text = f"{heading}\n{body}"
    chunker = TokenChunker(
        chunk_size=512,
        chunk_overlap=64,
        section_aware=True,
        tokenizer=_WhitespaceTokenizer(),
    )
    chunks = chunker.chunk(text)
    assert chunks, "expected at least one chunk"
    assert chunks[0].startswith("7.3.6 Настройка SSO")


def test_section_aware_chunker_does_not_split_across_sections() -> None:
    """Two short adjacent sections must produce two separate chunks rather
    than one merged chunk."""
    text = (
        "# Section A\n"
        + _make_tokens(50)
        + "\n# Section B\n"
        + _make_tokens(50)
    )
    chunker = TokenChunker(
        chunk_size=512,
        chunk_overlap=64,
        section_aware=True,
        tokenizer=_WhitespaceTokenizer(),
    )
    chunks = chunker.chunk(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("# Section A")
    assert chunks[1].startswith("# Section B")


def test_section_aware_chunker_windows_long_sections() -> None:
    """A single section larger than chunk_size must still be windowed."""
    text = "# Long Section\n" + _make_tokens(1200)
    chunker = TokenChunker(
        chunk_size=512,
        chunk_overlap=64,
        section_aware=True,
        tokenizer=_WhitespaceTokenizer(),
    )
    chunks = chunker.chunk(text)
    # 1 heading + 1200 body tokens = 1202 tokens, step = 448.
    # Windows: 0..512, 448..960, 896..1202 -> 3 chunks.
    assert len(chunks) == 3
    assert chunks[0].startswith("# Long Section")


def test_section_aware_can_be_disabled_via_flag() -> None:
    text = "# Section A\n" + _make_tokens(20) + "\n# Section B\n" + _make_tokens(20)
    chunker = TokenChunker(
        chunk_size=512,
        chunk_overlap=64,
        section_aware=False,
        tokenizer=_WhitespaceTokenizer(),
    )
    chunks = chunker.chunk(text)
    # With section-aware disabled the whole body fits in one window.
    assert len(chunks) == 1


# ------------------------------------------------- config loading -------


def test_from_config_reads_l1_values_from_repo_yaml() -> None:
    """The shipping ``configs/embedding_config.yaml`` must declare the L1 targets."""
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "configs" / "embedding_config.yaml"
    cfg = load_chunk_config(str(config_path))
    assert cfg["chunk_size"] == 512
    assert cfg["chunk_overlap"] == 64
    assert cfg["min_chunk_size"] == 384
    assert cfg["max_chunk_size"] == 768
    assert cfg.get("section_aware_chunking") is True


def test_from_config_propagates_section_aware_flag(tmp_path: Path) -> None:
    config = tmp_path / "embedding_config.yaml"
    config.write_text(
        "chunk_size: 512\n"
        "chunk_overlap: 64\n"
        "model_name: BAAI/bge-m3\n"
        "section_aware_chunking: false\n",
        encoding="utf-8",
    )
    chunker = TokenChunker.from_config(
        config_path=str(config), tokenizer=_WhitespaceTokenizer()
    )
    assert chunker.section_aware is False


def test_chunk_text_helper_uses_l1_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The ``chunk_text`` convenience wrapper must also honour the config."""
    config = tmp_path / "embedding_config.yaml"
    config.write_text(
        "chunk_size: 512\nchunk_overlap: 64\nmodel_name: BAAI/bge-m3\n",
        encoding="utf-8",
    )
    text = _make_tokens(20)
    monkeypatch.setattr(
        chunker_mod,
        "_load_hf_tokenizer",
        lambda model_name: _WhitespaceTokenizer(),
    )
    chunks = chunk_text(text, config_path=str(config))
    assert len(chunks) == 1
    assert chunks[0].startswith("tok0")
