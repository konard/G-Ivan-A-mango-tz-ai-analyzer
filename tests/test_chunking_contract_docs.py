from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_chunking_contract_is_synchronized_across_config_and_docs() -> None:
    config = yaml.safe_load(_read("configs/embedding_config.yaml"))
    expected = {
        "chunk_size": 512,
        "chunk_overlap": 64,
        "min_chunk_size": 384,
        "max_chunk_size": 768,
    }
    for key, value in expected.items():
        assert config[key] == value

    docs = {
        "CONCEPT": _read("docs/CONCEPT.md"),
        "embedding standard": _read("docs/standards/embedding-model.md"),
        "ADR-001": _read("docs/ADR/001-rag-architecture.md"),
        "CHANGELOG": _read("CHANGELOG.md"),
    }
    for name, text in docs.items():
        assert "512" in text, name
        assert "64" in text, name
        assert "384" in text, name
        assert "768" in text, name

    concept_current_sections = "\n".join(
        line
        for line in docs["CONCEPT"].splitlines()
        if "Чанкинг:" in line or "**Чанкер**" in line or "| **Описание** | Чтение источников" in line
    )
    assert "200–300" not in concept_current_sections
    assert "overlap 50" not in concept_current_sections


def test_required_metadata_contract_includes_citation_and_parent_fields() -> None:
    config = yaml.safe_load(_read("configs/embedding_config.yaml"))
    required = set(config["required_metadata"])

    for field in {
        "page_number",
        "section_title",
        "section_number",
        "product",
        "parent_id",
    }:
        assert field in required
