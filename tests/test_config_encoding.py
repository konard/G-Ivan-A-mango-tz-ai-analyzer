"""Regression tests for UTF-8 config loading on Windows cp1251 locales."""

from __future__ import annotations

import builtins
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Callable

import yaml

from knowledge_base.indexing import build_index
from src.llm.client import _load_llm_config
from src.llm.masking import _load_yaml as load_masking_config
from src.rag.chunker import load_chunk_config
from src.rag.retriever import load_embedding_config
from src.utils.export import load_excel_columns


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_streamlit_stub() -> None:
    stub = sys.modules.get("streamlit")
    if stub is None:
        stub = ModuleType("streamlit")
        sys.modules["streamlit"] = stub

    def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    def _decorator(*_args: Any, **_kwargs: Any) -> Callable[[Any], Any]:
        def _wrap(fn: Any) -> Any:
            return fn

        return _wrap

    for attr in (
        "set_page_config",
        "error",
        "warning",
        "cache_resource",
    ):
        if not hasattr(stub, attr):
            setattr(stub, attr, _decorator if attr == "cache_resource" else _noop)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def test_yaml_safe_load_reads_cyrillic_config_with_utf8() -> None:
    """The shipped YAML with Cyrillic comments must decode as UTF-8."""
    raw = (REPO_ROOT / "configs" / "embedding_config.yaml").read_text(
        encoding="utf-8"
    )
    config = yaml.safe_load(raw)

    assert config["model_name"] == "BAAI/bge-m3"


def test_config_loaders_pass_utf8_to_path_read_text(monkeypatch) -> None:
    """Config readers must not rely on the OS default encoding."""
    _ensure_streamlit_stub()
    from src.ui import app as ui_app

    original_read_text = Path.read_text
    config_root = (REPO_ROOT / "configs").resolve()

    def strict_read_text(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        resolved = self.resolve()
        if _is_relative_to(resolved, config_root) and self.suffix in {".yaml", ".yml"}:
            assert encoding == "utf-8", f"{self} must be read as UTF-8"
        return original_read_text(
            self,
            encoding=encoding,
            errors=errors,
        )

    monkeypatch.setattr(Path, "read_text", strict_read_text)

    checks: list[Callable[[], Any]] = [
        lambda: load_embedding_config(
            str(REPO_ROOT / "configs" / "embedding_config.yaml")
        ),
        lambda: load_chunk_config(str(REPO_ROOT / "configs" / "embedding_config.yaml")),
        lambda: _load_llm_config(str(REPO_ROOT / "configs" / "llm_config.yaml")),
        lambda: load_masking_config(str(REPO_ROOT / "configs" / "masking_rules.yaml")),
        lambda: ui_app.load_llm_config(REPO_ROOT / "configs" / "llm_config.yaml"),
        lambda: ui_app.load_ui_config(REPO_ROOT / "configs" / "ui_config.yaml"),
        lambda: load_excel_columns(REPO_ROOT / "configs" / "export_config.yaml"),
    ]

    for load_config in checks:
        assert load_config()


def test_build_index_load_config_opens_yaml_as_utf8(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    original_open = builtins.open

    def spy_open(*args: Any, **kwargs: Any) -> Any:
        if Path(args[0]).name == "embedding_config.yaml":
            captured["encoding"] = kwargs.get("encoding")
        return original_open(*args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)

    assert build_index.load_config()["model_name"] == "BAAI/bge-m3"
    assert captured["encoding"] == "utf-8"


def test_gitattributes_pins_text_files_to_utf8_lf() -> None:
    attrs = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "*.yaml  text eol=lf encoding=utf-8" in attrs
    assert "*.md    text eol=lf encoding=utf-8" in attrs
    assert "*.py    text eol=lf encoding=utf-8" in attrs
