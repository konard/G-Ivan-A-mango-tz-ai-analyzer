import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from src.llm.client import LLMClient  # noqa: E402
from src.pipeline import run_analysis  # noqa: E402
from src.rag.retriever import _hash_embedding, build_retriever  # noqa: E402


def test_run_analysis_end_to_end(tmp_path: Path) -> None:
    input_file = tmp_path / "tz.xlsx"
    pd.DataFrame(
        {"Требование": ["Поддержка интеграции с Битрикс24", "Запись звонков"]}
    ).to_excel(input_file, index=False)

    documents = [
        {
            "text": "MANGO CRM поддерживает коннектор Битрикс24.",
            "source": "crm.md",
            "metadata": {"section": "4.2"},
        },
        {
            "text": "Запись звонков и расшифровка STT доступны в постобработке.",
            "source": "ai.md",
            "metadata": {"section": "3.1"},
        },
    ]
    retriever = build_retriever(documents=documents, embedder=_hash_embedding)

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

    llm_client = LLMClient(
        llm_config={
            "active_provider": "fake",
            "fallback_providers": ["fake"],
            "providers": {"fake": {"priority": 1, "retry_attempts": 1}},
        },
        provider_callers={"fake": fake_provider},
    )

    output_file = tmp_path / "result.xlsx"
    stats = run_analysis(
        input_file=str(input_file),
        output_file=str(output_file),
        retriever=retriever,
        llm_client=llm_client,
    )

    assert stats.total == 2
    assert stats.success == 2
    assert stats.errors == 0
    assert output_file.exists()

    df = pd.read_excel(output_file)
    assert "[Статус]" in df.columns
    assert "[Комментарий]" in df.columns
    assert (df["[Статус]"] == "Да").all()


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
