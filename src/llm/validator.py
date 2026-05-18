"""LLM response JSON extraction and validation.

This module provides functions for extracting JSON from LLM responses and
validating them against the classification schema defined in
``prompts/system_classifier_v1.0.md``.

BL-11 also uses this module for the multi-hop reflection schema from
``prompts/system_rag_reflection_v1.0.md``:
``{"sufficient": boolean, "follow_up": string | null, "confidence": float}``.

Validation rules:
- ``classification`` must be one of: ``Да``, ``Нет``, ``Частично``, ``НД``.
- ``reasoning`` must be a non-empty string.
- ``citations`` must be a list; at least one entry is required for any non-``НД``
  classification (mandatory citation rule from the system prompt).
- ``confidence`` must be a float in ``[0.0, 1.0]``.

A strict Pydantic model is preferred when ``pydantic`` is installed. If it is
not available, a manual fallback enforces the same rules so that the pipeline
still runs in slim environments (e.g. minimal CI images).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

_VALID_CATEGORIES = {"Да", "Нет", "Частично", "НД"}


try:  # Pydantic v2 is the project pin (see requirements.txt).
    from pydantic import (
        BaseModel,
        ConfigDict,
        Field,
        StrictBool,
        ValidationError,
        field_validator,
    )

    _PYDANTIC_AVAILABLE = True

    class Citation(BaseModel):
        """A single citation from the retrieved context."""

        model_config = ConfigDict(extra="ignore")

        source: str = Field(..., description="Source filename or document id")
        section: str = Field("", description="Section / page label")
        quote: str = Field("", description="Exact quote from the context")

        @field_validator("source")
        @classmethod
        def _source_not_blank(cls, value: str) -> str:
            if not value or not value.strip():
                raise ValueError("citation.source must not be empty")
            return value

    class ClassificationPayload(BaseModel):
        """Strict schema for the LLM classification response."""

        model_config = ConfigDict(extra="ignore")

        requirement_id: str = ""
        requirement_text: str = ""
        classification: str
        confidence: float = 0.0
        reasoning: str
        citations: List[Citation] = Field(default_factory=list)
        requires_ba_review: bool = False
        recommendations: str = ""

        @field_validator("classification")
        @classmethod
        def _validate_classification(cls, value: str) -> str:
            if value not in _VALID_CATEGORIES:
                raise ValueError(
                    f"Invalid classification value: {value!r}. "
                    f"Expected one of {sorted(_VALID_CATEGORIES)}."
                )
            return value

        @field_validator("reasoning")
        @classmethod
        def _validate_reasoning(cls, value: str) -> str:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("'reasoning' must be a non-empty string")
            return value

        @field_validator("confidence")
        @classmethod
        def _validate_confidence(cls, value: float) -> float:
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError("'confidence' must be within [0.0, 1.0]")
            return float(value)

    class ReflectionPayload(BaseModel):
        """Strict schema for the multi-hop reflection judge response."""

        model_config = ConfigDict(extra="ignore")

        sufficient: StrictBool
        follow_up: Optional[str] = None
        confidence: float

        @field_validator("follow_up", mode="before")
        @classmethod
        def _normalise_follow_up(cls, value: Any) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        @field_validator("confidence")
        @classmethod
        def _validate_reflection_confidence(cls, value: float) -> float:
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError("'confidence' must be within [0.0, 1.0]")
            return float(value)

except ImportError:  # pragma: no cover - exercised only when pydantic is absent
    _PYDANTIC_AVAILABLE = False
    Citation = None  # type: ignore[assignment]
    ClassificationPayload = None  # type: ignore[assignment]
    ReflectionPayload = None  # type: ignore[assignment]
    ValidationError = Exception  # type: ignore[assignment]


def extract_json(payload: str) -> Dict[str, Any]:
    """Parse the first JSON object found in ``payload``.

    Args:
        payload: Raw LLM response string that may contain JSON.

    Returns:
        Parsed JSON as dict.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    if not payload:
        raise ValueError("Empty LLM response")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(payload[start : end + 1])


def _validate_with_pydantic(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        model = ClassificationPayload(**payload)  # type: ignore[misc]
    except ValidationError as exc:
        raise ValueError(f"LLM payload failed schema validation: {exc}") from exc

    data = model.model_dump()
    if data["classification"] != "НД" and not data["citations"]:
        raise ValueError(
            "'citations' must contain at least one entry for non-НД classifications"
        )
    # Normalise auto-review flag: BA review is mandatory below the prompt threshold.
    data["requires_ba_review"] = bool(
        payload.get("requires_ba_review", data["confidence"] < 0.75)
    )
    return data


def _validate_manually(payload: Dict[str, Any]) -> Dict[str, Any]:
    classification = payload.get("classification")
    if classification not in _VALID_CATEGORIES:
        raise ValueError(f"Invalid classification value: {classification!r}")

    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("Missing or empty 'reasoning'")

    citations = payload.get("citations", []) or []
    if not isinstance(citations, list):
        raise ValueError("'citations' must be a list")

    if classification != "НД" and not citations:
        raise ValueError(
            "'citations' must contain at least one entry for non-НД classifications"
        )

    confidence = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("'confidence' must be a float") from exc

    if not 0.0 <= confidence <= 1.0:
        raise ValueError("'confidence' must be within [0.0, 1.0]")

    payload["confidence"] = confidence
    payload["requires_ba_review"] = bool(
        payload.get("requires_ba_review", confidence < 0.75)
    )
    payload["recommendations"] = str(payload.get("recommendations", "") or "")
    payload["citations"] = citations
    return payload


def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an LLM classification response against the schema.

    Args:
        payload: Dict containing classification result fields.

    Returns:
        A new dict with normalised types (matches the schema in
        ``prompts/system_classifier_v1.0.md``).

    Raises:
        ValueError: If the payload fails validation rules.
    """
    if _PYDANTIC_AVAILABLE:
        return _validate_with_pydantic(payload)
    return _validate_manually(payload)


def _validate_reflection_with_pydantic(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        model = ReflectionPayload(**payload)  # type: ignore[misc]
    except ValidationError as exc:
        raise ValueError(f"Reflection payload failed schema validation: {exc}") from exc
    return model.model_dump()


def _validate_reflection_manually(payload: Dict[str, Any]) -> Dict[str, Any]:
    sufficient = payload.get("sufficient")
    if not isinstance(sufficient, bool):
        raise ValueError("'sufficient' must be a boolean")

    follow_up = payload.get("follow_up")
    if follow_up is not None:
        follow_up = str(follow_up).strip() or None

    confidence = payload.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("'confidence' must be a float") from exc
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("'confidence' must be within [0.0, 1.0]")

    return {
        "sufficient": sufficient,
        "follow_up": follow_up,
        "confidence": confidence,
    }


def validate_reflection_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a multi-hop reflection response.

    The reflection judge must return exactly the contract described in
    ``prompts/system_rag_reflection_v1.0.md``:
    ``{"sufficient": bool, "follow_up": str | null, "confidence": float}``.
    Unknown keys are ignored; missing or malformed required keys raise
    ``ValueError`` so callers can gracefully fall back to the last context.
    """
    if _PYDANTIC_AVAILABLE:
        return _validate_reflection_with_pydantic(payload)
    return _validate_reflection_manually(payload)
