import json
import logging
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from src.llm.client import LLMClient  # noqa: E402
from src.pipeline import run_analysis  # noqa: E402
from src.rag.retriever import _hash_embedding, build_retriever  # noqa: E402


def _build_fake_llm() -> LLMClient:
    def fake_provider(system_prompt, user_message, cfg):
        return json.dumps(
            {
                "classification": "Да",
                "confidence": 0.9,
                "reasoning": "Документация подтверждает наличие функциональности.",
                "citations": [
                    {"source": "crm.md", "section": "4.2", "quote": "поддерживает Битрикс24"}
                ],
                "requires_ba_review": False,
                "recommendations": "",
            },
            ensure_ascii=False,
        )

    return LLMClient(
        llm_config={
            "active_provider": "fake",
            "fallback_providers": ["fake"],
            "providers": {"fake": {"priority": 1, "retry_attempts": 1}},
        },
        provider_callers={"fake": fake_provider},
    )


def _build_retriever():
    documents = [
        {
            "text": "Внутренняя CRM поддерживает коннектор Битрикс24.",
            "source": "crm.md",
            "metadata": {"section": "4.2"},
        },
        {
            "text": "Запись звонков и расшифровка STT доступны в постобработке.",
            "source": "ai.md",
            "metadata": {"section": "3.1"},
        },
    ]
    return build_retriever(documents=documents, embedder=_hash_embedding)


def test_run_analysis_end_to_end(tmp_path: Path) -> None:
    input_file = tmp_path / "tz.xlsx"
    pd.DataFrame(
        {"Требование": ["Поддержка интеграции с Битрикс24", "Запись звонков"]}
    ).to_excel(input_file, index=False)

    output_file = tmp_path / "result.xlsx"
    stats = run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=_build_retriever(),
        llm_client=_build_fake_llm(),
    )

    assert stats.total == 2
    assert stats.success == 2
    assert stats.errors == 0
    assert output_file.exists()

    df = pd.read_excel(output_file)
    assert "[Статус]" in df.columns
    assert "[Комментарий]" in df.columns
    assert (df["[Статус]"] == "Да").all()


def test_run_analysis_emits_progress_snapshots(tmp_path: Path) -> None:
    input_file = tmp_path / "tz.xlsx"
    pd.DataFrame(
        {"Требование": ["Поддержка интеграции с Битрикс24", "Запись звонков"]}
    ).to_excel(input_file, index=False)
    output_file = tmp_path / "result.xlsx"
    snapshots: list[dict] = []

    run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=_build_retriever(),
        llm_client=_build_fake_llm(),
        progress_callback=lambda stats: snapshots.append(stats.as_dict()),
    )

    assert snapshots[0]["total"] == 2
    assert snapshots[0]["success"] == 0
    assert snapshots[0]["errors"] == 0
    assert snapshots[-1]["success"] == 2
    assert snapshots[-1]["errors"] == 0


def test_run_analysis_accepts_docx_input(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    input_file = tmp_path / "tz.docx"
    document = docx.Document()
    document.add_paragraph("Поддержка интеграции с Битрикс24")
    document.add_paragraph("Запись звонков")
    document.save(input_file)

    output_file = tmp_path / "result.xlsx"
    stats = run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=_build_retriever(),
        llm_client=_build_fake_llm(),
    )

    assert stats.total == 2
    assert stats.success == 2
    assert stats.errors == 0
    assert output_file.exists()

    df = pd.read_excel(output_file)
    assert list(df["Требование"]) == [
        "Поддержка интеграции с Битрикс24",
        "Запись звонков",
    ]


def test_run_analysis_exports_markdown_when_output_suffix_is_md(tmp_path: Path) -> None:
    input_file = tmp_path / "tz.xlsx"
    pd.DataFrame({"Требование": ["Поддержка интеграции с Битрикс24"]}).to_excel(
        input_file, index=False
    )

    output_file = tmp_path / "result.md"
    run_id = "abcdef0123456789abcdef0123456789"
    stats = run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=_build_retriever(),
        llm_client=_build_fake_llm(),
        run_id=run_id,
    )

    assert stats.total == 1
    assert output_file.exists()
    rendered = output_file.read_text(encoding="utf-8")
    assert f"run_id: {run_id}" in rendered
    assert "| № | Ref | Исходное требование | [Статус] |" in rendered
    assert "Поддержка интеграции с Битрикс24" in rendered


