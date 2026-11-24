"""Regression tests for ``ALLOWED_USER_MODELS`` validation."""

from __future__ import annotations

import json

import pytest
from voice_typer.server.gguf_model_registry import (
    DEFAULT_MODEL_KEY,
    DEFAULT_MODEL_SIZE,
    available_models,
    normalize_model_key,
    production_models,
)


class TestAllowedUserModels:
    """ALLOWED_USER_MODELS must include every model offered in"""

    def test_kept_whisper_models_in_allowed_set(self):
        """Source builds still offer tiny; frozen builds never do."""
        from voice_typer.server.config_validators import ALLOWED_USER_MODELS

        if "tiny" in available_models():
            assert "tiny" in ALLOWED_USER_MODELS, (
                "'tiny' is selectable from source and must survive a config round-trip."
            )
        else:
            assert "tiny" not in ALLOWED_USER_MODELS
        assert "large-v3" in ALLOWED_USER_MODELS, (
            "'large-v3' is not in ALLOWED_USER_MODELS, users who pick it would be silently reset."
        )
        assert "large-v3-turbo" in ALLOWED_USER_MODELS, (
            "'large-v3-turbo' is not in ALLOWED_USER_MODELS, users who pick it would be silently reset."
        )

    def test_removed_models_not_in_allowed_set(self):
        """Models removed by the 2026-08-15 catalog prune must NOT be"""
        from voice_typer.server.config_validators import ALLOWED_USER_MODELS

        for removed in ("tiny.en", "small.en", "medium.en", "base", "small", "medium", "turbo", "distil-large-v3"):
            assert removed not in ALLOWED_USER_MODELS, (
                f"{removed!r} was removed from the catalog (2026-08-15) but is still in ALLOWED_USER_MODELS."
            )

    def test_every_onboarding_model_option_is_allowed(self):
        """ALLOWED_USER_MODELS, otherwise Config.load() silently resets"""
        from voice_typer.server.config_validators import ALLOWED_USER_MODELS
        from voice_typer.server.onboarding import OnboardingController

        model_option_names = {option["name"] for option in OnboardingController.MODEL_OPTIONS}
        disallowed = model_option_names - ALLOWED_USER_MODELS
        assert not disallowed, (
            "OnboardingController.MODEL_OPTIONS names that are NOT in "
            f"ALLOWED_USER_MODELS: {disallowed}. Config.load() would "
            f"silently reset each to {DEFAULT_MODEL_SIZE!r} on the next launch."
        )

    def test_frozen_catalogue_is_production_only(self) -> None:
        assert set(production_models()) == {
            "parakeet",
            "large-v3-turbo",
            "qwen3-1.7b",
            "qwen3-0.6b",
            "large-v3",
        }
        assert "tiny" not in production_models()
        assert DEFAULT_MODEL_KEY in production_models()

    @pytest.mark.parametrize(
        "stored",
        ["tiny", "", "Systran/faster-whisper-tiny", "nonsense", None],
    )
    def test_frozen_normalizes_dev_legacy_empty_and_unknown_ids(self, stored) -> None:
        assert normalize_model_key(stored, frozen=True) == DEFAULT_MODEL_KEY

    def test_frozen_preserves_legacy_ids_for_production_models(self) -> None:
        assert normalize_model_key("Systran/faster-whisper-large-v3", frozen=True) == "large-v3"

    def test_source_keeps_no_model_sentinel_and_resolves_legacy_ids(self) -> None:
        assert normalize_model_key("", frozen=False) == ""
        assert normalize_model_key("tiny", frozen=False) == "tiny"
        assert normalize_model_key("qwen", frozen=False) == "qwen3-1.7b"
        assert normalize_model_key("Systran/faster-whisper-large-v3", frozen=False) == "large-v3"

    @pytest.mark.parametrize(
        "model_size", ["tiny", "large-v3", "large-v3-turbo", "parakeet", "qwen3-1.7b", "qwen3-0.6b"]
    )
    def test_load_preserves_valid_model_choice(self, tmp_config_dir, model_size):
        """Config.load() must preserve a valid model choice, it must"""
        from voice_typer.server.config import Config

        config_file = tmp_config_dir / "config.json"
        config_file.write_text(json.dumps({"model_size": model_size}))

        c = Config.load()
        assert c.model_size == model_size, (
            f"Config.load() reset model_size from '{model_size}' to '{c.model_size}', valid choices must be preserved."
        )

    def test_load_still_normalizes_truly_unsupported_models(self, tmp_config_dir):
        """Sanity check: Config.load() still normalizes unsupported"""
        from voice_typer.server.config import Config

        config_file = tmp_config_dir / "config.json"
        config_file.write_text(json.dumps({"model_size": "unsupported-model-name"}))

        c = Config.load()
        assert c.model_size == DEFAULT_MODEL_SIZE, (
            f"Config.load() should normalize unsupported model names to "
            f"{DEFAULT_MODEL_SIZE!r}, but got '{c.model_size}'."
        )
