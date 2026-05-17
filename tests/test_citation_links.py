"""Tests for BL-09 clickable Markdown citations (issue #87).

Pins the contract of the citation helpers in :mod:`src.ui.app`:

* ``build_citation_link`` formats ``[source.pdf, стр. N](http://.../source.pdf#page=N)``
  and gracefully degrades when the page number is missing.
* ``_first_page_per_source`` picks the page from the highest-ranked chunk
  and ignores duplicates further down the result list.
* ``linkify_citations`` rewrites bare ``[filename.pdf]`` placeholders in
  the LLM answer, leaves already-linked Markdown alone, and refuses to
  invent links for sources that are not present in the retrieved chunks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType


def _ensure_streamlit_stub() -> None:
    stub = sys.modules.get("streamlit")
    if stub is None:
        stub = ModuleType("streamlit")
        sys.modules["streamlit"] = stub

    def _noop(*_args, **_kwargs):
        return None

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def _decorator(*_args, **_kwargs):
        def _wrap(fn):
            return fn

        return _wrap

    for attr in (
        "set_page_config",
        "title",
        "write",
        "header",
        "subheader",
        "caption",
        "info",
        "success",
        "warning",
        "error",
        "markdown",
        "divider",
        "selectbox",
        "button",
        "file_uploader",
        "download_button",
        "rerun",
        "link_button",
        "code",
        "json",
        "toggle",
        "slider",
        "text_area",
    ):
        if not hasattr(stub, attr):
            setattr(stub, attr, _noop)
    if not hasattr(stub, "session_state"):
        stub.session_state = {}
    if not hasattr(stub, "sidebar"):
        stub.sidebar = _Ctx()
    if not hasattr(stub, "expander"):
        stub.expander = lambda *_a, **_kw: _Ctx()
    if not hasattr(stub, "spinner"):
        stub.spinner = lambda *_a, **_kw: _Ctx()
    if not hasattr(stub, "cache_resource"):
        stub.cache_resource = _decorator


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_ensure_streamlit_stub()

from src.ui import app  # noqa: E402


def test_build_citation_link_includes_page_anchor(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "SIP_trunk-1.23.43.pdf").write_bytes(b"%PDF")
    link = app.build_citation_link(
        "SIP_trunk-1.23.43.pdf",
        7,
        base_url="http://localhost:8000/docs",
    )
    assert link == (
        "[SIP_trunk-1.23.43.pdf, стр. 7]"
        "(http://localhost:8000/docs/SIP_trunk-1.23.43.pdf#page=7)"
    )


def test_build_citation_link_falls_back_without_page(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    link = app.build_citation_link(
        "doc.pdf", None, base_url="http://localhost:8000/docs/"
    )
    assert link == "[doc.pdf](http://localhost:8000/docs/doc.pdf)"


def test_build_citation_link_ignores_non_positive_page(tmp_path: Path) -> None:
    link = app.build_citation_link("doc.pdf", 0)
    assert "#page=" not in link
    link = app.build_citation_link("doc.pdf", "abc")
    assert "#page=" not in link


def test_first_page_per_source_prefers_top_ranked_chunk() -> None:
    chunks = [
        {"source": "a.pdf", "metadata": {"page_number": 3}},
        {"source": "a.pdf", "metadata": {"page_number": 99}},
        {"source": "b.pdf", "page": 5},
        {"source": "", "metadata": {"page_number": 1}},
        {"source": "c.pdf", "metadata": {}},
    ]
    assert app._first_page_per_source(chunks) == {"a.pdf": 3, "b.pdf": 5}


def test_linkify_citations_rewrites_only_known_sources(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    chunks = [
        {"source": "SIP_trunk-1.23.43.pdf", "metadata": {"page_number": 12}},
    ]
    answer = (
        "Настройте транк, как описано в [SIP_trunk-1.23.43.pdf]. "
        "Сценарий из [unknown.pdf] недоступен."
    )
    rewritten = app.linkify_citations(
        answer,
        chunks,
        base_url="http://localhost:8000/docs",
    )
    expected_link = (
        "[SIP_trunk-1.23.43.pdf, стр. 12]"
        "(http://localhost:8000/docs/SIP_trunk-1.23.43.pdf#page=12)"
    )
    assert expected_link in rewritten
    # Unknown source MUST be left untouched (the UI never invents links).
    assert "[unknown.pdf]" in rewritten
    assert "(http://localhost:8000/docs/unknown.pdf" not in rewritten


def test_linkify_citations_includes_section_fallback_signature(tmp_path: Path) -> None:
    chunks = [
        {
            "source": "doc.pdf",
            "metadata": {
                "page_number": 2,
                "section_title": "MANGO OFFICE LK VATS Auth SSO",
                "section_number": "document",
                "section_fallback": "source_filename",
            },
        },
    ]

    rewritten = app.linkify_citations(
        "См. [doc.pdf].",
        chunks,
        base_url="http://localhost:8000/docs",
    )

    assert "doc.pdf, стр. 2, раздел: MANGO OFFICE LK VATS Auth SSO" in rewritten
    assert "#page=2" in rewritten


def test_linkify_citations_leaves_existing_markdown_links_alone(tmp_path: Path) -> None:
    chunks = [{"source": "doc.pdf", "metadata": {"page_number": 4}}]
    answer = "См. [doc.pdf](https://example.com/doc.pdf)."
    assert (
        app.linkify_citations(answer, chunks)
        == "См. [doc.pdf](https://example.com/doc.pdf)."
    )


def test_linkify_citations_returns_input_when_no_chunks(tmp_path: Path) -> None:
    assert app.linkify_citations("[doc.pdf] is the source.", []) == "[doc.pdf] is the source."
    assert app.linkify_citations("", [{"source": "a.pdf"}]) == ""


def test_ui_config_contains_citation_settings() -> None:
    cfg = app.get_citations_config()
    assert cfg["base_url"] == "http://localhost:8000/docs"
    assert cfg["source_dir"].name == "sources"
