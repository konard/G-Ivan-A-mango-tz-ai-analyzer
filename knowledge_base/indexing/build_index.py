#!/usr/bin/env python3
"""Knowledge-base indexer.

Loads documents from ``knowledge_base/sources``, chunks them with the bge-m3
tokenizer (see :mod:`src.rag.chunker`), embeds them with
``sentence-transformers``, persists vectors into ChromaDB and finally syncs
``knowledge_base/metadata/source_registry.csv`` with the canonical schema
``filename, version, sha256_hash, indexed_date, status, coverage`` (issues #45,
#48).

Hashing uses SHA-256 (the MD5 path from previous revisions was removed because
MD5 is no longer acceptable for integrity checks).

All chunking parameters are read from ``configs/embedding_config.yaml`` — there
is no duplicate ``chunk_config.yaml`` under ``knowledge_base/indexing``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "embedding_config.yaml"
PRODUCTS_CONFIG_PATH = BASE_DIR / "configs" / "products.yaml"
SOURCES_DIR = BASE_DIR / "knowledge_base" / "sources"
METADATA_DIR = BASE_DIR / "knowledge_base" / "metadata"
REGISTRY_FILE = METADATA_DIR / "source_registry.csv"
REGISTRY_FIELDS = [
    "filename",
    "version",
    "sha256_hash",
    "indexed_date",
    "status",
    "coverage",
]

# BL-02 / BL-16a / NFR-02: every persisted chunk MUST carry these keys.
REQUIRED_METADATA_KEYS: Tuple[str, ...] = (
    "source",
    "chunk_idx",
    "page_number",
    "section_title",
    "section_number",
    "product",
    "section_inherited",
    "parent_id",
    "section_id",
    "parent_text",
    "related_sections",
    "prerequisites",
    "see_also",
    "dependencies_extracted",
)

COVERAGE_METADATA_KEYS: Tuple[str, ...] = (
    "source",
    "chunk_idx",
    "page_number",
    "section_title",
    "section_number",
    "product",
)

DEFAULT_METADATA_COVERAGE_MIN = 0.65
DEFAULT_SECTION_MAX_PAGES_WITHOUT_HEADING = 6

# Built-in filename-prefix → product mapping. Overridable via configs/products.yaml.
DEFAULT_PRODUCT_MAP: Dict[str, str] = {
    "click2call": "Click2Call",
    "lk_manual": "ЛК",
    "mango_office_lk_vats_auth_sso": "ВАТС",
    "mangooffice_vpbx_api": "VPBX API",
    "qm_manual": "Quality Management",
    "rechevaya-analitika": "Речевая аналитика",
    "rolevaya-model-vats": "ВАТС",
    "sip_trunk": "SIP Trunk",
}

# Heading patterns (run in order; first match wins):
#  1) "# 1.2.3 Title" or "## 1.2 Title."
#  2) "1.2.3 Title" or "1.2 Title."
#  3) "Раздел 4.2 Title"
#  4) "Section 4.2 Title"
_HEADING_PATTERNS = (
    re.compile(r"^\s*#{1,6}\s*(\d+(?:\.\d+){0,4})\.?\s+([A-ZА-ЯЁ][^\n]{0,200})", re.MULTILINE),
    re.compile(r"^\s*(\d+(?:\.\d+){0,4})\.?\s+([A-ZА-ЯЁ][^\n]{0,200})", re.MULTILINE),
    re.compile(r"^\s*Раздел\s+(\d+(?:\.\d+){0,4})\s+([^\n]{0,200})", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Section\s+(\d+(?:\.\d+){0,4})\s+([^\n]{0,200})", re.MULTILINE | re.IGNORECASE),
)


# ---------------------------------------------------------------- logging --
class _RunIdJsonFormatter(logging.Formatter):
    """Minimal JSON log line including ``run_id`` for traceability."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "run_id": self._run_id,
            "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(run_id: str) -> logging.Logger:
    logger = logging.getLogger("kb_indexer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_RunIdJsonFormatter(run_id))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# --------------------------------------------------------------- helpers --
def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def sha256_hash(file_path: Path) -> str:
    """Compute the SHA-256 digest of ``file_path`` in 64 KiB blocks."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_text(file_path: Path, logger: logging.Logger) -> Optional[str]:
    """Read a single KB source file as plain text.

    Supported extensions: ``.txt``, ``.md``, ``.pdf``. ``.xlsx`` files are
    reported as unsupported (the MVP indexer ingests text-only sources).
    """
    suffix = file_path.suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError:
                logger.warning("pypdf not installed, skipping PDF: %s", file_path)
                return None
            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        logger.info("Unsupported extension %s, skipping.", suffix)
        return None
    except Exception as exc:  # noqa: BLE001 - log and skip
        logger.error("Error reading %s: %s", file_path, exc)
        return None


def load_pages(file_path: Path, logger: logging.Logger) -> Optional[List[Tuple[int, str]]]:
    """Read a KB source as ``[(page_number, text), ...]`` for BL-02 metadata.

    Non-PDF formats are treated as a single logical page (``page_number=1``).
    Returns ``None`` if the file cannot be read.
    """
    suffix = file_path.suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            return [(1, text)]
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError:
                logger.warning("pypdf not installed, skipping PDF: %s", file_path)
                return None
            reader = PdfReader(str(file_path))
            pages: List[Tuple[int, str]] = []
            for idx, page in enumerate(reader.pages, start=1):
                pages.append((idx, page.extract_text() or ""))
            return pages
        logger.info("Unsupported extension %s, skipping.", suffix)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Error reading pages from %s: %s", file_path, exc)
        return None


# ----------------------------------------------------- BL-02 metadata helpers --
def load_product_map(config_path: Path = PRODUCTS_CONFIG_PATH) -> Dict[str, str]:
    """Load filename-prefix → product name mapping.

    Format of ``configs/products.yaml`` (optional, lowercase prefixes)::

        prefixes:
          click2call: "Click2Call"
          mangooffice_vpbx_api: "VPBX API"

    Falls back to :data:`DEFAULT_PRODUCT_MAP` when the file is missing or
    invalid. Returned mapping is always non-empty.
    """
    mapping = dict(DEFAULT_PRODUCT_MAP)
    if not config_path.exists():
        return mapping
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return mapping
    prefixes = data.get("prefixes") if isinstance(data, dict) else None
    if isinstance(prefixes, dict):
        for key, value in prefixes.items():
            if isinstance(key, str) and isinstance(value, str) and value.strip():
                mapping[key.lower()] = value.strip()
    return mapping


def infer_product(filename: str, product_map: Optional[Dict[str, str]] = None) -> str:
    """Infer the product label from ``filename`` using the longest matching prefix."""
    mapping = product_map or DEFAULT_PRODUCT_MAP
    stem = Path(filename).stem.lower()
    best_key = ""
    best_value = "unknown"
    for prefix, product in mapping.items():
        prefix_lc = prefix.lower()
        if stem.startswith(prefix_lc) and len(prefix_lc) > len(best_key):
            best_key = prefix_lc
            best_value = product
    return best_value


@dataclass
class _SectionFrame:
    """A section heading active for following chunks in the same document."""

    number: str
    title: str
    depth: int
    page_number: int


@dataclass
class _SectionResolution:
    """Resolved section metadata for one chunk."""

    number: str = ""
    title: str = ""
    inherited: bool = False
    fallback: str = "none"


@dataclass
class SectionPropagationState:
    """Stateful metadata inheritance for chunks from one source document.

    The state is intentionally per-document: callers should create a new
    instance for every source file so a heading from one PDF cannot bleed into
    the next. Numbered headings update a small hierarchy stack; later chunks
    without headings inherit the nearest active section until the configured
    page-distance guard resets the context.
    """

    enabled: bool = True
    max_pages_without_heading: int = DEFAULT_SECTION_MAX_PAGES_WITHOUT_HEADING
    fallback_to_document_title: bool = True
    fallback_section_number: str = "document"
    _stack: List[_SectionFrame] = field(default_factory=list, init=False)
    headings_detected: int = 0
    inherited_chunks: int = 0
    fallback_chunks: int = 0
    stale_resets: int = 0
    unassigned_chunks: int = 0

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "SectionPropagationState":
        raw = config.get("section_propagation") if isinstance(config, dict) else {}
        cfg = raw if isinstance(raw, dict) else {}
        return cls(
            enabled=bool(cfg.get("enabled", True)),
            max_pages_without_heading=_coerce_int(
                cfg.get("max_pages_without_heading"),
                DEFAULT_SECTION_MAX_PAGES_WITHOUT_HEADING,
            ),
            fallback_to_document_title=bool(cfg.get("fallback_to_document_title", True)),
            fallback_section_number=str(cfg.get("fallback_section_number", "document")),
        )

    def resolve(
        self,
        text: str,
        *,
        page_number: int,
        source: str,
    ) -> _SectionResolution:
        number, title = extract_section(text)
        page = _coerce_int(page_number, 1)

        if not self.enabled:
            return _SectionResolution(number=number, title=title)

        if number or title:
            frame = _SectionFrame(
                number=number,
                title=title,
                depth=_section_depth(number),
                page_number=page,
            )
            self._push_heading(frame)
            self.headings_detected += 1
            return _SectionResolution(number=number, title=title)

        current = self._current_frame()
        if current and not self._is_stale(current, page):
            self.inherited_chunks += 1
            return _SectionResolution(
                number=current.number,
                title=current.title,
                inherited=True,
            )
        if current:
            self._stack.clear()
            self.stale_resets += 1

        fallback = self._source_fallback(source)
        if fallback:
            self.fallback_chunks += 1
            return fallback

        self.unassigned_chunks += 1
        return _SectionResolution()

    def stats(self) -> Dict[str, int]:
        return {
            "headings_detected": self.headings_detected,
            "inherited_chunks": self.inherited_chunks,
            "fallback_chunks": self.fallback_chunks,
            "stale_resets": self.stale_resets,
            "unassigned_chunks": self.unassigned_chunks,
        }

    def _push_heading(self, frame: _SectionFrame) -> None:
        while self._stack and self._stack[-1].depth >= frame.depth:
            self._stack.pop()
        self._stack.append(frame)

    def _current_frame(self) -> Optional[_SectionFrame]:
        return self._stack[-1] if self._stack else None

    def _is_stale(self, frame: _SectionFrame, page_number: int) -> bool:
        if self.max_pages_without_heading < 0:
            return False
        return page_number - frame.page_number > self.max_pages_without_heading

    def _source_fallback(self, source: str) -> Optional[_SectionResolution]:
        if not self.fallback_to_document_title:
            return None
        title = _title_from_source(source)
        if not title:
            return None
        return _SectionResolution(
            number=self.fallback_section_number,
            title=title,
            inherited=False,
            fallback="source_filename",
        )


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _section_depth(section_number: str) -> int:
    if not section_number:
        return 1
    return section_number.count(".") + 1


def _title_from_source(source: str) -> str:
    stem = Path(source or "").stem
    title = re.sub(r"[_-]+", " ", stem)
    return re.sub(r"\s+", " ", title).strip()[:200]


def extract_section(text: str) -> Tuple[str, str]:
    """Return ``(section_number, section_title)`` for the first heading in ``text``.

    Falls back to ``("", "")`` when no heading is detected. Section number is
    the dotted numeric prefix (e.g. ``"4.2"``); section title is the trailing
    heading text trimmed and capped at 200 characters.
    """
    for pattern in _HEADING_PATTERNS:
        match = pattern.search(text or "")
        if match:
            number = match.group(1).strip()
            title = re.sub(r"\s+", " ", match.group(2)).strip().rstrip(".")
            return number, title[:200]
    return "", ""


def build_chunk_metadata(
    source: str,
    chunk_idx: int,
    page_number: int,
    text: str,
    *,
    product_map: Optional[Dict[str, str]] = None,
    section_state: Optional[SectionPropagationState] = None,
) -> Dict[str, Any]:
    """Assemble the BL-02 metadata dict for a single chunk.

    Guarantees that every key in :data:`REQUIRED_METADATA_KEYS` is present.
    Missing values are emitted as empty strings (``page_number`` defaults to
    1 so the value type stays an int) so downstream consumers can count
    coverage without branching on ``None``. When ``section_state`` is supplied,
    chunks without a local heading inherit the nearest document-level section
    until the state's page-distance guard resets the context.
    """
    if section_state is not None:
        section = section_state.resolve(
            text,
            page_number=page_number,
            source=source,
        )
    else:
        number, title = extract_section(text)
        section = _SectionResolution(number=number, title=title)
    product = infer_product(source, product_map=product_map)
    parent_id = _build_parent_id(source, section.number, section.title)
    return {
        "source": source,
        "chunk_idx": int(chunk_idx),
        "page_number": int(page_number) if page_number else 1,
        "section_title": section.title,
        "section_number": section.number,
        "product": product,
        "section_inherited": section.inherited,
        "section_fallback": section.fallback,
        "parent_id": parent_id,
        "section_id": parent_id,
        "parent_text": "",
        "related_sections": "",
        "prerequisites": "",
        "see_also": "",
        "dependencies_extracted": False,
    }


def _build_parent_id(source: str, section_number: str, section_title: str) -> str:
    number = re.sub(r"\s+", " ", section_number or "").strip()
    title = re.sub(r"\s+", " ", section_title or "").strip()
    if number or title:
        return f"{source}::{number}::{title}"
    return f"{source}::document"


# --------------------------------------------------------------- registry --
def _read_registry() -> Dict[str, Dict[str, str]]:
    """Load the existing registry (filename → row dict). Empty when missing."""
    if not REGISTRY_FILE.exists():
        return {}
    rows: Dict[str, Dict[str, str]] = {}
    with open(REGISTRY_FILE, "r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row.get("filename")
            if name:
                rows[name] = {field: row.get(field, "") for field in REGISTRY_FIELDS}
    return rows


def _write_registry(rows: Dict[str, Dict[str, str]]) -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: r.get("filename", ""))
    with open(REGISTRY_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REGISTRY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)


def update_registry(
    filename: str,
    *,
    status: str,
    sha256: str,
    version: str = "",
    coverage: str = "",
) -> None:
    """Upsert a row in ``source_registry.csv`` using the canonical schema.

    Pre-existing ``version`` / ``coverage`` values are preserved when the
    caller does not override them — those columns describe the source rather
    than the indexing run.
    """
    rows = _read_registry()
    existing = rows.get(filename, {})
    rows[filename] = {
        "filename": filename,
        "version": version or existing.get("version", "1.0"),
        "sha256_hash": sha256,
        "indexed_date": date.today().isoformat(),
        "status": status,
        "coverage": coverage or existing.get("coverage", ""),
    }
    _write_registry(rows)


# --------------------------------------------------------------- pipeline --
def build_chunker(config_path: Path = CONFIG_PATH):
    """Create the configured :class:`src.rag.chunker.TokenChunker` once per run."""
    sys.path.insert(0, str(BASE_DIR))  # ensure ``src`` import works in CLI mode
    from src.rag.chunker import TokenChunker

    return TokenChunker.from_config(config_path=str(config_path))


def build_chunks(text: str, config_path: Path = CONFIG_PATH, chunker: Any = None) -> List[str]:
    """Split ``text`` into chunks using :class:`src.rag.chunker.TokenChunker`."""
    active_chunker = chunker or build_chunker(config_path=config_path)
    return active_chunker.chunk(text)


def _metadata_coverage(metadatas: List[Dict[str, Any]]) -> float:
    """Return the fraction of chunks with complete searchable metadata.

    A chunk counts as "covered" when **all** values in
    :data:`COVERAGE_METADATA_KEYS` are non-empty strings or non-zero ints.
    The boolean audit flag ``section_inherited`` is required on persisted
    metadata but intentionally excluded from the ratio because ``False`` is a
    valid direct-heading value.
    """
    if not metadatas:
        return 0.0
    full = 0
    for meta in metadatas:
        if all(_metadata_value_present(meta, key) for key in COVERAGE_METADATA_KEYS):
            full += 1
    return full / len(metadatas)


def _metadata_value_present(meta: Dict[str, Any], key: str) -> bool:
    value = meta.get(key)
    if key == "chunk_idx":
        return value is not None and value != ""
    if key == "page_number":
        return _coerce_int(value, 0) > 0
    return value not in (None, "")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract-dependencies",
        action="store_true",
        help="Enrich chunk metadata with BL-14 dependency/cross-reference fields.",
    )
    parser.add_argument(
        "--dependency-use-ollama",
        action="store_true",
        help="Use local Ollama in addition to regex dependency extraction.",
    )
    parser.add_argument(
        "--dependency-ollama-base-url",
        default="http://localhost:11434",
        help="Base URL for local Ollama when --dependency-use-ollama is set.",
    )
    parser.add_argument(
        "--dependency-ollama-model",
        default="qwen2.5:7b-instruct-q4_K_M",
        help="Ollama model for dependency extraction.",
    )
    parser.add_argument(
        "--dependency-min-related-coverage",
        type=float,
        default=0.0,
        help="Fail when related_sections coverage for marker chunks is below this ratio.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    run_id = str(uuid.uuid4())
    logger = setup_logging(run_id)
    logger.info("KB indexing started (run_id=%s)", run_id)

    config = load_config()
    model_name = str(config.get("model_name", "BAAI/bge-m3"))
    persist_dir = str(config.get("vector_store", {}).get("persist_directory", BASE_DIR / "chroma_data"))
    collection_name = str(config.get("vector_store", {}).get("collection_name", "clarify_engine_kb"))
    metadata_coverage_min = float(
        config.get("metadata_coverage_min", DEFAULT_METADATA_COVERAGE_MIN)
    )
    product_map = load_product_map()
    chunker = build_chunker()
    dependency_settings = None
    dependency_stats = None
    dependency_helpers = None
    if args.extract_dependencies:
        sys.path.insert(0, str(BASE_DIR))
        from scripts.tools import extract_dependencies as dependency_helpers

        dependency_settings = dependency_helpers.ExtractionSettings(
            use_ollama=args.dependency_use_ollama,
            ollama_base_url=args.dependency_ollama_base_url,
            ollama_model=args.dependency_ollama_model,
        )
        dependency_stats = dependency_helpers.ExtractionStats()

    if not SOURCES_DIR.exists():
        logger.error("Sources directory not found: %s", SOURCES_DIR)
        return 1

    files = sorted(
        p for p in SOURCES_DIR.glob("*") if p.is_file() and not p.name.startswith(".")
    )
    if not files:
        logger.warning("No source files found in %s", SOURCES_DIR)
        return 0

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import chromadb  # type: ignore
    except ImportError as exc:
        logger.error(
            "ML dependencies missing (%s). Install requirements.txt before running.",
            exc,
        )
        return 2

    logger.info("Loading embedding model %s", model_name)
    embedder = SentenceTransformer(model_name)
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name=collection_name)

    ids: List[str] = []
    docs: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for path in files:
        logger.info("Processing %s", path.name)
        pages = load_pages(path, logger)
        if not pages:
            update_registry(path.name, status="Skipped", sha256=sha256_hash(path))
            continue

        chunk_counter = 0
        section_state = SectionPropagationState.from_config(config)
        for page_number, page_text in pages:
            if not page_text or not page_text.strip():
                continue
            chunks = build_chunks(page_text, chunker=chunker)
            if not chunks:
                continue
            for chunk in chunks:
                meta = build_chunk_metadata(
                    source=path.name,
                    chunk_idx=chunk_counter,
                    page_number=page_number,
                    text=chunk,
                    product_map=product_map,
                    section_state=section_state,
                )
                if dependency_helpers is not None and dependency_settings is not None:
                    dependency_stats.total_chunks += 1
                    dependency_stats.processed_chunks += 1
                    has_markers = dependency_helpers.contains_dependency_markers(chunk)
                    if has_markers:
                        dependency_stats.chunks_with_markers += 1
                    meta = dependency_helpers.enrich_metadata(
                        meta,
                        chunk,
                        settings=dependency_settings,
                    )
                    if has_markers and meta.get("related_sections"):
                        dependency_stats.chunks_with_related_sections += 1
                ids.append(f"{path.stem}__{chunk_counter}")
                docs.append(chunk)
                metadatas.append(meta)
                chunk_counter += 1

        if chunk_counter == 0:
            update_registry(path.name, status="Skipped", sha256=sha256_hash(path))
            continue

        doc_parent_texts: Dict[str, str] = {}
        doc_meta_start = len(metadatas) - chunk_counter
        for idx in range(doc_meta_start, len(metadatas)):
            parent_id = str(metadatas[idx].get("parent_id") or "")
            if not parent_id:
                continue
            doc_parent_texts[parent_id] = (
                f"{doc_parent_texts.get(parent_id, '')}\n\n{docs[idx]}".strip()
            )
        for idx in range(doc_meta_start, len(metadatas)):
            parent_id = str(metadatas[idx].get("parent_id") or "")
            metadatas[idx]["parent_text"] = doc_parent_texts.get(parent_id, docs[idx])

        logger.info("→ %d chunks (pages=%d)", chunk_counter, len(pages))
        logger.info(
            "Section propagation for %s: headings=%d inherited=%d fallback=%d "
            "stale_resets=%d unassigned=%d",
            path.name,
            section_state.headings_detected,
            section_state.inherited_chunks,
            section_state.fallback_chunks,
            section_state.stale_resets,
            section_state.unassigned_chunks,
        )
        update_registry(path.name, status="Indexed", sha256=sha256_hash(path))

    if not docs:
        logger.warning("No chunks to index — nothing to persist.")
        return 0

    coverage = _metadata_coverage(metadatas)
    logger.info(
        "Metadata coverage (BL-02, target ≥ %.2f): %.4f",
        metadata_coverage_min,
        coverage,
    )
    if coverage < metadata_coverage_min:
        logger.warning(
            "Metadata coverage %.4f is below the NFR-02 / BL-02 target of %.2f.",
            coverage,
            metadata_coverage_min,
        )

    if dependency_stats is not None:
        logger.info("Dependency extraction stats: %s", dependency_stats.to_dict())
        if (
            dependency_stats.chunks_with_markers > 0
            and dependency_stats.related_section_coverage
            < float(args.dependency_min_related_coverage)
        ):
            logger.error(
                "Dependency related_sections coverage %.4f is below threshold %.4f.",
                dependency_stats.related_section_coverage,
                float(args.dependency_min_related_coverage),
            )
            return 3

    logger.info("Embedding %d chunks", len(docs))
    embeddings = embedder.encode(docs, show_progress_bar=False).tolist()

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
            documents=docs[i : i + batch_size],
        )

    logger.info("KB indexing finished (chunks=%d, collection=%s)", len(docs), collection_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
