"""LLM client with provider fallback, masking and strict JSON validation.

The client loads provider settings from ``configs/llm_config.yaml`` and masking
regexes from ``configs/masking_rules.yaml``. It tries providers in priority
order (DeepSeek → GigaChat by default) and returns a validated JSON payload
that matches the schema defined in ``prompts/system_classifier_v1.0.md``.

Network policy (per ADR-001 and issues #39 / #45):
- Per-call HTTP timeout: 30 seconds.
- Retry policy per provider: up to 3 attempts with a fixed exponential
  backoff schedule of **5s → 15s → 45s** for retriable errors (HTTP 5xx,
  HTTP 429, ``ConnectionError``, ``Timeout``). The schedule is the wait
  *before* each retry, so attempt 1 → 5s → attempt 2 → 15s → attempt 3 → 45s.
- LLM calls are issued **sequentially per requirement** (no parallelisation;
  see CONCEPT v2 ADR-001).
- Non-retriable failures (invalid JSON, schema violations, auth errors) trip
  the next provider in the fallback chain immediately.

For environments without API keys, a ``stub`` provider produces a deterministic
``НД`` response so the pipeline can be exercised end-to-end in tests.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import yaml

from src.llm.masking import mask_text, mask_context_chunks  # noqa: F401 - re-export
from src.llm.prompt_loader import (
    PromptNotFoundError,
    load_prompt_from_path,
)
from src.llm.validator import extract_json, validate_payload  # noqa: F401 - re-export

logger = logging.getLogger(__name__)

DEFAULT_LLM_CONFIG_PATH = "configs/llm_config.yaml"
DEFAULT_EMBEDDING_CONFIG_PATH = "configs/embedding_config.yaml"
DEFAULT_MASKING_CONFIG_PATH = "configs/masking_rules.yaml"
DEFAULT_PROMPT_PATH = "prompts/system_classifier_v1.0.md"
HTTP_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_ATTEMPTS = 3
RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# --- BL-22: temperature lock (issue #87) --------------------------------------
# Centralised decoding parameters enforced on every provider call. Per-prompt
# overrides are forbidden — `LLMClient` merges these onto the provider config
# only when a `decoding:` block is present in `configs/llm_config.yaml`, so the
# legacy config that ships without the block keeps its previous behaviour.
DECODING_PARAM_KEYS: tuple[str, ...] = ("temperature", "top_p", "seed", "max_tokens")

# --- BL-03: STRICT_MODE deterministic fallback (issue #87) --------------------
# Returned by `classify_requirement` when the retriever yielded no chunks or
# every chunk scored below `strict_min_score`. The LLM is **not** called.
STRICT_MODE_REASONING = (
    "STRICT_MODE: релевантного контекста в базе знаний не найдено. "
    "Требование помечено как НД без обращения к LLM (защита от галлюцинаций R-01)."
)
STRICT_MODE_RECOMMENDATIONS = (
    "Уточните формулировку требования или пополните knowledge_base/ "
    "соответствующими источниками; после переиндексации повторите запуск."
)

# Ordered fallback chain for free-text RAG generation (issue #73).
# 1) GigaChat (OAuth2)  →  2) OpenRouter (free models)  →  3) Ollama (local)
RAG_FALLBACK_CHAIN: tuple[str, ...] = ("gigachat", "openrouter", "ollama")
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-r1:free"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
# Fixed exponential backoff schedule (seconds), per issue #45 MUST 3.
# index = attempt - 1; clipped to last value if more attempts are configured.
BACKOFF_SCHEDULE_SECONDS: tuple[int, ...] = (5, 15, 45)


def _backoff_delay(attempt: int) -> int:
    """Return the seconds to wait before retry attempt ``attempt`` (1-based).

    For attempts beyond the schedule the final delay (45s) is reused so the
    behaviour stays deterministic when ``retry_attempts`` is misconfigured.
    """
    if attempt <= 0:
        return 0
    idx = min(attempt - 1, len(BACKOFF_SCHEDULE_SECONDS) - 1)
    return BACKOFF_SCHEDULE_SECONDS[idx]


class LLMError(RuntimeError):
    """Raised when every configured provider has failed."""


class RetriableProviderError(RuntimeError):
    """Network / rate-limit failure that should trigger a retry."""


@dataclass
class ClassificationResult:
    """Validated LLM classification response."""

    classification: str
    reasoning: str
    citations: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    requires_ba_review: bool = False
    recommendations: str = ""
    provider: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification,
            "reasoning": self.reasoning,
            "citations": self.citations,
            "confidence": self.confidence,
            "requires_ba_review": self.requires_ba_review,
            "recommendations": self.recommendations,
            "provider": self.provider,
        }


ProviderCall = Callable[[str, str, Dict[str, Any]], str]
RagProviderCall = Callable[[str, str, Dict[str, Any]], str]


def _load_llm_config(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("Config file not found: %s", file_path)
        return {}
    try:
        return yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return {}


def _resolve_env(*candidates: Optional[str]) -> Optional[str]:
    for name in candidates:
        if not name:
            continue
        value = os.environ.get(name)
        if value:
            return value
    return None


def _http_post_with_retries(
    url: str,
    *,
    headers: Dict[str, str],
    json_payload: Dict[str, Any],
    timeout: int = HTTP_TIMEOUT_SECONDS,
) -> Any:
    """Issue an HTTP POST and translate transport errors into our taxonomy.

    Returns the parsed JSON body on success. Raises
    :class:`RetriableProviderError` for HTTP 5xx, HTTP 429, ``ConnectionError``
    and timeouts; other errors propagate as is so the caller can decide to skip
    to the next provider immediately.
    """
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover - guarded by requirements.txt
        raise RuntimeError("`requests` library is required for LLM providers") from exc

    try:
        response = requests.post(url, headers=headers, json=json_payload, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RetriableProviderError(f"Connection error to {url}: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        raise RetriableProviderError(f"Timeout calling {url}: {exc}") from exc

    if response.status_code in RETRIABLE_STATUS_CODES:
        raise RetriableProviderError(
            f"Retriable HTTP {response.status_code} from {url}: {response.text[:200]}"
        )
    response.raise_for_status()
    return response.json()


class LLMClient:
    """Multi-provider LLM client with masking, retries and validation."""

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        masking_config_path: str = DEFAULT_MASKING_CONFIG_PATH,
        prompt_path: str = DEFAULT_PROMPT_PATH,
        provider_callers: Optional[Dict[str, ProviderCall]] = None,
        embedding_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = llm_config or {}
        self.embedding_config = embedding_config or {}
        self.masking_config_path = masking_config_path
        self.system_prompt = self._load_system_prompt(prompt_path)
        self.provider_callers: Dict[str, ProviderCall] = {
            "deepseek": _call_deepseek,
            "gigachat": _call_gigachat,
            "stub": _call_stub,
        }
        if provider_callers:
            self.provider_callers.update(provider_callers)

    @classmethod
    def from_config(
        cls,
        config_path: str = DEFAULT_LLM_CONFIG_PATH,
        masking_config_path: str = DEFAULT_MASKING_CONFIG_PATH,
        prompt_path: str = DEFAULT_PROMPT_PATH,
        provider_callers: Optional[Dict[str, ProviderCall]] = None,
        embedding_config_path: str = DEFAULT_EMBEDDING_CONFIG_PATH,
    ) -> "LLMClient":
        return cls(
            llm_config=_load_llm_config(config_path),
            masking_config_path=masking_config_path,
            prompt_path=prompt_path,
            provider_callers=provider_callers,
            embedding_config=_load_llm_config(embedding_config_path),
        )

    @staticmethod
    def _load_system_prompt(prompt_path: str) -> str:
        """Load the classifier system prompt via the prompt library (BL-08).

        Delegates to :func:`src.llm.prompt_loader.load_prompt_from_path` so the
        SHA-256 of the loaded prompt is recorded in the audit log together
        with name/version parsed from the filename. The minimal hardcoded
        fallback stays in place for broken installs where the file is
        absent — it is **not** an editing surface.
        """
        try:
            return load_prompt_from_path(prompt_path).content
        except PromptNotFoundError:
            logger.warning(
                "System prompt not found at %s; using minimal fallback.", prompt_path
            )
            return (
                "You are a classifier. Respond ONLY with JSON containing keys: "
                "requirement_id, requirement_text, classification (Да|Частично|Нет|НД), "
                "confidence, reasoning, citations, requires_ba_review, recommendations."
            )

    def mask_text(self, text: str) -> str:
        return mask_text(text, config_path=self.masking_config_path)

    @property
    def use_test_data_mode(self) -> bool:
        return bool(self.config.get("use_test_data_mode", False))

    @property
    def mask_rag_context_enabled(self) -> bool:
        """BL-04: read ``mask_rag_context`` from llm or embedding config.

        Looked up in both files for safety — the canonical flag lives in
        ``configs/embedding_config.yaml`` but a mirror in ``llm_config.yaml``
        is allowed so ``LLMClient`` does not have to parse the embedding YAML.
        Defaults to ``True`` (data residency by default).
        """
        if "mask_rag_context" in self.config:
            return bool(self.config["mask_rag_context"])
        if "mask_rag_context" in self.embedding_config:
            return bool(self.embedding_config["mask_rag_context"])
        return True

    @property
    def strict_rag_mode(self) -> bool:
        """BL-03: STRICT_MODE flag from ``configs/embedding_config.yaml``."""
        return bool(self.embedding_config.get("strict_rag_mode", False))

    @property
    def strict_min_score(self) -> float:
        """BL-03: minimum RRF-fusion score for a chunk to count as relevant."""
        try:
            return float(self.embedding_config.get("strict_min_score", 0.30))
        except (TypeError, ValueError):
            return 0.30

    def _decoding_params(self) -> Dict[str, Any]:
        """BL-22: return decoding params only when the ``decoding:`` block is set.

        Returning an empty dict when the block is absent keeps the legacy
        ``test_generate_rag_response_passes_provider_config`` assertion intact
        (it compares the captured cfg by exact equality).
        """
        decoding = self.config.get("decoding")
        if not isinstance(decoding, dict):
            return {}
        params: Dict[str, Any] = {}
        for key in DECODING_PARAM_KEYS:
            if key in decoding and decoding[key] is not None:
                params[key] = decoding[key]
        return params

    def _merge_decoding(self, provider_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of ``provider_cfg`` with decoding params merged in.

        Decoding params override per-provider settings (BL-22: prompts and
        provider overrides cannot beat the centralised lock). A no-op when the
        ``decoding:`` block is not configured.
        """
        decoding = self._decoding_params()
        if not decoding:
            return provider_cfg
        merged = dict(provider_cfg)
        merged.update(decoding)
        return merged

    @staticmethod
    def _chunk_score(chunk: Dict[str, Any]) -> Optional[float]:
        """Best-effort numeric score extraction from a retriever chunk.

        HybridRetriever uses ``score`` (RRF), ChromaRetriever uses
        ``similarity`` (cosine). Returns ``None`` when the chunk shape is
        unexpected so the strict-mode guard can fall back to ``len() > 0``.
        """
        for key in ("score", "similarity", "rrf_score"):
            value = chunk.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    def _strict_mode_blocks_call(
        self, chunks: Sequence[Dict[str, Any]]
    ) -> Optional[str]:
        """BL-03: return a reason string if STRICT_MODE should skip the LLM call."""
        if not self.strict_rag_mode:
            return None
        if not chunks:
            return "empty_context"
        threshold = self.strict_min_score
        scores = [self._chunk_score(c) for c in chunks]
        numeric = [s for s in scores if s is not None]
        if numeric and max(numeric) < threshold:
            return f"low_score(max={max(numeric):.3f} < {threshold:.3f})"
        return None

    def _strict_mode_result(
        self, reason: str, requirement_id: Optional[str]
    ) -> "ClassificationResult":
        """Deterministic ``НД`` fallback used when STRICT_MODE blocks the call."""
        logger.info(
            "strict_mode=true skipped LLM call: %s",
            reason,
            extra={"requirement_id": requirement_id} if requirement_id else None,
        )
        return ClassificationResult(
            classification="НД",
            reasoning=f"{STRICT_MODE_REASONING} (причина: {reason})",
            citations=[],
            confidence=0.0,
            requires_ba_review=True,
            recommendations=STRICT_MODE_RECOMMENDATIONS,
            provider="strict_mode",
            raw={"strict_mode": True, "reason": reason},
        )

    def _ordered_providers(self) -> List[tuple[str, Dict[str, Any]]]:
        providers = self.config.get("providers", {}) or {}
        active = self.config.get("active_provider")
        ordering = self.config.get("fallback_providers")
        if not ordering:
            ordering = sorted(providers.keys(), key=lambda name: providers[name].get("priority", 99))
        if active and active in providers:
            ordering = [active] + [name for name in ordering if name != active]
        result: List[tuple[str, Dict[str, Any]]] = []
        for name in ordering:
            if name in providers:
                result.append((name, providers[name]))
        return result

    def generate_rag_response(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        mask: Optional[bool] = None,
    ) -> str:
        """Generate a free-text RAG answer with the GigaChat→OpenRouter→Ollama chain.

        Unlike :meth:`classify_requirement`, this method:

        - Does **not** force ``response_format: json_object``; providers return
          unconstrained text suitable for the KB Q&A UI.
        - Does **not** run schema validation on the response.
        - Uses a dedicated fallback chain (``RAG_FALLBACK_CHAIN``) so the
          classification pipeline (DeepSeek→GigaChat) and the RAG pipeline can
          evolve independently.

        BL-04 (issue #87): when ``mask`` is left ``None`` the
        ``mask_rag_context`` flag from ``configs/embedding_config.yaml``
        (mirrored in ``configs/llm_config.yaml``) is consulted; defaults to
        ``True``. Pass ``mask=False`` only in offline ``evaluate_rag.py``
        runs with synthetic data.

        Errors from each provider (HTTP 4xx/5xx, SSL, timeouts, refused
        connections) are logged at ``WARNING`` and trigger fallback to the next
        provider. ``LLMError`` is raised only when every provider has failed.
        """
        if not user_prompt or not user_prompt.strip():
            raise ValueError("user_prompt must not be empty")

        should_mask = self.mask_rag_context_enabled if mask is None else bool(mask)
        if should_mask:
            user_prompt = self.mask_text(user_prompt)

        providers = self.config.get("providers", {}) or {}
        rag_callers: Dict[str, RagProviderCall] = {
            "gigachat": _call_gigachat_rag,
            "openrouter": _call_openrouter_rag,
            "ollama": _call_ollama_rag,
        }

        last_error: Optional[Exception] = None
        for name in RAG_FALLBACK_CHAIN:
            caller = rag_callers.get(name)
            if caller is None:
                continue
            provider_cfg = self._merge_decoding(providers.get(name) or {})
            try:
                return caller(system_prompt, user_prompt, provider_cfg)
            except Exception as exc:  # noqa: BLE001 - fall through to next provider
                last_error = exc
                logger.warning(
                    "RAG provider %s failed (%s); trying next provider.",
                    name,
                    exc,
                )
                continue

        raise LLMError(
            "All RAG providers failed (GigaChat → OpenRouter → Ollama). "
            f"Last error: {last_error}"
        )

    def classify_requirement(
        self,
        req_text: str,
        context_chunks: Sequence[Dict[str, Any]],
        requirement_id: Optional[str] = None,
    ) -> ClassificationResult:
        """Run masking → provider fallback → JSON validation for one requirement.

        Masking is always applied to the requirement text and context chunks
        BEFORE the HTTP request is built, regardless of the provider. When
        ``use_test_data_mode`` is enabled the masking step is forced and any
        future opt-out is ignored, per the data residency requirements in
        ``docs/CONCEPT.md``.
        """
        if not req_text or not req_text.strip():
            raise ValueError("Requirement text must not be empty")

        # BL-03: STRICT_MODE — refuse to call the LLM when retrieval is empty
        # or every chunk scored below `strict_min_score`. This blocks the
        # CONCEPT §7 R-01 hallucination path.
        strict_reason = self._strict_mode_blocks_call(context_chunks)
        if strict_reason is not None:
            return self._strict_mode_result(strict_reason, requirement_id)

        masked_req = self.mask_text(req_text)
        masked_chunks = mask_context_chunks(
            list(context_chunks), config_path=self.masking_config_path
        )

        if self.use_test_data_mode:
            logger.debug("use_test_data_mode=true: masking enforced before LLM call")

        context_block = self._format_context(masked_chunks)
        user_message = self._build_user_message(masked_req, context_block, requirement_id)

        # BL-22: audit-trail of the locked decoding parameters (FR-08). Only
        # emitted when a `decoding:` block is present; legacy configs stay
        # silent so existing tests keep their previous log surface.
        decoding_params = self._decoding_params()
        if decoding_params:
            logger.info(
                "decoding_lock applied: %s",
                {k: decoding_params[k] for k in DECODING_PARAM_KEYS if k in decoding_params},
                extra={"requirement_id": requirement_id} if requirement_id else None,
            )

        last_error: Optional[Exception] = None
        for provider_name, provider_cfg in self._ordered_providers():
            caller = self.provider_callers.get(provider_name)
            if caller is None:
                logger.warning("No caller registered for provider %s; skipping.", provider_name)
                continue
            provider_cfg = self._merge_decoding(provider_cfg)
            retries = max(1, int(provider_cfg.get("retry_attempts", DEFAULT_RETRY_ATTEMPTS)))
            for attempt in range(1, retries + 1):
                try:
                    raw_response = caller(self.system_prompt, user_message, provider_cfg)
                    payload = extract_json(raw_response)
                    payload = validate_payload(payload)
                    return ClassificationResult(
                        classification=payload["classification"],
                        reasoning=payload["reasoning"],
                        citations=payload.get("citations", []),
                        confidence=payload.get("confidence", 0.0),
                        requires_ba_review=payload.get("requires_ba_review", False),
                        recommendations=payload.get("recommendations", ""),
                        provider=provider_name,
                        raw=payload,
                    )
                except RetriableProviderError as exc:
                    last_error = exc
                    logger.warning(
                        "Retriable failure on provider %s (attempt %d/%d): %s",
                        provider_name,
                        attempt,
                        retries,
                        exc,
                    )
                    if attempt < retries:
                        time.sleep(_backoff_delay(attempt))
                        continue
                    break  # exhaust retries → move to next provider
                except Exception as exc:  # noqa: BLE001 - try the next provider
                    last_error = exc
                    logger.warning(
                        "Non-retriable failure on provider %s: %s (skipping retries)",
                        provider_name,
                        exc,
                    )
                    break
        raise LLMError(f"All providers failed; last error: {last_error}")

    # ------------------------------------------------------------- formatting --
    @staticmethod
    def _format_context(chunks: Sequence[Dict[str, Any]]) -> str:
        if not chunks:
            return "(контекст отсутствует)"
        lines: List[str] = []
        for chunk in chunks:
            source = chunk.get("source", "unknown")
            page = chunk.get("page") or (chunk.get("metadata") or {}).get("section", "")
            header = f"[{source}{(' — ' + page) if page else ''}]"
            lines.append(f"{header}\n{chunk.get('text', '').strip()}")
        return "\n\n".join(lines)

    def _build_user_message(
        self, requirement_text: str, context_block: str, requirement_id: Optional[str]
    ) -> str:
        req_id_attr = f' id="{requirement_id}"' if requirement_id else ""
        return (
            f"<requirement{req_id_attr}>{requirement_text}</requirement>\n"
            f"<context>\n{context_block}\n</context>\n"
            "Respond with the JSON object only."
        )


