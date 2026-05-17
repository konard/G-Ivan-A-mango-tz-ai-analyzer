from __future__ import annotations

from pathlib import Path

import pytest

from src.api.static_serve import HTTPException, resolve_source_pdf


def test_resolve_source_pdf_accepts_pdf_basename(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")

    assert resolve_source_pdf("doc.pdf", tmp_path) == pdf.resolve()


@pytest.mark.parametrize(
    "filename",
    ["../doc.pdf", "nested/doc.pdf", "..\\doc.pdf", "", "doc.txt"],
)
def test_resolve_source_pdf_rejects_invalid_paths(
    tmp_path: Path, filename: str
) -> None:
    with pytest.raises(HTTPException):
        resolve_source_pdf(filename, tmp_path)
