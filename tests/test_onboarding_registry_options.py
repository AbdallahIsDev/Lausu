"""Onboarding model options must come from the single GGUF registry.

No download is performed here: the registry is an in-process catalogue.
"""

from __future__ import annotations

from voice_typer.server.gguf_model_registry import (
    DEFAULT_MODEL_KEY,
    GGUF_MODELS,
    PRODUCTION_MODEL_KEYS,
)
from voice_typer.server.onboarding import OnboardingController
from voice_typer.server.onboarding_selections import _OnboardingSelectionsMixin


def test_visible_options_are_exactly_the_five_production_models() -> None:
    options = OnboardingController.visible_model_options()
    names = {option["name"] for option in options}

    assert names == set(PRODUCTION_MODEL_KEYS)
    assert len(options) == 5
    assert "tiny" not in names, "dev-only model must never reach the wizard"


def test_visible_option_sizes_come_from_the_registry() -> None:
    options = {
        option["name"]: option
        for option in OnboardingController.visible_model_options()
    }

    for name, option in options.items():
        expected_mb = GGUF_MODELS[name].size_bytes // 1_000_000
        assert option["download_size_mb"] == expected_mb
        # The human label is derived from the byte count, never curated.
        assert option["size"] == _OnboardingSelectionsMixin._size_label(expected_mb)


def test_recommended_flag_follows_the_registry_default() -> None:
    flagged = [
        option["name"]
        for option in OnboardingController.visible_model_options()
        if option.get("recommended") is True
    ]
    assert flagged == [DEFAULT_MODEL_KEY]
