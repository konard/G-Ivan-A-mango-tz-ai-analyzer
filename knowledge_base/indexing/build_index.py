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
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "embedding_config.yaml"
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


def main() -> int:
    run_id = str(uuid.uuid4())
    logger = setup_logging(run_id)
    logger.info("KB indexing started (run_id=%s)", run_id)

    config = load_config()
    model_name = str(config.get("model_name", "BAAI/bge-m3"))
    persist_dir = str(config.get("vector_store", {}).get("persist_directory", BASE_DIR / "chroma_data"))
    collection_name = str(config.get("vector_store", {}).get("collection_name", "mango_kb"))

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
        text = load_text(path, logger)
        if not text or not text.strip():
            update_registry(
                path.name,
                status="Skipped",
                sha256=sha256_hash(path),
            )
            continue

        chunks = build_chunks(text)
        if not chunks:
            update_registry(path.name, status="Skipped", sha256=sha256_hash(path))
            continue

        logger.info("→ %d chunks", len(chunks))
        for idx, chunk in enumerate(chunks):
            ids.append(f"{path.stem}__{idx}")
            docs.append(chunk)
            metadatas.append({"source": path.name, "chunk_idx": idx})

        update_registry(path.name, status="Indexed", sha256=sha256_hash(path))

    if not docs:
        logger.warning("No chunks to index — nothing to persist.")
        return 0

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