# -------------------------------------------------------- provider call stubs --
def _call_stub(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    """Offline stub used when no real provider is reachable."""
    payload = {
        "requirement_id": "",
        "requirement_text": "",
        "classification": "НД",
        "confidence": 0.0,
        "reasoning": (
            "Заглушка LLM-провайдера: реальные провайдеры не настроены, "
            "поэтому требование помечено как НД для ручной проверки."
        ),
        "citations": [],
        "requires_ba_review": True,
        "recommendations": "Настройте API-ключи провайдеров (DeepSeek, GigaChat).",
    }
    return json.dumps(payload, ensure_ascii=False)


def _decoding_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Pick up decoding params (top_p / seed / max_tokens) from ``config``.

    BL-22: ``temperature`` is forwarded separately by every caller, but the
    remaining locked parameters are optional in the wire payload — we only
    include them when present so legacy provider configs (which never set
    them) keep their previous request shape.
    """
    overrides: Dict[str, Any] = {}
    if "top_p" in config and config["top_p"] is not None:
        overrides["top_p"] = float(config["top_p"])
    if "seed" in config and config["seed"] is not None:
        overrides["seed"] = int(config["seed"])
    if "max_tokens" in config and config["max_tokens"] is not None:
        overrides["max_tokens"] = int(config["max_tokens"])
    return overrides


def _call_deepseek(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    api_key = _resolve_env(config.get("api_key_env"))
    if not api_key:
        raise RuntimeError("DeepSeek API key is not configured")
    payload: Dict[str, Any] = {
        "model": config.get("model", "deepseek-chat"),
        "temperature": config.get("temperature", 0.1),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
    }
    payload.update(_decoding_overrides(config))
    data = _http_post_with_retries(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json_payload=payload,
    )
    return data["choices"][0]["message"]["content"]


def _call_gigachat(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    credentials = _resolve_env(config.get("credentials_env"))
    if not credentials:
        raise RuntimeError("GigaChat credentials are not configured")
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for GigaChat") from exc

    try:
        token_resp = requests.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {credentials}",
                "RqUID": "00000000-0000-0000-0000-000000000000",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": "GIGACHAT_API_PERS"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError as exc:
        raise RetriableProviderError(f"GigaChat auth connection error: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        raise RetriableProviderError(f"GigaChat auth timeout: {exc}") from exc
    if token_resp.status_code in RETRIABLE_STATUS_CODES:
        raise RetriableProviderError(f"GigaChat auth HTTP {token_resp.status_code}")
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    payload: Dict[str, Any] = {
        "model": config.get("model", "GigaChat-Pro"),
        "temperature": config.get("temperature", 0.1),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    payload.update(_decoding_overrides(config))
    data = _http_post_with_retries(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json_payload=payload,
    )
    return data["choices"][0]["message"]["content"]


# ----------------------------------------------------- RAG provider callers --
def _gigachat_access_token(config: Dict[str, Any]) -> str:
    """Fetch a fresh OAuth2 access token from GigaChat.

    Reads credentials from either:
    - ``config['credentials_env']`` (a single env var containing the prebuilt
      ``Basic`` payload, kept for backwards compatibility with the existing
      classification provider), or
    - ``GIGACHAT_CLIENT_ID`` + ``GIGACHAT_CLIENT_SECRET`` (per issue #73 —
      preferred so secrets are not pre-encoded in the environment).
    """
    try:
        import base64
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover - guaranteed by requirements.txt
        raise RuntimeError("`requests` library is required for GigaChat") from exc

    credentials = _resolve_env(config.get("credentials_env"))
    if not credentials:
        client_id = _resolve_env("GIGACHAT_CLIENT_ID", config.get("client_id_env"))
        client_secret = _resolve_env(
            "GIGACHAT_CLIENT_SECRET", config.get("client_secret_env")
        )
        if not client_id or not client_secret:
            raise RuntimeError(
                "GigaChat OAuth2 credentials are not configured "
                "(set GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET, or "
                "GIGACHAT_AUTH in your .env)."
            )
        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("ascii")

    scope = str(config.get("scope", "GIGACHAT_API_PERS"))
    rq_uid = str(config.get("rq_uid", "00000000-0000-0000-0000-000000000000"))
    verify_ssl = bool(config.get("verify_ssl", True))

    try:
        token_resp = requests.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {credentials}",
                "RqUID": rq_uid,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": scope},
            timeout=HTTP_TIMEOUT_SECONDS,
            verify=verify_ssl,
        )
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(f"GigaChat SSL error: {exc}") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"GigaChat auth connection error: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"GigaChat auth timeout: {exc}") from exc

    if token_resp.status_code >= 400:
        raise RuntimeError(
            f"GigaChat auth returned HTTP {token_resp.status_code}: "
            f"{token_resp.text[:300]}"
        )
    try:
        return str(token_resp.json()["access_token"])
    except (ValueError, KeyError) as exc:
        raise RuntimeError(f"GigaChat auth response missing access_token: {exc}") from exc


def _call_gigachat_rag(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    """GigaChat (priority 1 in the RAG fallback chain).

    Authenticates with OAuth2 (``client_id`` + ``client_secret``) and calls the
    Sberbank chat-completions endpoint. SSL verification can be disabled
    per-provider via ``verify_ssl: false`` in ``configs/llm_config.yaml`` for
    corporate proxies — there is no global override.
    """
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for GigaChat") from exc

    access_token = _gigachat_access_token(config)
    verify_ssl = bool(config.get("verify_ssl", True))
    body: Dict[str, Any] = {
        "model": config.get("model", "GigaChat-Pro"),
        "temperature": float(config.get("temperature", 0.1)),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    body.update(_decoding_overrides(config))
    try:
        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=HTTP_TIMEOUT_SECONDS,
            verify=verify_ssl,
        )
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(f"GigaChat SSL error: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"GigaChat request failed: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(
            f"GigaChat returned HTTP {response.status_code}: {response.text[:300]}"
        )
    try:
        data = response.json()
        return str(data["choices"][0]["message"]["content"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected GigaChat response shape: {exc}") from exc


def _call_openrouter_rag(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    """OpenRouter (priority 2 in the RAG fallback chain).

    Uses the OpenAI-compatible ``/api/v1/chat/completions`` endpoint. The API
    key is read from ``OPENROUTER_API_KEY`` by default; the default model is a
    free tier (``deepseek/deepseek-r1:free``) so the chain works without a
    paid subscription.
    """
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for OpenRouter") from exc

    api_key = _resolve_env("OPENROUTER_API_KEY", config.get("api_key_env"))
    if not api_key:
        raise RuntimeError(
            "OpenRouter API key is not configured (set OPENROUTER_API_KEY in your .env)."
        )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Optional headers recommended by OpenRouter for analytics; no PII leaks.
    referer = config.get("http_referer") or os.environ.get("OPENROUTER_HTTP_REFERER")
    if referer:
        headers["HTTP-Referer"] = str(referer)
    title = config.get("x_title") or os.environ.get("OPENROUTER_X_TITLE")
    if title:
        headers["X-Title"] = str(title)

    base_url = str(config.get("base_url", "https://openrouter.ai/api/v1")).rstrip("/")
    body: Dict[str, Any] = {
        "model": config.get("model", DEFAULT_OPENROUTER_MODEL),
        "temperature": float(config.get("temperature", 0.1)),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    body.update(_decoding_overrides(config))
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=body,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.exceptions.SSLError as exc:
        raise RuntimeError(f"OpenRouter SSL error: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

    if response.status_code == 429:
        raise RetriableProviderError(
            f"OpenRouter rate-limit HTTP 429: {response.text[:300]}"
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter returned HTTP {response.status_code}: {response.text[:300]}"
        )
    try:
        data = response.json()
        return str(data["choices"][0]["message"]["content"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response shape: {exc}") from exc


def _call_ollama_rag(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    """Ollama (priority 3 — local fallback).

    Targets the OpenAI-compatible endpoint exposed by Ollama
    (``/v1/chat/completions``). The base URL and model are configurable via
    ``OLLAMA_BASE_URL`` and ``OLLAMA_MODEL`` (or the per-provider config keys).
    No API key is required.
    """
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for Ollama") from exc

    base_url = str(
        config.get("base_url")
        or os.environ.get("OLLAMA_BASE_URL")
        or DEFAULT_OLLAMA_BASE_URL
    ).rstrip("/")
    model = str(
        config.get("model") or os.environ.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    )
    body: Dict[str, Any] = {
        "model": model,
        "temperature": float(config.get("temperature", 0.1)),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    body.update(_decoding_overrides(config))
    try:
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError as exc:
        logger.warning(
            "Ollama is unreachable at %s — start it with `ollama serve` "
            "and pull the model (`ollama pull %s`).",
            base_url,
            model,
        )
        raise RuntimeError(f"Ollama connection refused at {base_url}: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
        )
    try:
        data = response.json()
        return str(data["choices"][0]["message"]["content"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Ollama response shape: {exc}") from exc
