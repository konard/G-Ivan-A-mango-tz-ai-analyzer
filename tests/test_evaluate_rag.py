"""Tests for BL-05 RAG evaluator (issue #87).

Pins the contract of ``scripts/evaluate/evaluate_rag.py``:

* ``hit_rank`` returns the 1-based rank of the first matching source.
* ``context_recall`` is a 0-1 fraction over expected substrings.
* ``evaluate`` aggregates Hit Rate / MRR / Context Recall correctly.
* ``write_report`` runs the report through ``sanitize_log_record`` before
  it lands on disk (BL-23 invariant).
* The ``stub`` retriever resolves the smoke subset deterministically.
* The shipped Golden Set has at least 30 items and a non-empty
  ``smoke`` subset (BL-05 / BL-05.1 contract).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "evaluate" / "evaluate_rag.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_rag_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_hit_rank_returns_one_based_rank() -> None:
    module = _load_module()
    chunks = [
        {"source": "noise.pdf"},
        {"source": "WANT.pdf"},
        {"source": "other.pdf"},
    ]
    assert module.hit_rank(chunks, ["want.pdf"]) == 2


def test_hit_rank_returns_zero_when_no_match() -> None:
    module = _load_module()
    assert module.hit_rank([{"source": "x.pdf"}], ["y.pdf"]) == 0
    assert module.hit_rank([], ["y.pdf"]) == 0
    assert module.hit_rank([{"source": "x.pdf"}], []) == 0


def test_context_recall_counts_case_insensitive_substring_hits() -> None:
    module = _load_module()
    chunks = [
        {"text": "Поддерживается SIP-транк и SSO авторизация"},
        {"text": "Click2Call расширение для Chrome"},
    ]
    assert module.context_recall(chunks, ["SIP", "Chrome"]) == 1.0
    assert module.context_recall(chunks, ["SIP", "Webex"]) == 0.5
    assert module.context_recall(chunks, []) == 1.0


def test_evaluate_aggregates_hit_rate_mrr_context_recall() -> None:
    module = _load_module()
    items = [
        module.GoldenItem(id="Q1", question="x", expected_sources=["a.pdf"], expected_substrings=["xyz"]),
        module.GoldenItem(id="Q2", question="y", expected_sources=["b.pdf"], expected_substrings=["abc"]),
        module.GoldenItem(id="Q3", question="z", expected_sources=["c.pdf"], expected_substrings=["foo"]),
    ]
    canned = {
        "x": [{"source": "a.pdf", "text": "xyz appears here"}, {"source": "n.pdf", "text": "noise"}],
        "y": [{"source": "n.pdf", "text": "noise"}, {"source": "b.pdf", "text": "no match"}],
        "z": [{"source": "n.pdf", "text": "noise"}],
    }

    def retriever_fn(query: str, k: int):
        return canned.get(query, [])[:k]

    report = module.evaluate(items, retriever_fn, k=2)
    assert report["k"] == 2
    assert report["total_items"] == 3
    # hits: Q1 (rank 1), Q2 (rank 2), Q3 (none) → 2/3
    assert abs(report["hit_rate"] - 2 / 3) < 1e-9
    # MRR: 1/1 + 1/2 + 0 = 1.5 / 3 = 0.5
    assert abs(report["mrr"] - 0.5) < 1e-9
    # context recall: 1.0 + 0.0 + 0.0 = 1/3
    assert abs(report["context_recall"] - 1 / 3) < 1e-9


def test_write_report_sanitizes_pii(tmp_path: Path) -> None:
    module = _load_module()
    report = {
        "run_id": "evaluate-rag-test",
        "items": [
            {
                "id": "Q1",
                "question": "Свяжитесь по ivan@example.com или +71234567890.",
                "top_sources": ["doc.pdf"],
                "hit": True,
            }
        ],
    }
    target = tmp_path / "reports" / "rag_eval.json"
    module.write_report(report, target)
    raw = target.read_text(encoding="utf-8")
    assert "ivan@example.com" not in raw
    assert "+71234567890" not in raw
    assert "[EMAIL]" in raw
    assert "[PHONE]" in raw
    # run_id MUST survive sanitization (FR-08 trace identifier).
    assert "evaluate-rag-test" in raw


def test_stub_retriever_resolves_smoke_subset() -> None:
    module = _load_module()
    items = module.filter_items(
        module.load_golden_set(REPO_ROOT / "test_data" / "rag_golden_set.json"), "smoke"
    )
    retriever_fn = module._build_stub_retriever(REPO_ROOT / "test_data" / "rag_golden_set.json")
    report = module.evaluate(items, retriever_fn, k=3)
    assert report["total_items"] >= 5
    # Stub retriever should achieve a perfect score on its own corpus.
    assert report["hit_rate"] == 1.0
    assert report["mrr"] == 1.0


def test_packaged_golden_set_has_at_least_30_items_and_smoke_subset() -> None:
    raw = json.loads((REPO_ROOT / "test_data" / "rag_golden_set.json").read_text(encoding="utf-8"))
    items = raw["items"]
    assert len(items) >= 30, "BL-05 Golden Set must carry at least 30 items"
    smoke = [item for item in items if item.get("subset") == "smoke"]
    assert len(smoke) >= 5, "BL-05.1 CI smoke job needs a non-empty smoke subset"


def test_main_writes_report_with_stub_retriever(tmp_path: Path) -> None:
    module = _load_module()
    output = tmp_path / "rag_eval.json"
    exit_code = module.main(
        [
            "--golden",
            str(REPO_ROOT / "test_data" / "rag_golden_set.json"),
            "--output",
            str(output),
            "--k",
            "3",
            "--retriever",
            "stub",
            "--subset",
            "smoke",
            "--min-hit-rate",
            "1.0",
            "--min-mrr",
            "1.0",
            "--min-context-recall",
            "0.5",
        ]
    )
    assert exit_code == 0, "Stub retriever should pass its own smoke thresholds"
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["retriever"] == "stub"
    assert report["subset"] == "smoke"
    assert report["hit_rate"] == 1.0


def test_load_golden_set_supports_issue_jsonl_shape(tmp_path: Path) -> None:
    module = _load_module()
    golden = tmp_path / "golden_set_v1.jsonl"
    golden.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "query": "настройка SIP транка",
                        "expected_sources": ["SIP_trunk-1.23.43.pdf"],
                        "expected_pages": [10],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "question": "SSO авторизация",
                        "expected_sources": ["MANGO_OFFICE_LK_VATS_Auth_SSO.pdf"],
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    items = module.load_golden_set(golden)

    assert [item.id for item in items] == ["JSONL-001", "JSONL-002"]
    assert items[0].question == "настройка SIP транка"
    assert items[0].expected_pages == [10]


def test_main_hybrid_returns_friendly_error_when_chroma_missing(tmp_path: Path) -> None:
    module = _load_module()
    config = tmp_path / "embedding_config.yaml"
    config.write_text(
        """
model_name: BAAI/bge-m3
chunk_size: 512
vector_store:
  persist_directory: ./missing_chroma
  collection_name: clarify_engine_kb
""".strip(),
        encoding="utf-8",
    )
    golden = tmp_path / "golden_set_v1.jsonl"
    golden.write_text(
        json.dumps(
            {"query": "test", "expected_sources": ["source.pdf"]}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--golden",
            str(golden),
            "--config",
            str(config),
            "--retriever",
            "hybrid",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert exit_code == 2
