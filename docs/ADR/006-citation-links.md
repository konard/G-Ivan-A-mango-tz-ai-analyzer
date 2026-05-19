# ADR-006: Citation Links

## Status

Accepted (reaffirmed 2026-05-19 by BL-40 ADR-sync — see §History v1.1)

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

## Security Contract

- **`file://` is excluded** from rendered citations and from
  `build_citation_link()` output. Only `http(s)://` URLs derived from the
  configured `base_url` are produced; this is enforced by the
  link-construction code, not by Streamlit at render time.
- `base_url` and `source_dir` are sourced from
  [`configs/ui_config.yaml`](../../configs/ui_config.yaml) and must remain in
  sync. Production deployments override `base_url` to a corporate static host
  (`https://kb.mango-office.ru/docs` is the example commented in the config)
  and update `source_dir` only if the on-disk KB layout changes.
- `src/api/static_serve.py` accepts **PDF basenames only**, resolves them
  under the configured `source_dir`, rejects path traversal (`..`, absolute
  paths) and returns the file as `application/pdf`. It is a dev-only helper
  and is not exposed in production deployments.

## Consequences

The UI no longer depends on browser support for local `file://` links.
Production can replace `base_url` with a corporate static host or object
storage URL without changing UI code. The local static endpoint remains a
development helper and intentionally does not implement S3/CDN behavior.

## References

- [`configs/ui_config.yaml`](../../configs/ui_config.yaml) — `citations.base_url`, `citations.source_dir`.
- [`src/ui/app.py`](../../src/ui/app.py) — `build_citation_link()`.
- [`src/api/static_serve.py`](../../src/api/static_serve.py) — dev-only `GET /docs/{filename}` endpoint.

## History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-17 | First Accepted version: HTTP-based citation links, `configs/ui_config.yaml` SSoT, `base_url` / `source_dir` separation, dev static endpoint. |
| 1.1 | 2026-05-19 | BL-40 (issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)): ADR-sync. Added explicit §Security Contract (`file://` exclusion as a contract, not just side-effect; path traversal rejection in `static_serve.py`) and §References. No change to `base_url` / `source_dir` defaults; `configs/ui_config.yaml` values confirmed unchanged. |
