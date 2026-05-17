"""End-to-end RAG pipeline orchestrator.

Steps:
    1. Generate a unique ``run_id`` (UUID4) and configure JSON logging.
    2. Load requirements from an Excel/DOCX file (preserving all source columns).
    3. Load (or build) the knowledge-base index.
    4. For each requirement: hybrid search → mask → LLM classify.
    5. Append classification columns to the original DataFrame.
    6. Export to Excel with the source structure intact plus the four MVP
       columns ``[Статус]``, ``[Комментарий]``, ``[Confidence]``, ``[RunID]``
       (FR-06, issue #45).

Run as a CLI::

    python -m src.pipeline --input test_data/sample_tz.xlsx \\
        --output output/result_$(uuidgen).xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.exporters.excel_exporter import save_results
from src.llm.client import LLMClient, LLMError
from src.llm.masking import sanitize_log_record
from src.parsers.excel_parser import load_requirements
from src.rag.retriever import HybridRetriever, build_retriever

logger = logging.getLogger(__name__)

_RESERVED_LOG_RECORD_ATTRS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter that includes ``run_id`` and ``requirement_id``.

    BL-23 (issue #87): every record is passed through
    :func:`sanitize_log_record` before serialisation, so regex patterns from
    ``configs/masking_rules.yaml`` are applied to free-text fields and any
    secret-shaped env vars in ``extra`` are redacted.
    """

    def __init__(self, masking_config_path: str = "configs/masking_rules.yaml") -> None:
        super().__init__()
        self._masking_config_path = masking_config_path

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        run_id = getattr(record, "run_id", None)
        if run_id:
            entry["run_id"] = run_id
        requirement_id = getattr(record, "requirement_id", None)
        if requirement_id is not None:
            entry["requirement_id"] = requirement_id
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key in entry:
                continue
            entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        sanitized = sanitize_log_record(entry, config_path=self._masking_config_path)
        return json.dumps(sanitized, ensure_ascii=False)


