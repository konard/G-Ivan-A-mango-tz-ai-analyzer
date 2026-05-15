"""Tests for the Streamlit retry-on-errors workflow (issue #45 MUST 5).

The Streamlit module imports ``streamlit`` at module load time; we stub it
out in :mod:`tests.conftest` only when Streamlit is missing. To keep this
test lightweight we import the retry helper directly and stub the upstream
``run_analysis`` so no real pipeline call happens.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")


def _ensure_streamlit_stub() -> None:
    """Provide a minimal stub for streamlit so :mod:`src.app` can import."""
    if "streamlit" in sys.modules:
        return

    stub = ModuleType("streamlit")

    def _noop(*_args, **_kwargs):
        return None

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _ctx(*_args, **_kwargs):
        return _Ctx()

    for attr in (
        "set_page_config",
        "title",
        "write",
        "header",
        "subheader",
        "caption",
        "info",
        "success",
        "warning",
        "error",
        "markdown",
        "divider",
        "selectbox",
        "button",
        "file_uploader",
        "download_button",
        "rerun",
        "link_button",
    ):
        setattr(stub, attr, _noop)
    stub.session_state = {}
    stub.sidebar = _Ctx()
    stub.tabs = lambda labels: [_Ctx() for _ in labels]
    stub.columns = lambda n: [type("C", (), {"metric": _noop})() for _ in range(n)]
    stub.progress = lambda *a, **kw: type(
        "P", (), {"progress": _noop, "empty": _noop}
    )()
    sys.modules["streamlit"] = stub


_ensure_streamlit_stub()

from src.app import _retry_error_rows  # noqa: E402
from src.pipeline import PipelineStats  # noqa: E402


def _make_source_bytes() -> bytes:
    df = pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Требование": ["Req A", "Req B", "Req C"],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _make_result_bytes(statuses: list[str]) -> bytes:
    df = pd.DataFrame(
        {
            "ID": list(range(1, len(statuses) + 1)),
            "Требование": [f"Req {chr(64 + i)}" for i in range(1, len(statuses) + 1)],
            "[Статус]": statuses,
            "[Комментарий]": ["initial" for _ in statuses],
            "[Confidence]": [0.0 for _ in statuses],
            "[RunID]": ["run-1" for _ in statuses],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def test_retry_patches_only_error_rows(monkeypatch, tmp_path: Path) -> None:
    """Retry MUST overwrite Ошибка rows and leave the rest untouched."""

    def fake_run_analysis(*, input_file, output_file, run_id, **_kwargs):
        # The subset workbook contains only the rows we want to retry. Emit a
        # result that flips them to «Да» so we can assert the patch behaviour.
        subset_df = pd.read_excel(input_file)
        n = len(subset_df)
        result = subset_df.copy()
        result["[Статус]"] = ["Да"] * n
        result["[Комментарий]"] = ["fixed"] * n
        result["[Confidence]"] = [0.95] * n
        result["[RunID]"] = [run_id] * n
        result.to_excel(output_file, index=False)
        return PipelineStats(run_id=run_id, total=n, success=n, errors=0, nd=0)

    monkeypatch.setattr("src.app.run_analysis", fake_run_analysis)

    source_bytes = _make_source_bytes()
    result_bytes = _make_result_bytes(["Да", "Ошибка", "Ошибка"])

    retry_stats, patched_bytes, retry_run_id, retried = _retry_error_rows(
        source_bytes=source_bytes,
        source_filename="tz.xlsx",
        last_result_bytes=result_bytes,
    )

    assert retried == 2
    assert retry_stats.success == 2
    assert retry_run_id

    patched_df = pd.read_excel(io.BytesIO(patched_bytes))
    # Original good row is untouched.
    assert patched_df.loc[0, "[Статус]"] == "Да"
    assert patched_df.loc[0, "[Комментарий]"] == "initial"
    assert patched_df.loc[0, "[RunID]"] == "run-1"
    # Error rows now carry the retry outcome including the new RunID.
    assert patched_df.loc[1, "[Статус]"] == "Да"
    assert patched_df.loc[1, "[Комментарий]"] == "fixed"
    assert patched_df.loc[1, "[RunID]"] == retry_run_id
    assert patched_df.loc[2, "[Статус]"] == "Да"
    assert patched_df.loc[2, "[RunID]"] == retry_run_id


def test_retry_raises_when_no_error_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.run_analysis",
        lambda *a, **kw: pytest.fail("run_analysis must not be called"),
    )
    source_bytes = _make_source_bytes()
    result_bytes = _make_result_bytes(["Да", "Да", "Да"])

    with pytest.raises(RuntimeError, match="нет строк со статусом «Ошибка»"):
        _retry_error_rows(
            source_bytes=source_bytes,
            source_filename="tz.xlsx",
            last_result_bytes=result_bytes,
        )
