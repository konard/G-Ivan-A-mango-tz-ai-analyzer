"""Sanitised UI error diagnostics for generation failures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.llm.masking import mask_text


class ErrorHandler:
    """Collect and serialise masked diagnostics for UI failures."""

    def collect_error_context(
        self,
        provider: str,
        exception: BaseException,
        config: dict,
    ) -> dict:
        """Return a masked single-error context block."""
        return self._mask_mapping(
            {
                "provider": provider,
                "error_type": str(
                    config.get("error_type") or type(exception).__name__
                ),
                "message": str(exception),
                "provider_count": config.get("provider_count"),
                "run_id": config.get("run_id"),
                "timestamp": _utc_timestamp(),
            }
        )

    def generate_error_report(
        self,
        errors: list,
        query: str,
        config: dict,
    ) -> dict:
        """Build a masked report suitable for download from the UI."""
        provider_count = _provider_count(config)
        normalised_errors = [
            self._normalise_error(error, config) for error in errors
        ]
        return self._mask_mapping(
            {
                "run_id": config.get("run_id"),
                "timestamp": _utc_timestamp(),
                "query": query,
                "reason": f"Все провайдеры недоступны ({len(normalised_errors)} из {provider_count})",
                "errors": normalised_errors,
                "recommendations": _recommendations(normalised_errors),
            }
        )

    def export_to_txt(self, report: dict) -> bytes:
        """Serialise a masked report as UTF-8 text bytes."""
        lines = [
            "Clarify Engine error report",
            f"run_id: {report.get('run_id', '')}",
            f"timestamp: {report.get('timestamp', '')}",
            f"reason: {report.get('reason', '')}",
            "",
            "query:",
            str(report.get("query", "")),
            "",
            "errors:",
        ]
        for error in report.get("errors", []) or []:
            if not isinstance(error, dict):
                continue
            lines.append(
                "- provider={provider} type={error_type} message={message}".format(
                    provider=error.get("provider", ""),
                    error_type=error.get("error_type", ""),
                    message=error.get("message", ""),
                )
            )
        lines.extend(["", "recommendations:"])
        for item in report.get("recommendations", []) or []:
            lines.append(f"- {item}")
        return mask_text("\n".join(lines)).encode("utf-8")

    def _normalise_error(self, error: Any, config: dict) -> dict:
        if isinstance(error, dict):
            return self._mask_mapping(error)
        if isinstance(error, BaseException):
            return self.collect_error_context(
                str(config.get("provider") or "rag_fallback_chain"),
                error,
                config,
            )
        return self._mask_mapping(
            {
                "provider": str(config.get("provider") or "unknown"),
                "error_type": type(error).__name__,
                "message": str(error),
            }
        )

    def _mask_mapping(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._mask_mapping(sub) for key, sub in value.items()}
        if isinstance(value, list):
            return [self._mask_mapping(item) for item in value]
        if isinstance(value, str):
            return mask_text(value)
        return value


def _provider_count(config: dict) -> int:
    providers = config.get("providers")
    if isinstance(providers, dict):
        return len(providers)
    try:
        return int(config.get("provider_count") or 1)
    except (TypeError, ValueError):
        return 1


def _recommendations(errors: List[Dict[str, Any]]) -> List[str]:
    messages = " ".join(str(error.get("message", "")).lower() for error in errors)
    if "401" in messages or "auth" in messages or "token" in messages:
        return ["Проверьте API-ключи и переменные окружения провайдеров."]
    if "timeout" in messages or "connection" in messages:
        return ["Проверьте сетевую доступность провайдеров и повторите запрос."]
    if "400" in messages:
        return ["Проверьте формат запроса и ограничения выбранной модели."]
    return ["Проверьте конфигурацию провайдеров и серверные логи по run_id."]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
