"""Tests for the BL-30 semantic cache PoC script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "poc" / "semantic_cache_poc.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("semantic_cache_poc_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_prepare_replay_records_reaches_pilot_sample_size() -> None:
    module = _load_module()
    items = module.load_golden_set(REPO_ROOT / "test_data" / "rag_golden_set.json")

    records = module.prepare_replay_records(items, min_records=50, augment_per_item=2)

    assert len(items) >= 30
    assert len(records) >= 50
    assert records[0].source_refs
    assert records[0].answer
    assert records[0].intent_key


def test_threshold_simulation_reports_false_positive_accuracy_impact() -> None:
    module = _load_module()
    records = [
        module.QueryRecord(
            id="seed",
            query="Как настроить SIP?",
            answer="SIP answer",
            source_refs=["sip.pdf"],
            intent_key="sip.pdf",
        ),
        module.QueryRecord(
            id="same-text-different-intent",
            query="Как настроить SIP?",
            answer="SSO answer",
            source_refs=["sso.pdf"],
            intent_key="sso.pdf",
        ),
    ]
    embedder = module.HashingEmbedder(dimensions=64)
    embeddings = embedder.embed_many([record.query for record in records])

    result = module.simulate_cache(records, embeddings, threshold=0.99, seed_size=1)

    assert result["evaluated_records"] == 1
    assert result["cache_hits"] == 1
    assert result["false_positive_hits"] == 1
    assert result["hit_precision"] == 0.0
    assert result["accuracy_impact"] == 1.0


def test_main_writes_threshold_comparison_report(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / "semantic_cache_poc.json"

    exit_code = module.main(
        [
            "--golden",
            str(REPO_ROOT / "test_data" / "rag_golden_set.json"),
            "--output",
            str(output),
            "--embedding-backend",
            "hashing",
            "--thresholds",
            "0.90",
            "0.95",
            "0.97",
            "--min-records",
            "50",
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_records"] >= 50
    assert report["seed_size"] >= 30
    assert report["embedding_backend"] == "hashing"
    assert [result["threshold"] for result in report["results"]] == [0.9, 0.95, 0.97]
    assert {"hit_rate", "latency_savings_rate", "token_savings_estimated", "accuracy_impact"} <= set(
        report["results"][0]
    )
