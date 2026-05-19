"""BL-55 (issue #199) — contract tests for the Russian UI copy.

The tests pin the wording the BA actually sees so a casual translation pass
cannot accidentally drop the «60–90 сек» warning that BL-55 added to the
first-response UX. The warmup-button copy is co-located here so the whole
BL-55 contract is verifiable in one place.
"""

from __future__ import annotations

from src.ui.constants import LABELS


def test_spinner_llm_mentions_first_response_latency_window() -> None:
    """BL-55 DoD: spinner text must warn BAs about the 60–90 сек cold start."""
    spinner_text = LABELS["spinner_llm"]
    assert "60–90" in spinner_text, (
        "Spinner text must contain '60–90' with the en-dash so the wording "
        "matches the runbook §1 and the user guide warning."
    )
    assert "сек" in spinner_text
    # Provider chain order is part of the BL-55 contract — BAs read it to know
    # which provider answered if the UI does not echo it explicitly.
    assert "GigaChat" in spinner_text
    assert "OpenRouter" in spinner_text
    assert "Ollama" in spinner_text


def test_warmup_labels_are_present_and_non_empty() -> None:
    """BL-55: every warmup-related copy key must ship and be human-readable."""
    keys = [
        "sidebar_warmup_button",
        "sidebar_warmup_help",
        "sidebar_warmup_in_progress",
        "sidebar_warmup_success",
        "sidebar_warmup_error",
    ]
    for key in keys:
        value = LABELS.get(key)
        assert isinstance(value, str), f"LABELS[{key!r}] must be a string"
        assert value.strip(), f"LABELS[{key!r}] must not be empty"


def test_warmup_button_label_contains_fire_emoji_and_russian_text() -> None:
    """BL-55 contract: button visually distinguishes itself with 🔥."""
    label = LABELS["sidebar_warmup_button"]
    assert "🔥" in label
    assert "Прогреть" in label


def test_warmup_help_mentions_visibility_rule() -> None:
    """The help tooltip explains debug_mode/localhost gating to BAs."""
    help_text = LABELS["sidebar_warmup_help"]
    assert "debug" in help_text.lower()
    assert "localhost" in help_text.lower()