class _RunIdFilter(logging.Filter):
    """Inject ``run_id`` onto records that don't already carry one.

    A Filter is used instead of ``setLogRecordFactory`` so that call sites
    which pass ``extra={"run_id": ...}`` explicitly (e.g. excel_parser) do
    not collide with the framework's "cannot overwrite" guard.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "run_id", None):
            record.run_id = self._run_id
        return True


class _SanitizingFilter(logging.Filter):
    """BL-23 filter that masks ``record.msg`` in-place before formatting.

    The :class:`_JsonFormatter` already sanitises the assembled JSON entry,
    but a filter is also installed so that downstream handlers (e.g. a
    ``StreamHandler`` writing to stderr in plain text) cannot leak raw PII
    even when the JSON formatter is bypassed.
    """

    def __init__(self, masking_config_path: str = "configs/masking_rules.yaml") -> None:
        super().__init__()
        self._masking_config_path = masking_config_path

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:  # noqa: BLE001 - never break logging on format errors
            return True
        sanitized = sanitize_log_record(
            {"message": rendered}, config_path=self._masking_config_path
        )["message"]
        if sanitized != rendered:
            record.msg = sanitized
            record.args = ()
        return True


def configure_json_logging(
    run_id: str,
    level: int = logging.INFO,
    masking_config_path: str = "configs/masking_rules.yaml",
) -> None:
    """Install a JSON formatter on the root logger that carries the run_id.

    BL-23: a :class:`_SanitizingFilter` is attached to the root logger so
    every record reaches the formatter already sanitised. The formatter
    itself runs :func:`sanitize_log_record` over the JSON entry as a
    belt-and-braces defence (multiple handlers, ``extra=`` fields, etc.).
    """
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.filters.clear()
    root.addFilter(_SanitizingFilter(masking_config_path=masking_config_path))
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter(masking_config_path=masking_config_path))
    handler.addFilter(_RunIdFilter(run_id))
    root.addHandler(handler)


@dataclass
class PipelineStats:
    run_id: str = ""
    total: int = 0
    success: int = 0
    errors: int = 0
    nd: int = 0
    by_provider: Dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total": self.total,
            "success": self.success,
            "errors": self.errors,
            "nd": self.nd,
            "by_provider": dict(self.by_provider),
        }


def _read_knowledge_base(kb_dir: Path) -> List[Dict[str, Any]]:
    """Load documents from ``knowledge_base/sources`` + metadata registry."""
    documents: List[Dict[str, Any]] = []
    sources_dir = kb_dir / "sources"
    metadata_csv = kb_dir / "metadata" / "source_registry.csv"

    metadata_lookup: Dict[str, Dict[str, str]] = {}
    if metadata_csv.exists() and metadata_csv.stat().st_size > 0:
        try:
            with metadata_csv.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    name = row.get("file") or row.get("filename") or row.get("source")
                    if name:
                        metadata_lookup[name] = row
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read source registry %s: %s", metadata_csv, exc)

    if not sources_dir.exists():
        logger.warning("Knowledge base sources directory not found: %s", sources_dir)
        return documents

    for path in sorted(sources_dir.glob("**/*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                text = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping %s: %s", path, exc)
            continue
        if not text.strip():
            continue
        documents.append(
            {
                "text": text,
                "source": path.name,
                "metadata": metadata_lookup.get(path.name, {"path": str(path)}),
            }
        )
    return documents


def run_analysis(
    input_file: str,
    output_file: str,
    *,
    kb_dir: str = "knowledge_base",
    embedding_config: str = "configs/embedding_config.yaml",
    llm_config: str = "configs/llm_config.yaml",
    masking_config: str = "configs/masking_rules.yaml",
    prompt_path: str = "prompts/system_classifier_v1.0.md",
    top_k: Optional[int] = None,
    retriever: Optional[HybridRetriever] = None,
    llm_client: Optional[LLMClient] = None,
    documents: Optional[Iterable[Dict[str, Any]]] = None,
    run_id: Optional[str] = None,
) -> PipelineStats:
    """Run the full analysis pipeline on a single ТЗ file."""
    run_id = run_id or uuid.uuid4().hex
    configure_json_logging(run_id=run_id)
    logger.info("Pipeline started: input=%s output=%s", input_file, output_file)

    requirements = load_requirements(input_file, run_id=run_id)

    if retriever is None:
        kb_docs = list(documents) if documents is not None else _read_knowledge_base(Path(kb_dir))
        if not kb_docs:
            logger.warning(
                "Knowledge base is empty. The retriever will return no context — "
                "all requirements will likely be classified as 'НД'."
            )
        retriever = build_retriever(documents=kb_docs, config_path=embedding_config)

    if llm_client is None:
        llm_client = LLMClient.from_config(
            config_path=llm_config,
            masking_config_path=masking_config,
            prompt_path=prompt_path,
        )

    effective_top_k = top_k if top_k is not None else retriever.top_k

    stats = PipelineStats(run_id=run_id, total=len(requirements))
    results: List[Dict[str, Any]] = []

    for req in requirements:
        req_id = str(req["id"])
        req_text = str(req["text"])
        log_extra = {"requirement_id": req_id}
        try:
            chunks = retriever.search(req_text, top_k=effective_top_k)
            logger.info("retrieved=%d chunks", len(chunks), extra=log_extra)
            classification = llm_client.classify_requirement(
                req_text=req_text,
                context_chunks=chunks,
                requirement_id=req_id,
            )
            stats.success += 1
            if classification.classification == "НД":
                stats.nd += 1
            stats.by_provider[classification.provider] = (
                stats.by_provider.get(classification.provider, 0) + 1
            )
            results.append(
                {
                    "id": req["id"],
                    "text": req_text,
                    "chunks": chunks,
                    "classification": classification.to_dict(),
                }
            )
            logger.info(
                "classified=%s provider=%s confidence=%.2f",
                classification.classification,
                classification.provider,
                classification.confidence,
                extra=log_extra,
            )
        except (LLMError, Exception) as exc:  # noqa: BLE001 - per-requirement isolation
            stats.errors += 1
            logger.error(
                "Failed to classify requirement: %s", exc, extra=log_extra, exc_info=True
            )
            # Per issue #45 MUST 3: on full failure mark the row as «Ошибка»
            # without breaking the pipeline. The retry workflow in the UI uses
            # this status to filter rows that should be re-run.
            results.append(
                {
                    "id": req["id"],
                    "text": req_text,
                    "error": str(exc),
                    "classification": {
                        "classification": "Ошибка",
                        "reasoning": f"Ошибка обработки: {exc}",
                        "citations": [],
                        "confidence": 0.0,
                        "requires_ba_review": True,
                        "recommendations": "Проверьте логи пайплайна и настройки провайдеров.",
                        "provider": "",
                    },
                }
            )

    save_results(
        results,
        output_file,
        source_file=input_file,
        run_id=run_id,
    )
    logger.info(
        "Pipeline finished. total=%d success=%d errors=%d nd=%d",
        stats.total,
        stats.success,
        stats.errors,
        stats.nd,
    )
    return stats


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the TZ analyzer RAG pipeline.")
    parser.add_argument("--input", required=True, help="Path to the input file (.xlsx/.docx)")
    parser.add_argument("--output", required=True, help="Path to the output Excel file (.xlsx)")
    parser.add_argument("--kb-dir", default="knowledge_base", help="Knowledge base directory")
    parser.add_argument(
        "--embedding-config",
        default="configs/embedding_config.yaml",
        help="Path to the embedding config YAML",
    )
    parser.add_argument(
        "--llm-config",
        default="configs/llm_config.yaml",
        help="Path to the LLM provider config YAML",
    )
    parser.add_argument(
        "--masking-config",
        default="configs/masking_rules.yaml",
        help="Path to the masking rules YAML",
    )
    parser.add_argument(
        "--prompt",
        default="prompts/system_classifier_v1.0.md",
        help="Path to the system prompt",
    )
    parser.add_argument("--top-k", type=int, default=None, help="Number of context chunks per requirement (defaults to embedding_config.yaml)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _configure_logging(args.verbose)
    try:
        stats = run_analysis(
            input_file=args.input,
            output_file=args.output,
            kb_dir=args.kb_dir,
            embedding_config=args.embedding_config,
            llm_config=args.llm_config,
            masking_config=args.masking_config,
            prompt_path=args.prompt,
            top_k=args.top_k,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    print(
        "run_id={run_id} обработано: {total}, успешно: {success}, ошибки: {errors}, НД: {nd}".format(
            **stats.as_dict()
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
