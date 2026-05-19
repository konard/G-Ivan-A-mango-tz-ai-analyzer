"""Sidebar helpers that are independent of the mode/top-k slider (BL-55).

The warmup button (issue #199) lives here so :mod:`src.ui.components.mode_selector`
can stay focused on the mode/top-k controls. The render function is opt-in:
:func:`should_render_warmup_button` decides whether the BA actually sees it,
based on ``configs/ui_config.yaml`` and ``OLLAMA_BASE_URL``. Tests monkeypatch
the warmup HTTP call to avoid touching a real Ollama daemon.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import streamlit as st

from src.ui.constants import LABELS

logger = logging.getLogger(__name__)

WARMUP_PROMPT = "ok"
WARMUP_KEEP_ALIVE = "10m"
WARMUP_TIMEOUT_SECONDS = 120
WARMUP_LOCAL_HOSTNAMES: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"


def _get_debug_mode(ui_config: Optional[Dict[str, Any]]) -> bool:
    """Return ``ui.debug_mode`` from ``configs/ui_config.yaml`` (or ``False``)."""
    if not isinstance(ui_config, dict):
        return False
    ui_section = ui_config.get("ui")
    if not isinstance(ui_section, dict):
        return False
    return bool(ui_section.get("debug_mode", False))


def _get_ollama_base_url() -> str:
    """Return the resolved Ollama base URL from environment with a safe default."""
    value = os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
    return str(value).strip() or DEFAULT_OLLAMA_BASE_URL


def _get_ollama_model() -> str:
    return str(os.environ.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL


def is_local_ollama(base_url: Optional[str] = None) -> bool:
    """Return ``True`` when ``OLLAMA_BASE_URL`` resolves to a loopback host.

    The check is permissive: malformed URLs degrade to ``False`` so we never
    accidentally flood a remote service with warmup requests.
    """
    url = base_url if base_url is not None else _get_ollama_base_url()
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname in WARMUP_LOCAL_HOSTNAMES


def should_render_warmup_button(
    ui_config: Optional[Dict[str, Any]],
    *,
    base_url: Optional[str] = None,
) -> bool:
    """Decide whether the warmup button is visible to the BA.

    BL-55 contract: render when ``ui.debug_mode`` is true OR when
    ``OLLAMA_BASE_URL`` points at localhost. Anywhere else (remote pilot,
    cloud deployment) the button stays hidden.
    """
    if _get_debug_mode(ui_config):
        return True
    return is_local_ollama(base_url)


def _default_post_factory() -> Optional[Callable[..., Any]]:
    """Return ``requests.post`` if requests is importable, else ``None``."""
    try:
        import requests  # type: ignore
    except ImportError:  # pragma: no cover - requests ships in requirements.txt
        return None
    return requests.post


def _build_warmup_payload(model: str) -> Dict[str, Any]:
    """BL-55 warmup payload — fixed prompt, no PII can sneak in."""
    return {
        "model": model,
        "prompt": WARMUP_PROMPT,
        "keep_alive": WARMUP_KEEP_ALIVE,
    }


def trigger_warmup(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = WARMUP_TIMEOUT_SECONDS,
    post: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Send a single warmup request to ``/api/generate`` and report the outcome.

    Returns a dict with ``ok``/``status``/``error``/``url`` keys. Errors are
    captured rather than raised so the caller can render a polite Streamlit
    message instead of dumping a traceback into the UI.
    """
    resolved_url = (base_url or _get_ollama_base_url()).rstrip("/")
    resolved_model = model or _get_ollama_model()
    endpoint = f"{resolved_url}/api/generate"
    payload = _build_warmup_payload(resolved_model)

    post_callable = post or _default_post_factory()
    if post_callable is None:
        return {
            "ok": False,
            "status": "no_requests",
            "error": "Python пакет requests недоступен — warmup невозможен.",
            "url": endpoint,
        }

    try:
        response = post_callable(endpoint, json=payload, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - failure must never break the UI
        logger.warning(
            "ollama_warmup_failed url=%s error_type=%s",
            endpoint,
            type(exc).__name__,
        )
        return {
            "ok": False,
            "status": "exception",
            "error": str(exc) or type(exc).__name__,
            "url": endpoint,
        }

    status_code = getattr(response, "status_code", None)
    ok = bool(getattr(response, "ok", status_code == 200))
    return {
        "ok": ok,
        "status": status_code,
        "error": None if ok else f"HTTP {status_code}",
        "url": endpoint,
    }


def _run_warmup_in_thread(
    *,
    base_url: Optional[str],
    model: Optional[str],
    post: Optional[Callable[..., Any]],
    result_holder: Dict[str, Any],
) -> threading.Thread:
    """Run :func:`trigger_warmup` in a daemon thread so the UI stays responsive."""

    def _target() -> None:
        result_holder.update(trigger_warmup(base_url=base_url, model=model, post=post))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    return thread


def render_warmup_button(
    ui_config: Optional[Dict[str, Any]] = None,
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    post: Optional[Callable[..., Any]] = None,
    background: bool = True,
) -> Optional[Dict[str, Any]]:
    """Render the «🔥 Прогреть модель» button in the sidebar.

    Returns the warmup result dict when the button was clicked, ``None`` when
    the button is hidden by config or not clicked yet. ``post`` and ``background``
    are wired through for tests — production code always calls ``requests.post``
    in a daemon thread so the Streamlit thread is never blocked for 60–90 sec.
    """
    if not should_render_warmup_button(ui_config, base_url=base_url):
        return None

    clicked = st.button(
        LABELS["sidebar_warmup_button"],
        help=LABELS["sidebar_warmup_help"],
        key="sidebar_warmup_button",
    )
    if not clicked:
        return None

    spinner_ctx = st.spinner(LABELS["sidebar_warmup_in_progress"])
    with spinner_ctx:
        if background:
            holder: Dict[str, Any] = {}
            thread = _run_warmup_in_thread(
                base_url=base_url,
                model=model,
                post=post,
                result_holder=holder,
            )
            thread.join(timeout=WARMUP_TIMEOUT_SECONDS + 5)
            if thread.is_alive():
                result = {
                    "ok": False,
                    "status": "timeout",
                    "error": "warmup join timeout",
                    "url": (base_url or _get_ollama_base_url()).rstrip("/")
                    + "/api/generate",
                }
            else:
                result = holder
        else:
            result = trigger_warmup(base_url=base_url, model=model, post=post)

    if result.get("ok"):
        st.success(LABELS["sidebar_warmup_success"])
    else:
        st.error(LABELS["sidebar_warmup_error"])
    return result
