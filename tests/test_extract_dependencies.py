"""Tests for BL-14 offline dependency extraction."""

from __future__ import annotations

from typing import Any, Dict, List

from scripts.tools import extract_dependencies as deps


def test_regex_extracts_sections_prerequisites_and_see_also() -> None:
    text = (
        "Перед подключением требуется предварительная настройка SIP-транка. "
        "См. раздел 7.3.6 для параметров безопасности. "
        "См. также пункт 4.2."
    )

    result = deps.extract_dependencies(
        text,
        metadata={"source": "LK_manual_v-119_compressed.pdf"},
    )

    assert result.related_sections == [
        "LK_manual_v-119_compressed.pdf::7.3.6",
        "LK_manual_v-119_compressed.pdf::4.2",
    ]
    assert any("SIP" in item for item in result.prerequisites)
    assert any("4.2" in item for item in result.see_also)
    assert result.has_dependency_data is True


def test_enrich_metadata_uses_chroma_safe_scalar_lists() -> None:
    original = {"source": "doc.pdf", "chunk_idx": 3}
    enriched = deps.enrich_metadata(
        original,
        "Описание. См. раздел 7.3.6. См. п. 7.3.6 и пункт 7.3.7.",
        settings=deps.ExtractionSettings(use_ollama=False),
    )

    assert original == {"source": "doc.pdf", "chunk_idx": 3}
    assert enriched["related_sections"] == "doc.pdf::7.3.6;doc.pdf::7.3.7"
    assert enriched["see_also"] == "doc.pdf::7.3.6;doc.pdf::7.3.7"
    assert enriched["prerequisites"] == ""
    assert enriched["dependencies_extracted"] is True
    assert enriched["has_dependencies"] is True
    assert enriched["has_prerequisites"] is False


class _FakeCollection:
    def __init__(self) -> None:
        self.updated: List[Dict[str, Any]] = []

    def get(self, *, include):
        assert include == ["documents", "metadatas"]
        return {
            "ids": ["new", "done"],
            "documents": [
                "См. раздел 7.3.6.",
                "См. раздел 8.1.",
            ],
            "metadatas": [
                {"source": "doc.pdf", "chunk_idx": 0},
                {
                    "source": "doc.pdf",
                    "chunk_idx": 1,
                    "dependencies_extracted": True,
                    "related_sections": "doc.pdf::8.1",
                },
            ],
        }

    def update(self, *, ids, metadatas):
        self.updated.append({"ids": ids, "metadatas": metadatas})


def test_update_collection_dependencies_is_idempotent_by_default() -> None:
    collection = _FakeCollection()

    stats = deps.update_collection_dependencies(
        collection,
        settings=deps.ExtractionSettings(use_ollama=False),
        force=False,
        batch_size=10,
    )

    assert stats.total_chunks == 2
    assert stats.processed_chunks == 1
    assert stats.skipped_already_extracted == 1
    assert stats.chunks_with_markers == 1
    assert stats.chunks_with_related_sections == 1
    assert collection.updated == [
        {
            "ids": ["new"],
            "metadatas": [
                {
                    "source": "doc.pdf",
                    "chunk_idx": 0,
                    "related_sections": "doc.pdf::7.3.6",
                    "prerequisites": "",
                    "see_also": "doc.pdf::7.3.6",
                    "dependencies_extracted": True,
                    "has_dependencies": True,
                    "has_prerequisites": False,
                    "dependency_extraction_method": "regex",
                }
            ],
        }
    ]
