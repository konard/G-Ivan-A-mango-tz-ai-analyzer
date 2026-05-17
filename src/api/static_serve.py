"""Safe local static serving for source PDF citations."""

from __future__ import annotations

from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
except ImportError:  # pragma: no cover - exercised only without API extras
    FastAPI = None  # type: ignore[assignment]
    FileResponse = None  # type: ignore[assignment]

    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

from src.ui.app import get_citations_config

app = FastAPI(title="Clarify Engine static docs") if FastAPI else None


def resolve_source_pdf(filename: str, source_dir: Path | None = None) -> Path:
    """Resolve a PDF filename under ``source_dir`` and reject traversal."""
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid document path")
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Document not found")

    root = (source_dir or get_citations_config()["source_dir"]).resolve()
    candidate = (root / filename).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document path") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    return candidate


if app is not None:

    @app.get("/docs/{filename}")
    def get_document(filename: str) -> FileResponse:
        """Return a source PDF by basename for citation links."""
        path = resolve_source_pdf(filename)
        return FileResponse(path, media_type="application/pdf", filename=path.name)
