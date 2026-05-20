"""Tests for BL-58 retrieval architecture experiments harness.

Pins the contract of ``scripts/research/retrieval_experiments.py`` and the
Golden Set ``data/retrieval_golden_set_v1.jsonl``:

* The Golden Set ships with at least 15 items and covers all three synthetic
  failure modes (multi_facet / short_sparse / paraphrase_synonymy) plus the
  ``real_sample_tz_1`` subset.
* ``load_golden_set`` returns ``GoldenItem`` records that preserve every
  field used downstream (id, case_type, subset, requirement_text, ...).
* All six strategies registered in ``STRATEGY_FNS`` return at most ``top_k``
  hits with the chunk schema the runner expects.
* Strategy execution is deterministic for a fixed seed and Golden Set.
* The CLI ``main`` writes a non-empty report to the requested path and
  reports the strict-mode fallback rate for the strategies it ran.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "retrieval_experiments.py"
GOLDEN_PATH = REPO_ROOT / "data" / "retrieval_golden_set_v1.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "retrieval_experiments_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def module():
    return _load_module()


@pytest.fixture(scope="module")
def golden_items(module):
    return module.load_golden_set(GOLDEN_PATH)


@pytest.fixture(scope="module")
def corpus(module):
    return module.CorpusView.build(module.SYNTHETIC_CHUNKS)


# --------------------------------------------------------------- golden set --
def test_golden_set_meets_dod_size_and_coverage(golden_items) -> None:
    assert len(golden_items) >= 15, "BL-58 DoD requires at least 15 labelled requirements"
    case_types = {item.case_type for item in golden_items}
    assert {"multi_facet", "short_sparse", "paraphrase_synonymy"} <= case_types, (
        "Golden Set must cover the three synthetic failure cases listed in the issue"
    )
    subsets = {item.subset for item in golden_items}
    assert "synthetic" in subsets and "real_sample_tz_1" in subsets, (
        "Golden Set must contain both synthetic items and real sample_tz_1 requirements"
    )
    real_count = sum(1 for it in golden_items if it.subset == "real_sample_tz_1")
    assert real_count >= 12, "DoD requires at least 12 realistic requirements"


def test_golden_item_fields_are_preserved(module, golden_items) -> None:
    for item in golden_items:
        assert item.id
        assert item.requirement_text
        assert isinstance(item.expected_sources, list)
        assert isinstance(item.expected_substrings, list)
        assert isinstance(item.expected_section_numbers, list)
        assert item.case_type in {"multi_facet", "short_sparse", "paraphrase_synonymy", "direct"}


def test_golden_set_ids_are_unique(golden_items) -> None:
    ids = [it.id for it in golden_items]
    assert len(ids) == len(set(ids)), "Golden Set ids must be unique"


# ----------------------------------------------------------------- strategies --
ALL_STRATEGIES = (
    "naive",
    "query_expansion",
    "parent_context_tuning",
    "hybrid_alpha_tuning",
    "metadata_routing",
    "reranker_cross_encoder",
)


def test_strategy_registry_lists_required_strategies(module) -> None:
    # The DoD requires the naive baseline plus at least four advanced strategies.
    assert set(ALL_STRATEGIES) <= set(module.STRATEGY_FNS), (
        "All BL-58 strategies must be registered"
    )
    # The harness must surface them through ALL_STRATEGIES for the CLI.
    assert set(ALL_STRATEGIES) <= set(module.ALL_STRATEGIES)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_strategy_returns_top_k_hits_with_required_schema(
    module, corpus, strategy
) -> None:
    fn = module.STRATEGY_FNS[strategy]
    hits = fn(corpus, "Поддержка SSO и ролевая модель", top_k=5)
    assert 0 < len(hits) <= 5
    for hit in hits:
        assert "source" in hit and hit["source"]
        assert "text" in hit and hit["text"]
        assert "score" in hit
        assert isinstance(hit["score"], float)


def test_strategy_naive_finds_sso_source(module, corpus) -> None:
    hits = module.strategy_naive(corpus, "Поддержка SSO", top_k=5)
    sources = {h["source"] for h in hits}
    assert "MANGO_OFFICE_LK_VATS_Auth_SSO.pdf" in sources


def test_query_expansion_expands_short_acronyms(module) -> None:
    expansions = module._expand_query("SSO")
    joined = " ".join(expansions).lower()
    assert "saml" in joined or "single sign-on" in joined


def test_metadata_routing_prefilters_doc_types(module, corpus) -> None:
    # A query containing 'API' should route to chunks whose doc_type is 'api'.
    hits = module.strategy_metadata_routing(corpus, "REST API интеграция", top_k=5)
    doc_types = {h.get("doc_type") for h in hits}
    assert "api" in doc_types


def test_parent_context_tuning_expands_text(module, corpus) -> None:
    hits = module.strategy_parent_context_tuning(corpus, "ролевая модель", top_k=5)
    assert any(h.get("parent_context") for h in hits)


# ------------------------------------------------------------------- runner --
def test_evaluate_strategy_metrics_shape(module, corpus, golden_items) -> None:
    result = module.evaluate_strategy(
        strategy="naive",
        items=golden_items[:5],
        corpus=corpus,
        top_k=5,
        strict_min_score=0.30,
    )
    metrics = result.metrics
    assert metrics["n"] == 5
    assert metrics["top_k"] == 5
    for key in (
        "hit_rate_at_k",
        "mrr_at_k",
        "recall_at_k",
        "precision_at_3",
        "context_recall",
        "strict_mode_fallback_rate",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_mean_ms",
    ):
        assert key in metrics
        assert 0.0 <= float(metrics[key]) or key.startswith("latency_")


def test_evaluate_strategy_is_deterministic(module, corpus, golden_items) -> None:
    first = module.evaluate_strategy("naive", golden_items, corpus, 5, 0.30)
    second = module.evaluate_strategy("naive", golden_items, corpus, 5, 0.30)
    # Latency fluctuates between runs; rank-based metrics must be stable.
    keys = (
        "hit_rate_at_k",
        "mrr_at_k",
        "recall_at_k",
        "precision_at_3",
        "context_recall",
        "strict_mode_fallback_rate",
    )
    for key in keys:
        assert first.metrics[key] == second.metrics[key]
    assert [it["top_sources"] for it in first.items] == [
        it["top_sources"] for it in second.items
    ]


def test_main_writes_report_for_two_strategies(module, tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    exit_code = module.main(
        [
            "--golden",
            str(GOLDEN_PATH),
            "--strategy",
            "naive",
            "--strategy",
            "query_expansion",
            "--output",
            str(output),
            "--top-k",
            "5",
            "--quiet",
        ]
    )
    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    strategies = [r["strategy"] for r in payload["results"]]
    assert strategies == ["naive", "query_expansion"]
    for entry in payload["results"]:
        assert entry["metrics"]["n"] >= 15
        assert 0.0 <= entry["metrics"]["hit_rate_at_k"] <= 1.0
        assert 0.0 <= entry["metrics"]["mrr_at_k"] <= 1.0


def test_main_all_strategies_runs_six_experiments(module, tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    exit_code = module.main(
        [
            "--golden",
            str(GOLDEN_PATH),
            "--strategy",
            "all",
            "--output",
            str(output),
            "--top-k",
            "5",
            "--quiet",
        ]
    )
    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [r["strategy"] for r in payload["results"]] == list(ALL_STRATEGIES)


# --------------------------------------------------------------- regressions --
def test_strict_mode_fallback_threshold_is_configurable(module, corpus, golden_items) -> None:
    # Lowering the threshold to 0 must drop the fallback rate; the harness
    # must not silently swallow STRICT_MODE configuration.
    high = module.evaluate_strategy("naive", golden_items, corpus, 5, 0.99)
    low = module.evaluate_strategy("naive", golden_items, corpus, 5, 0.0)
    assert high.metrics["strict_mode_fallback_rate"] >= low.metrics["strict_mode_fallback_rate"]
    assert low.metrics["strict_mode_fallback_rate"] == 0.0


def test_hit_rank_returns_zero_when_expected_sources_empty(module) -> None:
    chunks = [{"source": "x.pdf"}]
    assert module._hit_rank(chunks, []) == 0


def test_percentile_handles_short_sequences(module) -> None:
    assert module._percentile([], 95) == 0.0
    assert module._percentile([5.0], 95) == 5.0
    assert module._percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
