"""File uploader widget for the «📊 Анализ ТЗ» mode (BL-54, issue #196).

Restores the pilot use-case lost in the BL-41 refactor: BAs upload a
tender requirements file (``.xlsx`` / ``.docx``), pick an export format,
run the pipeline, and download the report. This module owns the input
half — the file uploader plus the two validation rules from the issue
contract:

* Extension is one of the supported formats (CONCEPT §4 FR-01).
* File size does not exceed ``MAX_UPLOAD_SIZE_MB`` (NFR-09, 10 МБ).

Filenames are routed through :func:`src.llm.masking.sanitize_log_record`
before reaching any logger so PII never leaks into JSON logs (issue #196
PII clause).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import streamlit as st

from src.llm.masking import sanitize_log_record

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_MB: int = 10
MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
SUPPORTED_EXTENSIONS: tuple[str, ...] = ("xlsx", "docx")

DEFAULT_LABEL = "📎 Файл тендерного ТЗ"
DEFAULT_HELP = (
    "Поддерживаются Excel (.xlsx) и Word (.docx) файлы. Максимальный "
    "размер — 10 МБ."
)
DEFAULT_EXTENSION_ERROR_TEMPLATE = (
    "Неподдерживаемый формат: {extension}. Допустимые форматы: {allowed}."
)
DEFAULT_SIZE_ERROR_TEMPLATE = (
    "Файл превышает лимит {limit_mb} МБ (размер: {actual_mb:.1f} МБ)."
)


@dataclass(frozen=True)
class UploadValidationResult:
    """Outcome of validating an uploaded ``UploadedFile`` handle.

    The dataclass keeps the widget code simple: the caller checks
    :attr:`ok` and reads :attr:`error_message` to render a Streamlit
    error when validation fails, or :attr:`file` to feed the pipeline.
    """

    ok: bool
    file: Optional[Any] = None
    error_message: Optional[str] = None


def _safe_filename_for_log(name: str) -> str:
    """Return a log-safe version of ``name`` via the BL-23 sanitiser."""
    sanitized: Dict[str, Any] = sanitize_log_record({"message": str(name)})
    value = sanitized.get("message")
    return str(value) if value is not None else ""


def _get_file_size(file: Any) -> int:
    """Best-effort size lookup for Streamlit ``UploadedFile``-like objects."""
    size_attr = getattr(file, "size", None)
    if isinstance(size_attr, int) and size_attr >= 0:
        return size_attr
    getbuffer = getattr(file, "getbuffer", None)
    if callable(getbuffer):
        try:
            return len(getbuffer())
        except Exception:  # noqa: BLE001
            pass
    getvalue = getattr(file, "getvalue", None)
    if callable(getvalue):
        try:
            return len(getvalue())
        except Exception:  # noqa: BLE001
            pass
    return 0


def _get_extension(name: str) -> str:
    """Extract the lower-case extension without the leading dot."""
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].strip().lower()


def validate_uploaded_file(
    file: Any,
    *,
    allowed_extensions: Iterable[str] = SUPPORTED_EXTENSIONS,
    max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES,
    extension_error_template: str = DEFAULT_EXTENSION_ERROR_TEMPLATE,
    size_error_template: str = DEFAULT_SIZE_ERROR_TEMPLATE,
) -> UploadValidationResult:
    """Validate extension + size of an ``UploadedFile`` handle.

    The Streamlit ``type=`` argument already restricts the picker, but
    we re-validate defensively: programmatic clients (e.g. tests) can
    bypass it, and operator-friendly Russian error copy is part of the
    BL-54 DoD.
    """
    if file is None:
        return UploadValidationResult(ok=False)

    allowed = tuple(ext.lower().lstrip(".") for ext in allowed_extensions)
    name = str(getattr(file, "name", "") or "")
    extension = _get_extension(name)
    if extension not in allowed:
        allowed_text = ", ".join(f".{ext}" for ext in allowed)
        error_message = extension_error_template.format(
            extension=f".{extension}" if extension else "(нет)",
            allowed=allowed_text,
        )
        logger.warning(
            "analysis_uploader: rejected file with unsupported extension",
            extra={
                "event": "UPLOAD_REJECTED_EXTENSION",
                "upload_filename": _safe_filename_for_log(name),
                "extension": extension,
            },
        )
        return UploadValidationResult(ok=False, error_message=error_message)

    size_bytes = _get_file_size(file)
    if size_bytes > max_size_bytes:
        actual_mb = size_bytes / (1024 * 1024)
        limit_mb = max_size_bytes / (1024 * 1024)
        # Render the limit as an integer when it's whole megabytes so the
        # Russian copy stays clean ("лимит 10 МБ" not "лимит 10.0 МБ").
        limit_repr = int(limit_mb) if float(limit_mb).is_integer() else limit_mb
        error_message = size_error_template.format(
            limit_mb=limit_repr,
            actual_mb=actual_mb,
        )
        logger.warning(
            "analysis_uploader: rejected file exceeding size limit",
            extra={
                "event": "UPLOAD_REJECTED_SIZE",
                "upload_filename": _safe_filename_for_log(name),
                "size_bytes": size_bytes,
                "limit_bytes": max_size_bytes,
            },
        )
        return UploadValidationResult(ok=False, error_message=error_message)

    logger.info(
        "analysis_uploader: file accepted",
        extra={
            "event": "UPLOAD_ACCEPTED",
            "upload_filename": _safe_filename_for_log(name),
            "extension": extension,
            "size_bytes": size_bytes,
        },
    )
    return UploadValidationResult(ok=True, file=file)


def render_analysis_uploader(
    label: str = DEFAULT_LABEL,
    *,
    types: Iterable[str] = SUPPORTED_EXTENSIONS,
    help_text: str = DEFAULT_HELP,
    max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES,
    extension_error_template: str = DEFAULT_EXTENSION_ERROR_TEMPLATE,
    size_error_template: str = DEFAULT_SIZE_ERROR_TEMPLATE,
    key: Optional[str] = None,
    disabled: bool = False,
) -> Optional[Any]:
    """Render the BL-54 file uploader and return a validated handle.

    Returns the underlying ``UploadedFile`` when the file passes both
    validations, ``None`` when nothing is uploaded yet, and ``None``
    after an explicit ``st.error`` for invalid uploads. Callers can rely
    on truthiness: a non-``None`` return is always ready for the
    pipeline.
    """
    uploaded = st.file_uploader(
        label,
        type=[ext.lstrip(".") for ext in types],
        help=help_text,
        key=key,
        disabled=disabled,
    )
    if uploaded is None:
        return None

    result = validate_uploaded_file(
        uploaded,
        allowed_extensions=types,
        max_size_bytes=max_size_bytes,
        extension_error_template=extension_error_template,
        size_error_template=size_error_template,
    )
    if not result.ok:
        if result.error_message:
            st.error(result.error_message)
        return None
    return result.file
