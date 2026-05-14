"""LLM client with provider fallback, masking and strict JSON validation.

The client loads provider settings from ``configs/llm_config.yaml`` and masking
regexes from ``configs/masking_rules.yaml``. It tries providers in priority
order (Qwen → DeepSeek → GigaChat → Yandex by default) and returns a validated
JSON payload that matches the schema defined in
``prompts/system_classifier_v1.0.md``.

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

from src.llm.masking import mask_text, mask_context_chunks  # noqa: F401 - re-export for backward compatibility
from src.llm.validator import extract_json, validate_payload  # noqa: F401 - re-export for backward compatibility

logger = logging.getLogger(__name__)

DEFAULT_LLM_CONFIG_PATH = "configs/llm_config.yaml"
DEFAULT_MASKING_CONFIG_PATH = "configs/masking_rules.yaml"
DEFAULT_PROMPT_PATH = "prompts/system_classifier_v1.0.md"


class LLMError(RuntimeError):
    """Raised when every configured provider has failed."""


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


# ----------------------------------------------------------------- LLM client --
ProviderCall = Callable[[str, str, Dict[str, Any]], str]


class LLMClient:
    """Multi-provider LLM client with masking, retries and validation."""

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        masking_config_path: str = DEFAULT_MASKING_CONFIG_PATH,
        prompt_path: str = DEFAULT_PROMPT_PATH,
        provider_callers: Optional[Dict[str, ProviderCall]] = None,
    ) -> None:
        self.config = llm_config or {}
        self.masking_config_path = masking_config_path
        self.system_prompt = self._load_system_prompt(prompt_path)
        self.provider_callers: Dict[str, ProviderCall] = {
            "qwen_dashscope": _call_dashscope,
            "deepseek": _call_deepseek,
            "gigachat": _call_gigachat,
            "yandex": _call_yandex,
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
    ) -> "LLMClient":
        return cls(
            llm_config=_load_llm_config(config_path),
            masking_config_path=masking_config_path,
            prompt_path=prompt_path,
            provider_callers=provider_callers,
        )

    @staticmethod
    def _load_llm_config(path: str) -> Dict[str, Any]:
        """Load LLM configuration from YAML file."""
        file_path = Path(path)
        if not file_path.exists():
            logger.warning("Config file not found: %s", file_path)
            return {}
        try:
            return yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse %s: %s", file_path, exc)
            return {}

    @staticmethod
    def _load_system_prompt(prompt_path: str) -> str:
        path = Path(prompt_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        logger.warning("System prompt not found at %s; using minimal fallback.", path)
        return (
            "You are a classifier. Respond ONLY with JSON containing keys: "
            "requirement_id, requirement_text, classification (Да|Частично|Нет|НД), "
            "confidence, reasoning, citations, requires_ba_review, recommendations."
        )

    def mask_text(self, text: str) -> str:
        return mask_text(text, config_path=self.masking_config_path)

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

    def classify_requirement(
        self,
        req_text: str,
        context_chunks: Sequence[Dict[str, Any]],
        requirement_id: Optional[str] = None,
    ) -> ClassificationResult:
        """Run masking → provider fallback → JSON validation for one requirement.
        
        Both the requirement text and RAG context chunks are masked before
        being sent to the LLM provider to prevent data leakage.
        """
        if not req_text or not req_text.strip():
            raise ValueError("Requirement text must not be empty")

        # Mask requirement text
        masked_req = self.mask_text(req_text)
        
        # Mask context chunks to prevent sensitive data leakage
        masked_chunks = mask_context_chunks(list(context_chunks), config_path=self.masking_config_path)
        context_block = self._format_context(masked_chunks)
        
        user_message = self._build_user_message(masked_req, context_block, requirement_id)

        last_error: Optional[Exception] = None
        for provider_name, provider_cfg in self._ordered_providers():
            caller = self.provider_callers.get(provider_name)
            if caller is None:
                logger.warning("No caller registered for provider %s; skipping.", provider_name)
                continue
            retries = max(1, int(provider_cfg.get("retry_attempts", 1)))
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
                except Exception as exc:  # noqa: BLE001 - we keep trying other providers
                    last_error = exc
                    logger.warning(
                        "Provider %s failed (attempt %d/%d): %s",
                        provider_name,
                        attempt,
                        retries,
                        exc,
                    )
                    if attempt < retries:
                        time.sleep(min(2 ** (attempt - 1), 5))
        raise LLMError(f"All providers failed; last error: {last_error}")

    # ------------------------------------------------------------- formatting --
    @staticmethod
    def _format_context(chunks: Sequence[Dict[str, Any]]) -> str:
        if not chunks:
            return "(контекст отсутствует)"
        lines: List[str] = []
        for chunk in chunks:
            source = chunk.get("source", "unknown")
            section = (chunk.get("metadata") or {}).get("section", "")
            header = f"[{source}{(' — ' + section) if section else ''}]"
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
    """Offline stub used when no real provider is reachable.

    Returns a conservative ``НД`` response that still satisfies the JSON schema.
    """
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
        "recommendations": "Настройте API-ключи провайдеров (DashScope, DeepSeek, GigaChat, YandexGPT).",
    }
    return json.dumps(payload, ensure_ascii=False)


def _resolve_env(*candidates: Optional[str]) -> Optional[str]:
    for name in candidates:
        if not name:
            continue
        value = os.environ.get(name)
        if value:
            return value
    return None


def _call_dashscope(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    api_key = _resolve_env(config.get("api_key_env"))
    if not api_key:
        raise RuntimeError("DashScope API key is not configured")
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for DashScope") from exc

    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    payload = {
        "model": config.get("model", "qwen-max"),
        "temperature": config.get("temperature", 0.1),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_deepseek(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    api_key = _resolve_env(config.get("api_key_env"))
    if not api_key:
        raise RuntimeError("DeepSeek API key is not configured")
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for DeepSeek") from exc

    url = "https://api.deepseek.com/chat/completions"
    payload = {
        "model": config.get("model", "deepseek-chat"),
        "temperature": config.get("temperature", 0.1),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_gigachat(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    credentials = _resolve_env(config.get("credentials_env"))
    if not credentials:
        raise RuntimeError("GigaChat credentials are not configured")
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for GigaChat") from exc

    token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    token_resp = requests.post(
        token_url,
        headers={
            "Authorization": f"Basic {credentials}",
            "RqUID": "00000000-0000-0000-0000-000000000000",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": "GIGACHAT_API_PERS"},
        timeout=30,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    chat_resp = requests.post(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "model": config.get("model", "GigaChat-Pro"),
            "temperature": config.get("temperature", 0.1),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=60,
    )
    chat_resp.raise_for_status()
    return chat_resp.json()["choices"][0]["message"]["content"]


def _call_yandex(system_prompt: str, user_message: str, config: Dict[str, Any]) -> str:
    folder_id = _resolve_env(config.get("folder_id_env"))
    iam_token = _resolve_env(config.get("iam_token_env"))
    if not folder_id or not iam_token:
        raise RuntimeError("Yandex folder_id / IAM token are not configured")
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("`requests` library is required for YandexGPT") from exc

    payload = {
        "modelUri": f"gpt://{folder_id}/{config.get('model', 'yandexgpt-pro')}",
        "completionOptions": {"temperature": config.get("temperature", 0.1), "maxTokens": 2000},
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_message},
        ],
    }
    response = requests.post(
        "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
        headers={"Authorization": f"Bearer {iam_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["result"]["alternatives"][0]["message"]["text"]