def test_run_analysis_propagates_run_id_to_logs_stats_and_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RunID must flow end-to-end: pipeline → JSON logs → ``PipelineStats.run_id``
    → ``[RunID]`` Excel column.

    Verifies the audit-trail criterion of issue #48: pipeline-level JSON log
    lines and every row of the export carry the same UUID. LLM audit records
    use a per-request 12-hex run_id per BL-23 / issue #103.
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()

    input_file = tmp_path / "tz.xlsx"
    pd.DataFrame(
        {"Требование": ["Поддержка интеграции с Битрикс24", "Запись звонков"]}
    ).to_excel(input_file, index=False)

    output_file = tmp_path / "result.xlsx"
    fixed_run_id = "abcdef0123456789abcdef0123456789"
    stats = run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=_build_retriever(),
        llm_client=_build_fake_llm(),
        run_id=fixed_run_id,
    )

    # 1. PipelineStats carries the run_id verbatim.
    assert stats.run_id == fixed_run_id
    assert stats.as_dict()["run_id"] == fixed_run_id

    # 2. JSON logs configured by the pipeline carry run_id on every record.
    log_blob = capsys.readouterr().err
    parsed_lines = []
    for line in log_blob.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed_lines.append(json.loads(line))
        except json.JSONDecodeError:
            pytest.fail(f"Non-JSON log line emitted: {line!r}")
    assert parsed_lines, "Expected at least one JSON log line from the pipeline run"
    loggers_seen = {entry.get("logger") for entry in parsed_lines}
    assert "src.parsers.excel_parser" in loggers_seen, (
        f"excel_parser logs missing from {loggers_seen}"
    )
    llm_events = {"LLM_REQUEST", "LLM_RESPONSE"}
    for entry in parsed_lines:
        if entry.get("event") in llm_events:
            assert re.fullmatch(r"[0-9a-f]{12}", entry.get("run_id", "")), entry
        else:
            assert entry.get("run_id") == fixed_run_id, entry

    events = {entry.get("event"): entry for entry in parsed_lines if entry.get("event")}
    assert events["PIPELINE_START"]["input_file"] == str(input_file)
    assert events["PIPELINE_START"]["output_file"] == str(output_file)
    assert events["PIPELINE_END"]["total_requirements"] == 2
    assert events["PIPELINE_END"]["success_count"] == 2
    assert events["PIPELINE_END"]["error_count"] == 0
    assert events["PIPELINE_END"]["nd_count"] == 0
    assert events["PIPELINE_END"]["total_latency_ms"] >= 0

    # 3. Excel export contains a [RunID] column with the same value on every row.
    df = pd.read_excel(output_file)
    assert "[RunID]" in df.columns
    assert (df["[RunID]"] == fixed_run_id).all()

    # 4. MVP four columns are present (FR-06).
    for col in ("[Статус]", "[Комментарий]", "[Confidence]", "[RunID]"):
        assert col in df.columns, f"MVP column {col} missing in export"

    # Reset root logger configuration so subsequent tests are not affected.
    root = logging.getLogger()
    root.handlers.clear()


def test_run_analysis_marks_failed_row_as_oshibka(tmp_path: Path) -> None:
    """Per issue #45 MUST 3: a per-row provider failure becomes [Статус]=Ошибка."""
    input_file = tmp_path / "tz.xlsx"
    pd.DataFrame({"Требование": ["Совсем сломанное требование"]}).to_excel(
        input_file, index=False
    )

    retriever = build_retriever(documents=[], embedder=_hash_embedding)

    def boom_provider(system_prompt, user_message, cfg):
        raise RuntimeError("simulated provider outage")

    llm_client = LLMClient(
        llm_config={
            "active_provider": "boom",
            "fallback_providers": ["boom"],
            "providers": {"boom": {"priority": 1, "retry_attempts": 1}},
        },
        provider_callers={"boom": boom_provider},
    )

    output_file = tmp_path / "result.xlsx"
    stats = run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=retriever,
        llm_client=llm_client,
    )

    assert stats.total == 1
    assert stats.success == 0
    assert stats.errors == 1

    df = pd.read_excel(output_file)
    assert df["[Статус]"].iloc[0] == "Ошибка"
