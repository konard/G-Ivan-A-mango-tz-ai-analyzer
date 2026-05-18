"""Tests for BL-02/BL-10 chunk metadata extraction.

Every chunk persisted in ChromaDB must carry the BL-02 / BL-16a / NFR-02
required keys: ``source``, ``chunk_idx``, ``page_number``, ``section_title``,
``section_number``, ``product``, the audit flag ``section_inherited``, and
the BL-10 parent context keys ``parent_id``, ``section_id``, ``parent_text``.
These tests pin the small extraction helpers added to
``knowledge_base/indexing/build_index.py`` so regressions in heading detection,
propagation, product inference, or parent grouping metadata surface quickly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "knowledge_base" / "indexing" / "build_index.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_index_bl02", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_required_metadata_keys_include_section_audit_flag() -> None:
    module = _load_module()
    assert module.REQUIRED_METADATA_KEYS == (
        "source",
        "chunk_idx",
        "page_number",
        "section_title",
        "section_number",
        "product",
        "section_inherited",
        "parent_id",
        "section_id",
        "parent_text",
        "related_sections",
        "prerequisites",
        "see_also",
        "dependencies_extracted",
    )


def test_embedding_config_required_metadata_matches_indexer_contract() -> None:
    module = _load_module()
    config = yaml.safe_load(
        (REPO_ROOT / "configs" / "embedding_config.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert tuple(config["required_metadata"]) == module.REQUIRED_METADATA_KEYS


def test_extract_section_detects_dotted_numeric_heading() -> None:
    module = _load_module()
    text = "4.2 Подключение коннектора Битрикс24\nДалее идёт обычный абзац."
    number, title = module.extract_section(text)
    assert number == "4.2"
    assert "Битрикс24" in title


def test_extract_section_detects_razdel_heading() -> None:
    module = _load_module()
    text = "Раздел 5.1 Интеграционные протоколы\nREST API, SOAP, Webhooks."
    number, title = module.extract_section(text)
    assert number == "5.1"
    assert "Интеграционные" in title


def test_extract_section_returns_empty_when_missing() -> None:
    module = _load_module()
    assert module.extract_section("Просто текст без заголовка.") == ("", "")
    assert module.extract_section("") == ("", "")


def test_infer_product_uses_longest_matching_prefix() -> None:
    module = _load_module()
    assert module.infer_product("Click2call_Chrome_UserManual_1_0.pdf") == "Click2Call"
    assert module.infer_product("MangoOffice_VPBX_API_v1.9.pdf") == "VPBX API"
    assert module.infer_product("RECHEVAYA-ANALITIKA_1.26.18.pdf") == "Речевая аналитика"
    assert module.infer_product("Rolevaya-model-VATS_1_26_08.pdf") == "ВАТС"
    assert module.infer_product("SIP_trunk-1.23.43.pdf") == "SIP Trunk"


def test_infer_product_returns_unknown_for_unmapped_file() -> None:
    module = _load_module()
    assert module.infer_product("totally_unknown_doc.pdf") == "unknown"


def test_build_chunk_metadata_emits_all_required_keys() -> None:
    module = _load_module()
    meta = module.build_chunk_metadata(
        source="MangoOffice_VPBX_API_v1.9.pdf",
        chunk_idx=7,
        page_number=12,
        text="4.2 Подключение коннектора Битрикс24\nКонтекст ниже.",
    )
    for key in module.REQUIRED_METADATA_KEYS:
        assert key in meta, f"missing required key {key}"
    assert meta["source"] == "MangoOffice_VPBX_API_v1.9.pdf"
    assert meta["chunk_idx"] == 7
    assert meta["page_number"] == 12
    assert meta["section_number"] == "4.2"
    assert "Битрикс24" in meta["section_title"]
    assert meta["product"] == "VPBX API"
    assert meta["section_inherited"] is False
    assert meta["related_sections"] == ""
    assert meta["prerequisites"] == ""
    assert meta["see_also"] == ""
    assert meta["dependencies_extracted"] is False


def test_build_chunk_metadata_falls_back_for_unknown_product() -> None:
    module = _load_module()
    meta = module.build_chunk_metadata(
        source="random_doc.txt",
        chunk_idx=0,
        page_number=1,
        text="Без заголовка.",
    )
    assert meta["product"] == "unknown"
    assert meta["section_title"] == ""
    assert meta["section_number"] == ""
    assert meta["section_inherited"] is False
    assert meta["page_number"] == 1


def test_section_metadata_inherits_previous_heading_across_chunks() -> None:
    module = _load_module()
    state = module.SectionPropagationState(max_pages_without_heading=6)

    first = module.build_chunk_metadata(
        source="SIP_trunk-1.23.43.pdf",
        chunk_idx=0,
        page_number=3,
        text="4.2 Настройка транка\nПервый фрагмент раздела.",
        section_state=state,
    )
    second = module.build_chunk_metadata(
        source="SIP_trunk-1.23.43.pdf",
        chunk_idx=1,
        page_number=4,
        text="Продолжение инструкции без повторения заголовка.",
        section_state=state,
    )

    assert first["section_number"] == "4.2"
    assert first["section_inherited"] is False
    assert second["section_number"] == "4.2"
    assert second["section_title"] == first["section_title"]
    assert second["section_inherited"] is True


def test_section_metadata_resets_after_safety_window() -> None:
    module = _load_module()
    state = module.SectionPropagationState(
        max_pages_without_heading=1,
        fallback_to_document_title=False,
    )

    module.build_chunk_metadata(
        source="SIP_trunk-1.23.43.pdf",
        chunk_idx=0,
        page_number=1,
        text="2.1 Подключение\nТекст раздела.",
        section_state=state,
    )
    stale = module.build_chunk_metadata(
        source="SIP_trunk-1.23.43.pdf",
        chunk_idx=1,
        page_number=3,
        text="Далёкий фрагмент без заголовка не должен наследовать 2.1.",
        section_state=state,
    )

    assert stale["section_title"] == ""
    assert stale["section_number"] == ""
    assert stale["section_inherited"] is False


def test_section_metadata_replaces_context_on_sibling_heading() -> None:
    module = _load_module()
    state = module.SectionPropagationState(max_pages_without_heading=6)

    first = module.build_chunk_metadata(
        source="LK_manual_v-119_compressed.pdf",
        chunk_idx=0,
        page_number=10,
        text="4.1 Пользователи\nОписание пользователей.",
        section_state=state,
    )
    sibling = module.build_chunk_metadata(
        source="LK_manual_v-119_compressed.pdf",
        chunk_idx=1,
        page_number=11,
        text="4.2 Роли\nОписание ролей.",
        section_state=state,
    )
    inherited = module.build_chunk_metadata(
        source="LK_manual_v-119_compressed.pdf",
        chunk_idx=2,
        page_number=12,
        text="Продолжение описания ролей.",
        section_state=state,
    )

    assert first["section_number"] == "4.1"
    assert sibling["section_number"] == "4.2"
    assert inherited["section_number"] == "4.2"
    assert inherited["section_title"] == sibling["section_title"]
    assert inherited["section_inherited"] is True


def test_section_metadata_uses_document_title_fallback_before_first_heading() -> None:
    module = _load_module()
    state = module.SectionPropagationState(fallback_to_document_title=True)

    meta = module.build_chunk_metadata(
        source="MANGO_OFFICE_LK_VATS_Auth_SSO.pdf",
        chunk_idx=0,
        page_number=1,
        text="Титульный фрагмент без нумерованного заголовка.",
        section_state=state,
    )

    assert meta["section_number"] == "document"
    assert meta["section_title"] == "MANGO OFFICE LK VATS Auth SSO"
    assert meta["section_inherited"] is False


def test_metadata_coverage_counts_fully_filled_chunks() -> None:
    module = _load_module()
    full = {
        "source": "a.pdf",
        "chunk_idx": 1,
        "page_number": 2,
        "section_title": "Title",
        "section_number": "1.1",
        "product": "VPBX API",
        "section_inherited": False,
    }
    partial = dict(full, section_title="", section_number="")
    metadatas = [full, full, full, partial, full]
    coverage = module._metadata_coverage(metadatas)
    assert 0.79 < coverage < 0.81


def test_metadata_coverage_treats_zero_chunk_idx_as_present() -> None:
    module = _load_module()
    meta = {
        "source": "a.pdf",
        "chunk_idx": 0,
        "page_number": 1,
        "section_title": "Title",
        "section_number": "1",
        "product": "VPBX API",
        "section_inherited": False,
    }
    assert module._metadata_coverage([meta]) == 1.0


def test_load_pages_md_returns_single_page(tmp_path: Path) -> None:
    module = _load_module()
    src = tmp_path / "doc.md"
    src.write_text("Привет, мир", encoding="utf-8")
    import logging

    pages = module.load_pages(src, logging.getLogger("test"))
    assert pages == [(1, "Привет, мир")]


def test_load_product_map_merges_yaml_overrides(tmp_path: Path) -> None:
    module = _load_module()
    config = tmp_path / "products.yaml"
    config.write_text(
        "prefixes:\n  click2call: \"Click2Call Pro\"\n  custom_prefix: \"Custom Product\"\n",
        encoding="utf-8",
    )
    mapping = module.load_product_map(config_path=config)
    assert mapping["click2call"] == "Click2Call Pro"
    assert mapping["custom_prefix"] == "Custom Product"
    # Built-in fallbacks should still be present for keys not overridden.
    assert mapping["sip_trunk"] == "SIP Trunk"
