"""Offline DOCX structure enrichment for parser-produced raw blocks.

The enricher is intentionally isolated from the runtime RAG pipeline. It takes
``DocxParser``-style dictionaries, asks an optional local LLM for atom spans and
metadata, then slices ``exact_text`` from the original parser text in Python.
This keeps the source text byte-for-byte unchanged even when the LLM proposes
bad or reformulated content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import yaml

from src.llm.prompt_loader import PromptNotFoundError, load_prompt_from_path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "docx_structure_enrichment_v1"
DEFAULT_PROMPT_PATH = "prompts/docx_structure_enricher_v1.0.md"
DEFAULT_LLM_CONFIG_PATH = "configs/llm_config.yaml"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct-q4_K_M"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 180
DEFAULT_CONFIDENCE_THRESHOLD = 0.85
VALID_REQUIREMENT_TYPES = {
    "functional",
    "non-functional",
    "integration",
    "security",
}

LlmCall = Callable[[str, str, Dict[str, Any]], str]

_MARKER_RE = re.compile(
    r"(?m)^(?P<indent>\s*)"
    r"(?P<marker>"
    r"\d+(?:\.[A-Za-zА-Яа-я0-9]+)+\.?|"
    r"\d+[\.)]|"
    r"[A-Za-zА-Яа-я][\.)]|"
    r"[ivxlcdm]+[\.)]|"
    r"[-–—•]"
    r")\s+",
    re.IGNORECASE | re.UNICODE,
)

_ENV_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Z0-9_]+):(.+)\}$")


@dataclass(frozen=True)
class EnrichmentSettings:
    """Runtime settings for one DOCX structure enrichment pass."""

    use_llm: bool = True
    llm_config_path: str = DEFAULT_LLM_CONFIG_PATH
    prompt_path: str = DEFAULT_PROMPT_PATH
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_block_chars: int = 6000


@dataclass(frozen=True)
class RawBlock:
    """Normalized parser block used internally by the enricher."""

    source_id: str
    exact_text: str
    locator: Dict[str, Any]
    source_hash: str


@dataclass(frozen=True)
class AtomSpan:
    """One atom proposal represented only by source offsets and metadata."""

    start: int
    end: int
    marker: str = ""
    parent_marker: str = ""
    requirement_type: str = "functional"
    confidence: float = 0.0


class DocxStructureEnricher:
    """Enrich raw DOCX parser blocks into atomic requirement records."""

    def __init__(
        self,
        *,
        settings: Optional[EnrichmentSettings] = None,
        llm_call: Optional[LlmCall] = None,
    ) -> None:
        self.settings = settings or EnrichmentSettings()
        self.llm_call = llm_call or self._call_ollama
        self.system_prompt = self._load_prompt(self.settings.prompt_path)
        self.llm_config = _load_ollama_config(self.settings)

    def enrich_blocks(
        self,
        blocks: Iterable[Mapping[str, Any]],
        *,
        source_file: str,
    ) -> List[Dict[str, Any]]:
        """Return enriched requirement dictionaries for parser ``blocks``."""

        normalized_blocks = [normalize_raw_block(block) for block in blocks]
        rows: List[Dict[str, Any]] = []
        for block in normalized_blocks:
            spans: List[AtomSpan]
            enrichment_source = "heuristic"
            warnings: List[str] = []
            if self.settings.use_llm:
                try:
                    spans = self._llm_spans(block)
                    enrichment_source = "llm"
                except Exception as exc:  # noqa: BLE001 - offline fallback is required
                    warnings = [f"LLM enrichment failed: {exc}"]
                    logger.warning("%s", warnings[0])
                    spans = heuristic_spans(block.exact_text)
                    enrichment_source = "heuristic_fallback"
            else:
                spans = heuristic_spans(block.exact_text)

            rows.extend(
                self._rows_from_spans(
                    block,
                    spans,
                    source_file=source_file,
                    enrichment_source=enrichment_source,
                    warnings=warnings,
                )
            )

        _resolve_parent_ids(rows)
        return rows

    def _load_prompt(self, prompt_path: str) -> str:
        try:
            return load_prompt_from_path(prompt_path).content
        except PromptNotFoundError:
            logger.warning(
                "Prompt %s not found; using built-in DOCX enrichment fallback.",
                prompt_path,
            )
            return (
                "Split DOCX raw blocks into atomic requirement spans. "
                "Return strict JSON with an atoms array. "
                "Do not return exact_text."
            )

    def _llm_spans(self, block: RawBlock) -> List[AtomSpan]:
        text = block.exact_text
        if len(text) > self.settings.max_block_chars:
            raise ValueError(
                f"block {block.source_id} exceeds max_block_chars="
                f"{self.settings.max_block_chars}"
            )
        payload = json.dumps(
            {
                "schema_version": "docx_structure_enrichment_request_v1",
                "blocks": [
                    {
                        "source_id": block.source_id,
                        "locator": block.locator,
                        "exact_text_hash": block.source_hash,
                        "text": text,
                    }
                ],
            },
            ensure_ascii=False,
        )
        response = self.llm_call(self.system_prompt, payload, dict(self.llm_config))
        parsed = _extract_json(response)
        raw_atoms: Any
        if isinstance(parsed, dict):
            raw_atoms = parsed.get("atoms")
        else:
            raw_atoms = parsed
        if not isinstance(raw_atoms, list):
            raise ValueError("LLM response must contain an atoms array")
        return _validate_llm_atoms(raw_atoms, block)

    def _rows_from_spans(
        self,
        block: RawBlock,
        spans: Sequence[AtomSpan],
        *,
        source_file: str,
        enrichment_source: str,
        warnings: Sequence[str],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for span in spans:
            exact_text = block.exact_text[span.start : span.end]
            confidence = _clamp_confidence(span.confidence)
            force_review = enrichment_source == "heuristic_fallback"
            requires_review = (
                confidence < float(self.settings.confidence_threshold) or force_review
            )
            row_id = _stable_requirement_id(
                source_file=source_file,
                block=block,
                span=span,
            )
            rows.append(
                {
                    "id": row_id,
                    "requirement_id": row_id,
                    "parent_id": None,
                    "source_block_id": block.source_id,
                    "type": normalize_requirement_type(span.requirement_type),
                    "confidence": confidence,
                    "requires_manual_review": requires_review,
                    "needs_review": requires_review,
                    "exact_text": exact_text,
                    "requirement_text": exact_text,
                    "exact_text_hash": sha256_text(exact_text),
                    "source_hash": block.source_hash,
                    "text_span": {"start": span.start, "end": span.end},
                    "locator": dict(block.locator),
                    "Ref": canonical_ref_from_locator(block.locator, source_file),
                    "marker": span.marker,
                    "enrichment_source": enrichment_source,
                    "warnings": list(warnings),
                    "_parent_marker": span.parent_marker,
                }
            )
        return rows

    def _call_ollama(
        self,
        system_prompt: str,
        user_payload: str,
        config: Dict[str, Any],
    ) -> str:
        try:
            import requests  # type: ignore
        except ImportError as exc:  # pragma: no cover - requirements include requests
            raise RuntimeError("`requests` is required for Ollama enrichment") from exc

        base_url = str(config.get("base_url") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        model = str(config.get("model") or DEFAULT_OLLAMA_MODEL)
        timeout_seconds = max(int(config.get("timeout_seconds") or 1), 1)
        options = dict(config.get("options") or {})
        options["temperature"] = 0.0
        body: Dict[str, Any] = {
            "model": model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            "response_format": {"type": "json_object"},
        }
        if options:
            body["options"] = options

        response = requests.post(
            f"{base_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            return str(response.json()["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Ollama response shape: {exc}") from exc


def build_enrichment_document(
    requirements: Sequence[Mapping[str, Any]],
    *,
    source_file: str,
    raw_block_count: int,
    settings: EnrichmentSettings,
) -> Dict[str, Any]:
    """Build the top-level JSON document emitted by the CLI."""

    return {
        "schema_version": SCHEMA_VERSION,
        "source_file": source_file,
        "raw_block_count": raw_block_count,
        "requirement_count": len(requirements),
        "confidence_threshold": settings.confidence_threshold,
        "llm_enabled": settings.use_llm,
        "requirements": [dict(item) for item in requirements],
    }


def normalize_raw_block(block: Mapping[str, Any]) -> RawBlock:
    """Normalize parser output into an immutable raw block."""

    source_id = str(block.get("id") or block.get("source_id") or "")
    if not source_id:
        source_id = uuid.uuid4().hex
    exact_text = str(block.get("exact_text", block.get("text", "")) or "")
    if not exact_text.strip():
        raise ValueError(f"Raw block {source_id} has empty exact_text")
    locator = dict(block.get("locator") or {})
    return RawBlock(
        source_id=source_id,
        exact_text=exact_text,
        locator=locator,
        source_hash=sha256_text(exact_text),
    )


def heuristic_spans(text: str) -> List[AtomSpan]:
    """Deterministically split text on line-level list/outline markers."""

    matches = list(_MARKER_RE.finditer(text or ""))
    spans: List[AtomSpan] = []

    if not matches:
        start = _trim_span_start(text, 0)
        end = _trim_span_end(text, len(text))
        if start < end:
            exact = text[start:end]
            spans.append(
                AtomSpan(
                    start=start,
                    end=end,
                    requirement_type=classify_requirement_type(exact),
                    confidence=0.9,
                )
            )
        return spans

    first_marker_start = matches[0].start("marker")
    prefix_start = _trim_span_start(text, 0)
    prefix_end = _trim_span_end(text, first_marker_start)
    if prefix_start < prefix_end:
        exact = text[prefix_start:prefix_end]
        spans.append(
            AtomSpan(
                start=prefix_start,
                end=prefix_end,
                requirement_type=classify_requirement_type(exact),
                confidence=0.78,
            )
        )

    for index, match in enumerate(matches):
        start = match.start("marker")
        next_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        )
        end = _trim_span_end(text, next_start)
        if start >= end:
            continue
        exact = text[start:end]
        marker = normalize_marker(match.group("marker"))
        spans.append(
            AtomSpan(
                start=start,
                end=end,
                marker=marker,
                requirement_type=classify_requirement_type(exact),
                confidence=0.78,
            )
        )

    if not spans:
        raise ValueError("Heuristic enrichment produced no spans")
    return spans


def canonical_ref_from_locator(
    locator: Mapping[str, Any],
    source_file: str,
) -> Dict[str, Any]:
    """Map parser locator metadata to the export ``Ref`` contract."""

    source = str(source_file or "unknown")
    locator_type = str(locator.get("type") or "").lower()
    if locator_type == "paragraph":
        para_index = locator.get("para_index", locator.get("index"))
        ref: Dict[str, Any] = {
            "type": "list_item" if locator.get("list_path") else "paragraph",
            "source_file": source,
            "para_index": _optional_int(para_index),
        }
        if locator.get("list_path"):
            ref["list_path"] = list(locator["list_path"])
        return {key: value for key, value in ref.items() if value is not None}

    if locator_type in {"table", "table_cell_list", "cell"}:
        ref = {
            "type": "table_cell_list",
            "source_file": source,
            "table_index": _optional_int(
                locator.get("table_index", locator.get("table"))
            ),
            "row": _optional_int(locator.get("row")),
            "col": _optional_int(locator.get("col", locator.get("column"))),
        }
        if locator.get("list_path"):
            ref["list_path"] = list(locator["list_path"])
        return {key: value for key, value in ref.items() if value is not None}

    if locator.get("list_path"):
        return {
            "type": "list_item",
            "source_file": source,
            "list_path": list(locator["list_path"]),
        }

    return {
        "type": "paragraph",
        "source_file": source,
        "para_index": _optional_int(locator.get("index", 0)) or 0,
        "derived": True,
    }


def classify_requirement_type(text: str) -> str:
    """Small deterministic classifier used by the heuristic fallback."""

    lowered = (text or "").lower()
    if re.search(r"персональн|152-фз|фз\s*№?\s*152|шифр|безопас|защит", lowered):
        return "security"
    if re.search(
        r"интеграц|api|вебсервис|web[- ]?service|sip|h\.323|crm|мис",
        lowered,
    ):
        return "integration"
    if re.search(
        r"отказоустойчив|доступност|производительн|sla|круглосуточ|n\+1|уровн[ья] защищенности",
        lowered,
    ):
        return "non-functional"
    return "functional"


def normalize_requirement_type(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "nonfunctional": "non-functional",
        "non functional": "non-functional",
        "integration-requirement": "integration",
        "security-requirement": "security",
        "functional-requirement": "functional",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in VALID_REQUIREMENT_TYPES:
        return "functional"
    return normalized


def normalize_marker(marker: Any) -> str:
    value = str(marker or "").strip()
    if value in {"-", "–", "—", "•"}:
        return value
    return value.rstrip(".)")


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _validate_llm_atoms(raw_atoms: Sequence[Any], block: RawBlock) -> List[AtomSpan]:
    spans: List[AtomSpan] = []
    previous_end = -1
    text_length = len(block.exact_text)
    for raw in sorted(raw_atoms, key=lambda item: int((item or {}).get("start", 0))):
        if not isinstance(raw, Mapping):
            raise ValueError("Each atom must be an object")
        source_id = raw.get("source_id")
        if source_id is not None and str(source_id) != block.source_id:
            raise ValueError(
                f"Atom source_id={source_id!r} does not match block {block.source_id!r}"
            )
        start = int(raw.get("start"))
        end = int(raw.get("end"))
        if start < 0 or end > text_length or start >= end:
            raise ValueError(
                f"Invalid atom span [{start}, {end}) for block {block.source_id}"
            )
        if start < previous_end:
            raise ValueError("LLM atom spans must not overlap")
        exact = block.exact_text[start:end]
        if not exact.strip():
            raise ValueError("LLM atom span resolves to blank text")
        previous_end = end
        spans.append(
            AtomSpan(
                start=start,
                end=end,
                marker=normalize_marker(raw.get("marker")),
                parent_marker=normalize_marker(raw.get("parent_marker")),
                requirement_type=normalize_requirement_type(raw.get("type")),
                confidence=_clamp_confidence(raw.get("confidence", 0.0)),
            )
        )
    if not spans:
        raise ValueError("LLM response did not contain any valid atoms")
    return spans


def _resolve_parent_ids(rows: List[Dict[str, Any]]) -> None:
    marker_to_id: Dict[tuple[str, str], str] = {}
    global_marker_to_id: Dict[str, str] = {}
    previous_by_block: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        marker = str(row.get("marker") or "")
        source_block_id = str(row.get("source_block_id") or "")
        if marker:
            marker_to_id[(source_block_id, marker)] = str(row["id"])
            global_marker_to_id[marker] = str(row["id"])

    for row in rows:
        source_block_id = str(row.get("source_block_id") or "")
        marker = str(row.get("marker") or "")
        parent_marker = str(row.pop("_parent_marker", "") or "")
        parent_id = None
        if parent_marker:
            parent_id = marker_to_id.get((source_block_id, parent_marker))
            parent_id = parent_id or global_marker_to_id.get(parent_marker)
        if parent_id is None and marker:
            derived_marker = _derive_parent_marker(marker)
            if derived_marker:
                parent_id = marker_to_id.get((source_block_id, derived_marker))
                parent_id = parent_id or global_marker_to_id.get(derived_marker)
        if parent_id is None and marker:
            previous = previous_by_block.get(source_block_id)
            if previous and previous.get("marker"):
                parent_id = str(previous["id"])
        row["parent_id"] = parent_id
        previous_by_block[source_block_id] = row


def _derive_parent_marker(marker: str) -> str:
    parts = [part for part in marker.split(".") if part]
    if len(parts) <= 1:
        return ""
    return ".".join(parts[:-1])


def _stable_requirement_id(
    *,
    source_file: str,
    block: RawBlock,
    span: AtomSpan,
) -> str:
    key = "|".join(
        [
            "clarify-engine-ai",
            SCHEMA_VERSION,
            str(source_file or ""),
            block.source_id,
            block.source_hash,
            str(span.start),
            str(span.end),
            span.marker,
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _extract_json(text: str) -> Any:
    stripped = str(text or "").strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    match = re.search(r"(\{.*\}|\[.*\])", stripped, flags=re.DOTALL)
    if not match:
        raise ValueError("LLM response did not contain JSON")
    return json.loads(match.group(1))


def _trim_span_start(text: str, start: int) -> int:
    while start < len(text) and text[start].isspace():
        start += 1
    return start


def _trim_span_end(text: str, end: int) -> int:
    while end > 0 and text[end - 1].isspace():
        end -= 1
    return end


def _clamp_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = 0.0
    return round(min(max(parsed, 0.0), 1.0), 4)


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_ollama_config(settings: EnrichmentSettings) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "base_url": DEFAULT_OLLAMA_BASE_URL,
        "model": DEFAULT_OLLAMA_MODEL,
        "timeout_seconds": DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        "options": {},
    }
    path = Path(settings.llm_config_path)
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            providers = raw.get("providers") or {}
            ollama = dict(providers.get("ollama") or {})
            if ollama:
                config.update(
                    {
                        "base_url": _resolve_config_value(
                            ollama.get("base_url"), DEFAULT_OLLAMA_BASE_URL
                        ),
                        "model": _resolve_config_value(
                            ollama.get("model"), DEFAULT_OLLAMA_MODEL
                        ),
                        "timeout_seconds": _resolve_int_config_value(
                            ollama.get("timeout_seconds"),
                            DEFAULT_OLLAMA_TIMEOUT_SECONDS,
                        ),
                        "options": dict(ollama.get("options") or {}),
                    }
                )
        except Exception as exc:  # noqa: BLE001 - fall back to defaults
            logger.warning("Failed to load %s: %s", settings.llm_config_path, exc)
    config["base_url"] = settings.ollama_base_url or config["base_url"]
    config["model"] = settings.ollama_model or config["model"]
    config["timeout_seconds"] = max(
        int(settings.timeout_seconds or config["timeout_seconds"]), 1
    )
    return config


def _resolve_config_value(value: Any, default: Any) -> Any:
    if not isinstance(value, str):
        return default if value is None else value
    match = _ENV_PLACEHOLDER_RE.fullmatch(value)
    if match is None:
        return value
    env_name, fallback = match.groups()
    return os.environ.get(env_name, fallback)


def _resolve_int_config_value(value: Any, default: int) -> int:
    resolved = _resolve_config_value(value, default)
    try:
        return int(resolved)
    except (TypeError, ValueError):
        return int(default)
