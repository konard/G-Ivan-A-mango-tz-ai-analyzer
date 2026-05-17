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

import csv
import hashlib
import json
import logging
import re
import sys
import uuid
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
)

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
#  1) "1.2.3 Title" or "1.2 Title."
#  2) "Раздел 4.2 Title"
#  3) "Section 4.2 Title"
_HEADING_PATTERNS = (
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
) -> Dict[str, Any]:
    """Assemble the BL-02 metadata dict for a single chunk.

    Guarantees that every key in :data:`REQUIRED_METADATA_KEYS` is present.
    Missing values are emitted as empty strings (``page_number`` defaults to
    1 so the value type stays an int) so downstream consumers can count
    coverage without branching on ``None``.
    """
    number, title = extract_section(text)
    product = infer_product(source, product_map=product_map)
    return {
        "source": source,
        "chunk_idx": int(chunk_idx),
        "page_number": int(page_number) if page_number else 1,
        "section_title": title,
        "section_number": number,
        "product": product,
    }


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
        writer = csv.DictWriter(fh, fieldnames=REGISTRY_FIELDS)
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
def build_chunks(text: str, config_path: Path = CONFIG_PATH) -> List[str]:
    """Split ``text`` into chunks using :class:`src.rag.chunker.TokenChunker`."""
    sys.path.insert(0, str(BASE_DIR))  # ensure ``src`` import works in CLI mode
    from src.rag.chunker import TokenChunker

    return TokenChunker.from_config(config_path=str(config_path)).chunk(text)


def _metadata_coverage(metadatas: List[Dict[str, Any]]) -> float:
    """Return the fraction of chunks that carry every BL-02 required key.

    A chunk counts as "covered" when **all** values in
    :data:`REQUIRED_METADATA_KEYS` are non-empty strings or non-zero ints.
    Reported via the indexing log so the ≥ 95 % NFR-02 threshold is visible
    on every run.
    """
    if not metadatas:
        return 0.0
    full = 0
    for meta in metadatas:
        if all(meta.get(key) not in (None, "", 0) for key in REQUIRED_METADATA_KEYS):
            full += 1
    return full / len(metadatas)


def main() -> int:
    run_id = str(uuid.uuid4())
    logger = setup_logging(run_id)
    logger.info("KB indexing started (run_id=%s)", run_id)

    config = load_config()
    model_name = str(config.get("model_name", "BAAI/bge-m3"))
    persist_dir = str(config.get("vector_store", {}).get("persist_directory", BASE_DIR / "chroma_data"))
    collection_name = str(config.get("vector_store", {}).get("collection_name", "clarify_engine_kb"))
    product_map = load_product_map()

    if not SOURCES_DIR.exists():
        logger.error("Sources directory not found: %s", SOURCES_DIR)
        return 1

    files = sorted(p for p in SOURCES_DIR.glob("*") if p.is_file())
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
        for page_number, page_text in pages:
            if not page_text or not page_text.strip():
                continue
            chunks = build_chunks(page_text)
            if not chunks:
                continue
            for chunk in chunks:
                meta = build_chunk_metadata(
                    source=path.name,
                    chunk_idx=chunk_counter,
                    page_number=page_number,
                    text=chunk,
                    product_map=product_map,
                )
                ids.append(f"{path.stem}__{chunk_counter}")
                docs.append(chunk)
                metadatas.append(meta)
                chunk_counter += 1

        if chunk_counter == 0:
            update_registry(path.name, status="Skipped", sha256=sha256_hash(path))
            continue

        logger.info("→ %d chunks (pages=%d)", chunk_counter, len(pages))
        update_registry(path.name, status="Indexed", sha256=sha256_hash(path))

    if not docs:
        logger.warning("No chunks to index — nothing to persist.")
        return 0

    coverage = _metadata_coverage(metadatas)
    logger.info("Metadata coverage (BL-02, target ≥ 0.95): %.4f", coverage)
    if coverage < 0.95:
        logger.warning(
            "Metadata coverage %.4f is below the NFR-02 / BL-02 target of 0.95.",
            coverage,
        )

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
