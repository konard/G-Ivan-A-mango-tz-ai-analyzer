#!/usr/bin/env python3
"""Offline dependency extraction for KB chunk metadata (BL-14).

The script enriches existing ChromaDB chunks with cross-reference metadata:

* ``related_sections``: ``;``-separated section refs, e.g. ``doc.pdf::7.3.6``
* ``prerequisites``: ``;``-separated prerequisite snippets
* ``see_also``: ``;``-separated explicit "see also" references
* ``dependencies_extracted``: boolean extraction marker

ChromaDB metadata values are scalar, so logical lists are encoded as
semicolon-separated strings. The parser is regex-first and can optionally ask a
local Ollama model to enrich chunks that contain dependency markers.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "embedding_config.yaml"
DEFAULT_PERSIST_DIRECTORY = PROJECT_ROOT / "chroma_data"
DEFAULT_COLLECTION_NAME = "clarify_engine_kb"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct-q4_K_M"

DEPENDENCY_METADATA_DEFAULTS: Dict[str, Any] = {
    "related_sections": "",
    "prerequisites": "",
    "see_also": "",
    "dependencies_extracted": False,
}

DEPENDENCY_MARKER_RE = re.compile(
    r"("
    r"\bсм\.?\b|"
    r"\bсмотрите\b|"
    r"\bсм\.\s*также\b|"
    r"\bпредварительн\w*\b|"
    r"\bтребуется\b|"
    r"\bнеобходимо\b|"
    r"\bнужно\b|"
    r"\bзависит\b|"
    r"\bзависим\w*\b"
    r")",
    re.IGNORECASE | re.UNICODE,
)
SEE_MARKER_RE = re.compile(
    r"\b(?:см\.?|смотрите)\s*(?:также\s*)?"
    r"(?:в\s*)?(?:раздел(?:е)?|пункт(?:е)?|п\.?)?",
    re.IGNORECASE | re.UNICODE,
)
SECTION_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)+\b")
PREREQUISITE_PATTERNS = (
    re.compile(
        r"(?:требуется|необходимо|нужно)\s+"
        r"(?P<value>(?:предварительн\w+\s+)?[^.;\n]{3,160})",
        re.IGNORECASE | re.UNICODE,
    ),
    re.compile(
        r"предварительн\w+\s+"
        r"(?P<value>(?:настройка|подключение|конфигурация)[^.;\n]{3,160})",
        re.IGNORECASE | re.UNICODE,
    ),
    re.compile(
        r"перед\s+[^.;\n]{3,80}\s+(?:требуется|необходимо|нужно)\s+"
        r"(?P<value>[^.;\n]{3,160})",
        re.IGNORECASE | re.UNICODE,
    ),
)


@dataclass
class ExtractionSettings:
    """Runtime settings for one dependency extraction pass."""

    use_ollama: bool = False
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    timeout_seconds: int = 180
    max_text_chars: int = 3500
    fail_on_ollama_error: bool = False


@dataclass
class DependencyExtraction:
    """Structured dependencies extracted from one chunk."""

    related_sections: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)
    method: str = "none"

    @property
    def has_dependency_data(self) -> bool:
        return bool(self.related_sections or self.prerequisites or self.see_also)

    def merge(self, other: "DependencyExtraction") -> "DependencyExtraction":
        return DependencyExtraction(
            related_sections=_unique([*self.related_sections, *other.related_sections]),
            prerequisites=_unique([*self.prerequisites, *other.prerequisites]),
            see_also=_unique([*self.see_also, *other.see_also]),
            method=_merge_method(self.method, other.method),
        )


@dataclass
class ExtractionStats:
    """Summary counters for a ChromaDB enrichment run."""

    total_chunks: int = 0
    processed_chunks: int = 0
    skipped_already_extracted: int = 0
    chunks_with_markers: int = 0
    chunks_with_related_sections: int = 0
    updated_batches: int = 0

    @property
    def related_section_coverage(self) -> float:
        if self.chunks_with_markers == 0:
            return 1.0
        return self.chunks_with_related_sections / self.chunks_with_markers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_chunks": self.total_chunks,
            "processed_chunks": self.processed_chunks,
            "skipped_already_extracted": self.skipped_already_extracted,
            "chunks_with_markers": self.chunks_with_markers,
            "chunks_with_related_sections": self.chunks_with_related_sections,
            "related_section_coverage": round(self.related_section_coverage, 4),
            "updated_batches": self.updated_batches,
        }


def contains_dependency_markers(text: str) -> bool:
    """Return ``True`` when a chunk contains dependency/cross-link markers."""
    return bool(DEPENDENCY_MARKER_RE.search(text or ""))


def extract_dependencies(
    text: str,
    metadata: Optional[Mapping[str, Any]] = None,
    *,
    settings: Optional[ExtractionSettings] = None,
) -> DependencyExtraction:
    """Extract structured dependency metadata from ``text``.

    Regex extraction is deterministic and always runs. When
    ``settings.use_ollama`` is true, a local Ollama pass is attempted only for
    chunks that contain dependency markers; failures fall back to regex unless
    ``fail_on_ollama_error`` is enabled.
    """
    active_settings = settings or ExtractionSettings()
    meta = metadata or {}
    regex_result = _extract_with_regex(text, meta)
    if not active_settings.use_ollama or not contains_dependency_markers(text):
        return regex_result

    try:
        llm_result = _extract_with_ollama(text, meta, active_settings)
    except Exception:
        if active_settings.fail_on_ollama_error:
            raise
        logging.getLogger(__name__).warning(
            "Ollama dependency extraction failed; using regex result",
            exc_info=True,
        )
        return regex_result
    return regex_result.merge(llm_result)


def enrich_metadata(
    metadata: Mapping[str, Any],
    text: str,
    *,
    settings: Optional[ExtractionSettings] = None,
) -> Dict[str, Any]:
    """Return a Chroma-safe metadata copy enriched with dependency fields."""
    enriched = dict(metadata or {})
    extraction = extract_dependencies(text, enriched, settings=settings)
    related = _encode_list(extraction.related_sections)
    prerequisites = _encode_list(extraction.prerequisites)
    see_also = _encode_list(extraction.see_also)
    enriched.update(
        {
            "related_sections": related,
            "prerequisites": prerequisites,
            "see_also": see_also,
            "dependencies_extracted": True,
            "has_dependencies": bool(related or see_also),
            "has_prerequisites": bool(prerequisites),
            "dependency_extraction_method": extraction.method,
        }
    )
    return enriched


def update_collection_dependencies(
    collection: Any,
    *,
    settings: Optional[ExtractionSettings] = None,
    force: bool = False,
    batch_size: int = 100,
    logger: Optional[logging.Logger] = None,
) -> ExtractionStats:
    """Read ChromaDB chunks, enrich metadata, and update the collection.

    The operation is idempotent by default: chunks with
    ``dependencies_extracted=true`` are skipped unless ``force`` is set.
    """
    active_settings = settings or ExtractionSettings()
    log = logger or logging.getLogger(__name__)
    raw = collection.get(include=["documents", "metadatas"])
    ids = list(raw.get("ids") or [])
    documents = list(raw.get("documents") or [])
    metadatas = list(raw.get("metadatas") or [])
    stats = ExtractionStats(total_chunks=len(ids))

    pending_ids: List[str] = []
    pending_metadatas: List[Dict[str, Any]] = []

    for chunk_id, document, metadata in zip(ids, documents, metadatas):
        meta = dict(metadata or {})
        if meta.get("dependencies_extracted") is True and not force:
            stats.skipped_already_extracted += 1
            continue

        text = str(document or "")
        stats.processed_chunks += 1
        has_markers = contains_dependency_markers(text)
        if has_markers:
            stats.chunks_with_markers += 1

        enriched = enrich_metadata(meta, text, settings=active_settings)
        if has_markers and _decode_list(enriched.get("related_sections")):
            stats.chunks_with_related_sections += 1

        pending_ids.append(str(chunk_id))
        pending_metadatas.append(enriched)
        if len(pending_ids) >= max(1, int(batch_size)):
            _flush_updates(collection, pending_ids, pending_metadatas)
            stats.updated_batches += 1
            pending_ids = []
            pending_metadatas = []

    if pending_ids:
        _flush_updates(collection, pending_ids, pending_metadatas)
        stats.updated_batches += 1

    log.info("Dependency extraction stats: %s", stats.to_dict())
    return stats


def _extract_with_regex(text: str, metadata: Mapping[str, Any]) -> DependencyExtraction:
    source = _metadata_source(metadata)
    related = [_qualify_section(match, source) for match in _reference_numbers(text)]
    prerequisites = _extract_prerequisites(text)
    method = "regex" if contains_dependency_markers(text) else "none"
    return DependencyExtraction(
        related_sections=_unique(related),
        prerequisites=_unique(prerequisites),
        see_also=_unique(related),
        method=method,
    )


def _reference_numbers(text: str) -> List[str]:
    refs: List[str] = []
    for marker in SEE_MARKER_RE.finditer(text or ""):
        window = (text or "")[marker.end() : marker.end() + 220]
        refs.extend(match.group(0) for match in SECTION_NUMBER_RE.finditer(window))
    return _unique(refs)


def _extract_prerequisites(text: str) -> List[str]:
    values: List[str] = []
    for pattern in PREREQUISITE_PATTERNS:
        for match in pattern.finditer(text or ""):
            values.append(_clean_item(match.group("value")))
    return _unique(values)


def _extract_with_ollama(
    text: str,
    metadata: Mapping[str, Any],
    settings: ExtractionSettings,
) -> DependencyExtraction:
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover - requirements include requests
        raise RuntimeError("`requests` is required for Ollama extraction") from exc

    source = _metadata_source(metadata)
    payload = {
        "model": settings.ollama_model,
        "temperature": 0.0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract documentation dependencies from the user chunk. "
                    "Return strict JSON with keys related_sections, prerequisites, "
                    "see_also. Use arrays of short strings. Do not invent links."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source": source,
                        "section_number": metadata.get("section_number"),
                        "text": (text or "")[: settings.max_text_chars],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    response = requests.post(
        f"{settings.ollama_base_url.rstrip('/')}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=settings.timeout_seconds,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {response.text[:300]}")
    content = response.json()["choices"][0]["message"]["content"]
    data = _extract_json_object(str(content))
    return DependencyExtraction(
        related_sections=[
            _qualify_section(item, source)
            for item in _coerce_list(data.get("related_sections"))
        ],
        prerequisites=_coerce_list(data.get("prerequisites")),
        see_also=[
            _qualify_section(item, source)
            for item in _coerce_list(data.get("see_also"))
        ],
        method="ollama",
    )


def _extract_json_object(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        raise ValueError("Ollama response did not contain a JSON object")
    return json.loads(match.group(0))


def _flush_updates(
    collection: Any,
    ids: Sequence[str],
    metadatas: Sequence[Mapping[str, Any]],
) -> None:
    collection.update(ids=list(ids), metadatas=[dict(meta) for meta in metadatas])


def _metadata_source(metadata: Mapping[str, Any]) -> str:
    for key in ("source", "source_file", "filename"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def _qualify_section(section: Any, source: str) -> str:
    value = _clean_item(str(section or ""))
    if not value:
        return ""
    if "::" in value:
        return value
    match = SECTION_NUMBER_RE.search(value)
    number = match.group(0) if match else value
    return f"{source}::{number}" if source else number


def _encode_list(values: Iterable[Any]) -> str:
    return ";".join(_unique(str(value) for value in values))


def _decode_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return _unique(str(item) for item in value)
    return _unique(part for part in str(value).split(";"))


def _coerce_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return _unique(str(item) for item in value)
    if isinstance(value, str):
        return _decode_list(value)
    return []


def _unique(values: Iterable[Any]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        item = _clean_item(str(value))
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _clean_item(value: str) -> str:
    item = re.sub(r"\s+", " ", value or "").strip()
    item = item.strip(" \t\r\n,;:()[]{}")
    return item.replace(";", ",")


def _merge_method(left: str, right: str) -> str:
    methods = [m for m in (left, right) if m and m != "none"]
    if not methods:
        return "none"
    return "+".join(_unique(methods))


def _load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_vector_store(config: Mapping[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    vector_store = config.get("vector_store") if isinstance(config, Mapping) else None
    if not isinstance(vector_store, Mapping):
        vector_store = {}
    persist = args.persist_directory or vector_store.get("persist_directory")
    collection = args.collection_name or vector_store.get("collection_name")
    persist_path = Path(str(persist or DEFAULT_PERSIST_DIRECTORY))
    if not persist_path.is_absolute():
        persist_path = PROJECT_ROOT / persist_path
    return str(persist_path), str(collection or DEFAULT_COLLECTION_NAME)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--persist-directory")
    parser.add_argument("--collection-name")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--use-ollama", action="store_true")
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--min-related-coverage", type=float, default=0.0)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    config = _load_config(Path(args.config))
    persist_directory, collection_name = _resolve_vector_store(config, args)
    try:
        import chromadb  # type: ignore
    except ImportError as exc:
        logging.error("chromadb is not installed: %s", exc)
        return 2

    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_or_create_collection(name=collection_name)
    stats = update_collection_dependencies(
        collection,
        settings=ExtractionSettings(
            use_ollama=args.use_ollama,
            ollama_base_url=args.ollama_base_url,
            ollama_model=args.ollama_model,
            timeout_seconds=args.timeout_seconds,
        ),
        force=args.force,
        batch_size=args.batch_size,
        logger=logging.getLogger(__name__),
    )
    print(json.dumps(stats.to_dict(), ensure_ascii=False, indent=2))
    if (
        stats.chunks_with_markers > 0
        and stats.related_section_coverage < float(args.min_related_coverage)
    ):
        logging.error(
            "related_sections coverage %.4f is below threshold %.4f",
            stats.related_section_coverage,
            float(args.min_related_coverage),
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
