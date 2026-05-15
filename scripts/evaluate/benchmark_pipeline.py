#!/usr/bin/env python3
"""Pipeline throughput benchmark (issue #45 SHOULD 1).

Generates an Excel ТЗ with N synthetic requirements (default: 50) and runs the
full pipeline against it. Useful for sanity-checking provider latency and
sequential-call assumptions (no parallel LLM calls — see ADR-001).

Two modes:

* ``--mode stub`` — forces the offline ``stub`` provider so the benchmark
  measures the pipeline overhead alone (parsing + retrieval + export). Useful
  for CI; default.
* ``--mode production`` — uses the project's regular LLM config (real keys
  required). Suitable for periodic SLA checks.

Example::

    python scripts/evaluate/benchmark_pipeline.py --mode stub --count 50
    python scripts/evaluate/benchmark_pipeline.py --mode production --count 20

Output is a single JSON line on stdout::

    {"mode": "stub", "count": 50, "duration_seconds": 3.21,
     "throughput_per_second": 15.5, "stats": {...}}
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import run_analysis  # noqa: E402

DEFAULT_COUNT = 50
DEFAULT_MODE = "stub"
SUPPORTED_MODES = ("stub", "production")


def _generate_workbook(target: Path, count: int) -> None:
    """Write a synthetic ТЗ workbook with ``count`` requirements."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for the benchmark. Install requirements.txt."
        ) from exc

    rows = [
        {
            "ID": i + 1,
            "Требование": (
                f"Требование #{i + 1}: проверить поддержку функциональности "
                f"подсистемой MANGO CRM (синтетический бенчмарк)."
            ),
        }
        for i in range(count)
    ]
    pd.DataFrame(rows).to_excel(target, index=False)


def _force_stub_llm_config(tmp_root: Path) -> Path:
    """Write a minimal LLM config that pins the stub provider only."""
    import yaml  # type: ignore

    cfg = {
        "active_provider": "stub",
        "fallback_providers": ["stub"],
        "providers": {"stub": {"priority": 1, "retry_attempts": 1}},
    }
    path = tmp_root / "stub_llm_config.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def benchmark(mode: str, count: int) -> dict:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode {mode!r}; expected one of {SUPPORTED_MODES}")

    run_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / "benchmark_tz.xlsx"
        output_path = tmp_path / f"benchmark_result_{run_id}.xlsx"
        _generate_workbook(input_path, count)

        kwargs = {
            "input_file": str(input_path),
            "output_file": str(output_path),
            "run_id": run_id,
        }
        if mode == "stub":
            kwargs["llm_config"] = str(_force_stub_llm_config(tmp_path))

        started = time.perf_counter()
        stats = run_analysis(**kwargs)
        duration = time.perf_counter() - started

    throughput = count / duration if duration > 0 else 0.0
    return {
        "mode": mode,
        "count": count,
        "duration_seconds": round(duration, 3),
        "throughput_per_second": round(throughput, 3),
        "stats": stats.as_dict(),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--mode",
        choices=SUPPORTED_MODES,
        default=DEFAULT_MODE,
        help=f"Pipeline mode (default: {DEFAULT_MODE})",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of synthetic requirements (default: {DEFAULT_COUNT})",
    )
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error("--count must be a positive integer")

    result = benchmark(args.mode, args.count)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
