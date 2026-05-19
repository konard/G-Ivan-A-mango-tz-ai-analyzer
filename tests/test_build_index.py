"""Tests for ``knowledge_base/indexing/build_index.py`` registry & hashing.

Locks in the contract introduced by issues #45/#48:

* Hashing is SHA-256 (not MD5).
* ``source_registry.csv`` uses the schema
  ``filename, version, sha256_hash, indexed_date, status, coverage``.
* Chunk parameters and the model name are read from
  ``configs/embedding_config.yaml``.
* Pre-existing ``version`` / ``coverage`` values survive re-indexing.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "knowledge_base" / "indexing" / "build_index.py"


@pytest.fixture
def build_index_module(tmp_path: Path) -> Iterator[object]:
    """Import build_index.py with a tmp-scoped registry & sources tree."""
    spec = importlib.util.spec_from_file_location("build_index_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    metadata_dir = tmp_path / "metadata"
    sources_dir = tmp_path / "sources"
    metadata_dir.mkdir()
    sources_dir.mkdir()
    module.METADATA_DIR = metadata_dir
    module.REGISTRY_FILE = metadata_dir / "source_registry.csv"
    module.SOURCES_DIR = sources_dir

    try:
        yield module
    finally:
        sys.modules.pop(spec.name, None)


def test_sha256_hash_returns_sha256_hex(build_index_module, tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    payload = b"clarify-engine-ai/issue-48"
    sample.write_bytes(payload)

    digest = build_index_module.sha256_hash(sample)
    assert digest == hashlib.sha256(payload).hexdigest()
    # SHA-256 hex digest length is 64.
    assert len(digest) == 64


def test_update_registry_writes_required_schema(build_index_module) -> None:
    build_index_module.update_registry(
        "doc.md",
        sha256="a" * 64,
        status="Indexed",
        version="1.2",
        coverage="High",
    )

    with build_index_module.REGISTRY_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "filename",
            "version",
            "sha256_hash",
            "indexed_date",
            "status",
            "coverage",
        ]
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["filename"] == "doc.md"
    assert row["version"] == "1.2"
    assert row["sha256_hash"] == "a" * 64
    assert row["status"] == "Indexed"
    assert row["coverage"] == "High"
    assert row["indexed_date"], "indexed_date must be populated"
    # No legacy fields leak into the registry.
    assert "hash" not in row
    assert "run_id" not in row


def test_update_registry_preserves_existing_version_and_coverage(build_index_module) -> None:
    build_index_module.update_registry(
        "doc.md", sha256="b" * 64, status="Indexed", version="2.0", coverage="High"
    )
    # Re-index without supplying version/coverage; existing values must be preserved.
    build_index_module.update_registry("doc.md", sha256="c" * 64, status="Indexed")

    with build_index_module.REGISTRY_FILE.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["version"] == "2.0"
    assert rows[0]["coverage"] == "High"
    assert rows[0]["sha256_hash"] == "c" * 64


def test_load_config_returns_embedding_config_keys() -> None:
    spec = importlib.util.spec_from_file_location("build_index_cfg", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    try:
        config = module.load_config()
        # Must read the actual embedding_config.yaml keys (not legacy aliases).
        assert "model_name" in config
        assert "chunk_size" in config
        assert "chunk_overlap" in config
    finally:
        sys.modules.pop(spec.name, None)


def test_build_chunk_metadata_adds_parent_fields(build_index_module) -> None:
    meta = build_index_module.build_chunk_metadata(
        source="doc.md",
        chunk_idx=0,
        page_number=1,
        text="1.2 Интеграции\nREST API",
    )
    assert meta["parent_id"] == "doc.md::1.2::Интеграции"
    assert meta["section_id"] == meta["parent_id"]
    assert "parent_text" in meta


def test_run_id_json_formatter_uses_timezone_aware_utc(build_index_module, monkeypatch) -> None:
    class NoUtcNowDatetime:
        @staticmethod
        def now(tz=None):
            assert tz is timezone.utc
            return datetime(2026, 5, 20, 12, 34, 56, tzinfo=tz)

    monkeypatch.setattr(build_index_module, "datetime", NoUtcNowDatetime)
    formatter = build_index_module._RunIdJsonFormatter("run-1")
    record = logging.LogRecord(
        name="kb_indexer",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="indexed",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["time"] == "2026-05-20T12:34:56Z"
    parsed = datetime.fromisoformat(payload["time"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
