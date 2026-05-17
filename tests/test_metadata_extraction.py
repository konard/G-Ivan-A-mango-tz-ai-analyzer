"""Tests for BL-02 chunk metadata extraction (issue #87).

Every chunk persisted in ChromaDB must carry the six BL-02 / BL-16a / NFR-02
required keys: ``source``, ``chunk_idx``, ``page_number``, ``section_title``,
``section_number``, ``product``. These tests pin the small extraction
helpers added to ``knowledge_base/indexing/build_index.py`` so regressions
in heading detection or product inference surface quickly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "knowledge_base" / "indexing" / "build_index.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_index_bl02", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_required_metadata_keys_are_six() -> None:
    module = _load_module()
    assert module.REQUIRED_METADATA_KEYS == (
        "source",
        "chunk_idx",
        "page_number",
        "section_title",
        "section_number",
        "product",
    )


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
    assert meta["page_number"] == 1


def test_metadata_coverage_counts_fully_filled_chunks() -> None:
    module = _load_module()
    full = {
        "source": "a.pdf",
        "chunk_idx": 1,
        "page_number": 2,
        "section_title": "Title",
        "section_number": "1.1",
        "product": "VPBX API",
    }
    partial = dict(full, section_title="", section_number="")
    metadatas = [full, full, full, partial, full]
    coverage = module._metadata_coverage(metadatas)
    assert 0.79 < coverage < 0.81


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
