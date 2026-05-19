import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.tools.enrich_docx_structure import main as enrich_main  # noqa: E402
from src.exporters.contract import RefLocator  # noqa: E402
from src.llm.docx_structure_enricher import (  # noqa: E402
    DocxStructureEnricher,
    EnrichmentSettings,
)


def _table_block(text: str) -> dict:
    return {
        "id": 42,
        "text": text,
        "locator": {
            "type": "table",
            "table": 1,
            "row": 2,
            "col": 3,
            "paragraph": 1,
        },
    }


def test_heuristic_enrichment_splits_atoms_and_preserves_exact_spans() -> None:
    text = (
        "1.a.i Обеспечить запись звонков\n"
        "1.a.ii Настроить интеграцию с МИС\n"
        "1.a.iii Защитить персональные данные"
    )

    result = DocxStructureEnricher(
        settings=EnrichmentSettings(use_llm=False)
    ).enrich_blocks([_table_block(text)], source_file="sample_tz_1.DOCX")

    assert [item["marker"] for item in result] == ["1.a.i", "1.a.ii", "1.a.iii"]
    assert [item["exact_text"] for item in result] == [
        "1.a.i Обеспечить запись звонков",
        "1.a.ii Настроить интеграцию с МИС",
        "1.a.iii Защитить персональные данные",
    ]
    assert result[1]["parent_id"] == result[0]["id"]
    assert result[2]["parent_id"] == result[1]["id"]
    assert result[1]["type"] == "integration"
    assert result[2]["type"] == "security"

    for item in result:
        span = item["text_span"]
        assert item["exact_text"] == text[span["start"] : span["end"]]
        assert item["exact_text_hash"] == hashlib.sha256(
            item["exact_text"].encode("utf-8")
        ).hexdigest()
        assert item["source_hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert item["locator"] == _table_block(text)["locator"]
        RefLocator.model_validate(item["Ref"])


def test_llm_metadata_spans_are_sliced_from_source_text_not_copied() -> None:
    text = "1. Исходный текст\n2. Второй пункт"
    first_end = text.index("\n")
    second_start = first_end + 1
    seen_prompt = {}

    def fake_llm(system_prompt: str, user_payload: str, config: dict) -> str:
        seen_prompt["system"] = system_prompt
        seen_prompt["payload"] = json.loads(user_payload)
        return json.dumps(
            {
                "atoms": [
                    {
                        "source_id": "42",
                        "start": 0,
                        "end": first_end,
                        "marker": "1",
                        "type": "functional",
                        "confidence": 0.91,
                        "exact_text": "LLM must be ignored",
                    },
                    {
                        "source_id": "42",
                        "start": second_start,
                        "end": len(text),
                        "marker": "2",
                        "parent_marker": "1",
                        "type": "non-functional",
                        "confidence": 0.84,
                    },
                ]
            },
            ensure_ascii=False,
        )

    result = DocxStructureEnricher(
        settings=EnrichmentSettings(use_llm=True),
        llm_call=fake_llm,
    ).enrich_blocks([_table_block(text)], source_file="sample_tz_1.DOCX")

    assert "Do not return exact_text" in seen_prompt["system"]
    assert seen_prompt["payload"]["blocks"][0]["exact_text_hash"] == hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
    assert [item["exact_text"] for item in result] == [
        "1. Исходный текст",
        "2. Второй пункт",
    ]
    assert result[1]["parent_id"] == result[0]["id"]
    assert result[1]["requires_manual_review"] is True
    assert result[1]["needs_review"] is True


def test_llm_failure_falls_back_to_reviewable_heuristic_atoms() -> None:
    text = "1. Настроить очередь\n2. Подключить CRM"

    def broken_llm(system_prompt: str, user_payload: str, config: dict) -> str:
        raise RuntimeError("ollama offline")

    result = DocxStructureEnricher(
        settings=EnrichmentSettings(use_llm=True),
        llm_call=broken_llm,
    ).enrich_blocks([_table_block(text)], source_file="sample_tz_1.DOCX")

    assert [item["marker"] for item in result] == ["1", "2"]
    assert all(item["enrichment_source"] == "heuristic_fallback" for item in result)
    assert all(item["requires_manual_review"] is True for item in result)
    assert all("ollama offline" in item["warnings"][0] for item in result)


def test_cli_enriches_sample_docx_without_ollama(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    output_path = tmp_path / "sample_tz_1.enriched.json"

    exit_code = enrich_main(
        [
            "--input",
            "test_data/sample_tz_1.DOCX",
            "--output",
            str(output_path),
            "--no-llm",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "docx_structure_enrichment_v1"
    assert payload["source_file"] == "test_data/sample_tz_1.DOCX"
    assert payload["raw_block_count"] > 0
    assert payload["requirement_count"] >= payload["raw_block_count"]
    assert payload["requirements"]
    assert all("exact_text" in item for item in payload["requirements"])
    RefLocator.model_validate(payload["requirements"][0]["Ref"])
