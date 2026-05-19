#!/usr/bin/env python3
"""Offline DOCX structure enrichment CLI (BL-31).

Run this after DOCX parsing and before indexing/classification when a source
contains complex table-cell lists that need atom-level traceability.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.docx_structure_enricher import (  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_LLM_CONFIG_PATH,
    DEFAULT_PROMPT_PATH,
    DocxStructureEnricher,
    EnrichmentSettings,
    build_enrichment_document,
)
from src.parsers.docx_parser import DocxParser  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to the input .docx file")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the enriched JSON document",
    )
    parser.add_argument(
        "--parsing-config",
        default=None,
        help="Optional parser config YAML path",
    )
    parser.add_argument("--llm-config", default=DEFAULT_LLM_CONFIG_PATH)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT_PATH)
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic spans only")
    parser.add_argument("--ollama-base-url", default=None)
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
    )
    parser.add_argument(
        "--max-block-chars",
        type=int,
        default=6000,
        help="Maximum parser block size sent to Ollama",
    )
    parser.add_argument("--compact", action="store_true", help="Write compact JSON")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        raw_blocks = DocxParser(config_path=args.parsing_config).load_requirements(
            input_path
        )
        settings = EnrichmentSettings(
            use_llm=not args.no_llm,
            llm_config_path=args.llm_config,
            prompt_path=args.prompt,
            confidence_threshold=args.confidence_threshold,
            ollama_base_url=args.ollama_base_url,
            ollama_model=args.ollama_model,
            timeout_seconds=args.timeout_seconds,
            max_block_chars=args.max_block_chars,
        )
        requirements = DocxStructureEnricher(settings=settings).enrich_blocks(
            raw_blocks,
            source_file=str(input_path),
        )
        document = build_enrichment_document(
            requirements,
            source_file=str(input_path),
            raw_block_count=len(raw_blocks),
            settings=settings,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                document,
                ensure_ascii=False,
                indent=None if args.compact else 2,
            )
            + "\n",
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI should return a clear code
        logging.error("DOCX structure enrichment failed: %s", exc, exc_info=args.verbose)
        return 1

    print(
        json.dumps(
            {
                "source_file": str(input_path),
                "raw_block_count": len(raw_blocks),
                "requirement_count": len(requirements),
                "output": str(output_path),
                "llm_enabled": settings.use_llm,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
