"""End-to-end RAG pipeline orchestrator.

Steps:
    1. Load requirements from an Excel file.
    2. Load (or build) the knowledge-base index.
    3. For each requirement: hybrid search → mask → LLM classify.
    4. Aggregate results into a structured list.
    5. Export to Excel with ``[Статус]`` / ``[Комментарий]`` columns.

Run as a CLI:

    python -m src.pipeline --input test_data/sample_tz.xlsx \
        --output test_data/result_test.xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.exporters import save_results
from src.llm.client import LLMClient, LLMError
from src.parsers.excel_parser import load_requirements
from src.rag.retriever import HybridRetriever, build_retriever

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    total: int = 0
    success: int = 0
    errors: int = 0
    nd: int = 0
    by_provider: Dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
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
    top_k: int = 3,
    retriever: Optional[HybridRetriever] = None,
    llm_client: Optional[LLMClient] = None,
    documents: Optional[Iterable[Dict[str, Any]]] = None,
) -> PipelineStats:
    """Run the full analysis pipeline on a single ТЗ file."""
    logger.info("Loading requirements from %s", input_file)
    requirements = load_requirements(input_file)

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

    stats = PipelineStats(total=len(requirements))
    results: List[Dict[str, Any]] = []

    for req in requirements:
        req_id = str(req["id"])
        req_text = str(req["text"])
        try:
            chunks = retriever.search(req_text, top_k=top_k)
            logger.debug("Requirement %s: %d chunks retrieved", req_id, len(chunks))
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
                "Requirement %s → %s (provider=%s, confidence=%.2f)",
                req_id,
                classification.classification,
                classification.provider,
                classification.confidence,
            )
        except (LLMError, Exception) as exc:  # noqa: BLE001
            stats.errors += 1
            logger.error("Failed to classify requirement %s: %s", req_id, exc)
            results.append(
                {
                    "id": req["id"],
                    "text": req_text,
                    "error": str(exc),
                    "classification": {
                        "classification": "НД",
                        "reasoning": f"Ошибка обработки: {exc}",
                        "citations": [],
                        "confidence": 0.0,
                        "requires_ba_review": True,
                        "recommendations": "Проверьте логи пайплайна и настройки провайдеров.",
                        "provider": "",
                    },
                }
            )

    save_results(results, output_file)
    logger.info(
        "Pipeline finished. Processed: %d, Success: %d, Errors: %d, НД: %d",
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
    parser.add_argument("--input", required=True, help="Path to the input Excel file (.xlsx)")
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
    parser.add_argument("--top-k", type=int, default=3, help="Number of context chunks per requirement")
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
        "Обработано: {total}, Успешно: {success}, Ошибки: {errors}, НД: {nd}".format(
            **stats.as_dict()
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
