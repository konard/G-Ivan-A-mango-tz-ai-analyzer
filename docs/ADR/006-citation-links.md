# ADR-006: Citation Links

## Status

Accepted

## Context

The KB UI previously rendered source citations as plain text or local
`file://` links. Pilot users need clickable citations that open the cited PDF
page through a predictable HTTP URL, while local development still serves files
from `knowledge_base/sources`.

## Decision

Citation link settings live in `configs/ui_config.yaml`:

```yaml
citations:
  base_url: "http://localhost:8000/docs"
  source_dir: "knowledge_base/sources"
```

`src/ui/app.py::build_citation_link()` creates Markdown links in the form
`[file.pdf, стр. 5](http://localhost:8000/docs/file.pdf#page=5)`. If the page
number is missing, invalid, or non-positive, the link falls back to the document
URL without a `#page=` anchor.

`src/api/static_serve.py` provides a minimal FastAPI endpoint
`GET /docs/{filename}` for local development. It accepts only PDF basenames,
resolves them under the configured `source_dir`, rejects path traversal, and
returns files with `application/pdf`.

## Consequences

The UI no longer depends on browser support for local `file://` links.
Production can replace `base_url` with a corporate static host or object
storage URL without changing UI code. The local static endpoint remains a
development helper and intentionally does not implement S3/CDN behavior.
