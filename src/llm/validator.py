"""LLM response JSON extraction and validation.

This module provides functions for extracting JSON from LLM responses
and validating them against the classification schema defined in
``prompts/system_classifier_v1.0.md``.

Validation rules:
- classification must be one of: Да, Нет, Частично, НД
- reasoning must be a non-empty string
- citations must be a list; required for non-НД classifications
- confidence must be a float in [0.0, 1.0]
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

_VALID_CATEGORIES = {"Да", "Нет", "Частично", "НД"}


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


def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate LLM classification response against schema.
    
    Args:
        payload: Dict containing classification result fields.
        
    Returns:
        Validated payload with normalized types.
        
    Raises:
        ValueError: If payload fails validation rules.
    """
    classification = payload.get("classification")
    if classification not in _VALID_CATEGORIES:
        raise ValueError(f"Invalid classification value: {classification!r}")
    
    if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
        raise ValueError("Missing or empty 'reasoning'")
    
    citations = payload.get("citations", []) or []
    if not isinstance(citations, list):
        raise ValueError("'citations' must be a list")
    
    if classification != "НД" and not citations:
        raise ValueError("'citations' must contain at least one entry for non-НД classifications")
    
    confidence = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("'confidence' must be a float") from exc
    
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("'confidence' must be within [0.0, 1.0]")
    
    payload["confidence"] = confidence
    payload["requires_ba_review"] = bool(payload.get("requires_ba_review", confidence < 0.75))
    payload["recommendations"] = str(payload.get("recommendations", "") or "")
    payload["citations"] = citations
    
    return payload
