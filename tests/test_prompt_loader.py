"""Tests for ``src.llm.prompt_loader`` (BL-08, issue #94)."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.prompt_loader import (  # noqa: E402
    PromptInfo,
    PromptNotFoundError,
    compute_sha256,
    load_few_shot_examples,
    load_prompt,
    load_prompt_from_path,
    parse_prompt_filename,
)

REPO_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"

EXPECTED_CLASSIFIER_SHA = (
    "e3070fdc8055f7d7653412304647ae541897d8b1b59370eb5c614651f05590f5"
)
EXPECTED_RAG_SHA = (
    "a0339756d33cbbb32a461b7dbd88e72d2d7e60ec3c3660c68f052783a19614a4"
)
EXPECTED_FEW_SHOT_SHA = (
    "78079ef0b7110ba87d396af51dd7be55ea6ae4aa99f9472c9d8fbb344a0fd346"
)


def test_compute_sha256_matches_hashlib() -> None:
    payload = "Clarify Engine"
    assert compute_sha256(payload) == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert compute_sha256(payload.encode("utf-8")) == compute_sha256(payload)


def test_parse_prompt_filename_valid() -> None:
    assert parse_prompt_filename("system_classifier_v1.0.md") == (
        "system_classifier",
        "v1.0",
    )
    assert parse_prompt_filename("system_rag_v2.10.txt") == ("system_rag", "v2.10")
    assert parse_prompt_filename("few_shot_examples_v1.0.json") == (
        "few_shot_examples",
        "v1.0",
    )


def test_parse_prompt_filename_invalid() -> None:
    assert parse_prompt_filename("system_classifier.md") is None
    assert parse_prompt_filename("system_classifier_v1.md") is None
    assert parse_prompt_filename("v1.0.md") is None


def test_load_prompt_classifier_real_file() -> None:
    info = load_prompt(
        "system_classifier", version="v1.0", prompts_dir=REPO_PROMPTS
    )
    assert isinstance(info, PromptInfo)
    assert info.name == "system_classifier"
    assert info.version == "v1.0"
    assert info.path == (REPO_PROMPTS / "system_classifier_v1.0.md").resolve()
    assert info.sha256 == EXPECTED_CLASSIFIER_SHA
    assert "Business Analyst" in info.content
    assert str(info) == info.content


def test_load_prompt_system_rag_real_file() -> None:
    info = load_prompt("system_rag", version="v1.0", prompts_dir=REPO_PROMPTS)
    assert info.sha256 == EXPECTED_RAG_SHA
    assert "<context>" in info.content
    assert "<question>" in info.content


def test_load_prompt_prefers_md_then_txt(tmp_path: Path) -> None:
    (tmp_path / "alpha_v1.0.md").write_text("md content", encoding="utf-8")
    (tmp_path / "alpha_v1.0.txt").write_text("txt content", encoding="utf-8")
    info = load_prompt("alpha", version="v1.0", prompts_dir=tmp_path)
    assert info.content == "md content"

    (tmp_path / "beta_v1.0.txt").write_text("txt only", encoding="utf-8")
    beta = load_prompt("beta", version="v1.0", prompts_dir=tmp_path)
    assert beta.content == "txt only"
    assert beta.path.suffix == ".txt"


def test_load_prompt_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(PromptNotFoundError) as excinfo:
        load_prompt("missing", version="v9.9", prompts_dir=tmp_path)
    assert "missing" in str(excinfo.value)
    assert "v9.9" in str(excinfo.value)


def test_load_prompt_emits_log_with_run_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "gamma_v1.0.md").write_text("hello", encoding="utf-8")
    with caplog.at_level(logging.INFO, logger="src.llm.prompt_loader"):
        info = load_prompt(
            "gamma", version="v1.0", prompts_dir=tmp_path, run_id="run-123"
        )
    record = next(
        r for r in caplog.records if r.name == "src.llm.prompt_loader"
    )
    assert getattr(record, "run_id", None) == "run-123"
    assert getattr(record, "prompt_name", None) == "gamma"
    assert getattr(record, "prompt_version", None) == "v1.0"
    assert getattr(record, "prompt_hash", None) == info.sha256
    assert getattr(record, "prompt_sha256", None) == info.sha256


def test_load_prompt_logs_without_run_id_supplied(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # When run_id is not supplied the loader still emits the audit fields.
    # We do not assert absence of ``run_id`` on the record because the
    # pipeline JSON handler (``_RunIdFilter``) may inject one on the root
    # logger when other tests configure it earlier in the session.
    (tmp_path / "delta_v1.0.md").write_text("payload", encoding="utf-8")
    with caplog.at_level(logging.INFO, logger="src.llm.prompt_loader"):
        load_prompt("delta", version="v1.0", prompts_dir=tmp_path)
    record = next(r for r in caplog.records if r.name == "src.llm.prompt_loader")
    assert getattr(record, "prompt_name", None) == "delta"
    assert getattr(record, "prompt_version", None) == "v1.0"
    assert getattr(record, "prompt_hash", None)
    assert getattr(record, "prompt_sha256", None)


def test_load_few_shot_examples_real_file() -> None:
    examples, sha = load_few_shot_examples(
        "few_shot_examples", "v1.0", prompts_dir=REPO_PROMPTS
    )
    assert sha == EXPECTED_FEW_SHOT_SHA
    assert isinstance(examples, list)
    assert examples, "few-shot examples should not be empty"
    assert all(isinstance(item, dict) for item in examples)


def test_load_few_shot_examples_missing(tmp_path: Path) -> None:
    with pytest.raises(PromptNotFoundError):
        load_few_shot_examples("absent", "v1.0", prompts_dir=tmp_path)


def test_load_few_shot_examples_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "bad_v1.0.json").write_text("not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_few_shot_examples("bad", "v1.0", prompts_dir=tmp_path)


def test_load_prompt_from_path_versioned_filename() -> None:
    info = load_prompt_from_path(REPO_PROMPTS / "system_classifier_v1.0.md")
    assert info.name == "system_classifier"
    assert info.version == "v1.0"
    assert info.sha256 == EXPECTED_CLASSIFIER_SHA


def test_load_prompt_from_path_non_conventional_filename(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy_prompt.md"
    legacy.write_text("legacy", encoding="utf-8")
    info = load_prompt_from_path(legacy)
    assert info.name == "legacy_prompt"
    assert info.version == "unknown"
    assert info.content == "legacy"


def test_load_prompt_from_path_missing(tmp_path: Path) -> None:
    with pytest.raises(PromptNotFoundError):
        load_prompt_from_path(tmp_path / "nope.md")


def test_prompt_info_is_immutable() -> None:
    info = load_prompt(
        "system_classifier", version="v1.0", prompts_dir=REPO_PROMPTS
    )
    with pytest.raises(Exception):
        info.content = "mutated"  # type: ignore[misc]
