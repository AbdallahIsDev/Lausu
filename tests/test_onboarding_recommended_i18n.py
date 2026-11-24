"""Onboarding recommended model + i18n (no real downloads)."""

from __future__ import annotations

import json
from pathlib import Path

LOCALES = ["en", "ar", "de", "es", "fr", "hi", "ru", "zh"]
REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS_DIR = REPO_ROOT / "voice_typer/client/src/renderer/src/i18n/translations"


def _onboarding(locale: str) -> dict:
    return json.loads((TRANSLATIONS_DIR / f"{locale}.json").read_text(encoding="utf-8"))["onboarding"]


class TestRecommendedEntry:
    def test_parakeet_entry_is_ultra(self, tmp_config_dir):
        from voice_typer.server.onboarding import OnboardingController

        ctrl = OnboardingController(config_dir=tmp_config_dir)
        parakeet = next(o for o in ctrl.MODEL_OPTIONS if o["name"] == "parakeet")
        assert parakeet["size"] == "~670MB"
        assert parakeet["speed"] == "Fast"
        assert parakeet["description"] == "Parakeet Ultra, fast & accurate, 25 European languages"
        assert parakeet["vram_gb"] == 2.0
        assert parakeet["backend"] == "parakeet"
        assert parakeet["display_name"] == "Parakeet Ultra"

    def test_exactly_one_recommended_entry(self, tmp_config_dir):
        from voice_typer.server.onboarding import OnboardingController

        ctrl = OnboardingController(config_dir=tmp_config_dir)
        flagged = [o for o in ctrl.MODEL_OPTIONS if o.get("recommended") is True]
        assert len(flagged) == 1
        assert flagged[0]["name"] == "parakeet"

    def test_recommended_matches_registry_metadata(self, tmp_config_dir):
        from voice_typer.server.gguf_model_registry import GGUF_MODELS
        from voice_typer.server.model_registry import get_model_metadata
        from voice_typer.server.onboarding import OnboardingController

        ctrl = OnboardingController(config_dir=tmp_config_dir)
        parakeet = next(o for o in ctrl.MODEL_OPTIONS if o["name"] == "parakeet")
        meta = get_model_metadata("parakeet")
        assert meta is not None
        assert meta.display_name == parakeet["display_name"]
        assert meta.download_size_mb == GGUF_MODELS["parakeet"].size_bytes // 1_000_000
        assert meta.speed_rating == "fast"
        assert meta.multilingual is True

    def test_no_english_only_copy_in_recommended_entry(self, tmp_config_dir):
        from voice_typer.server.onboarding import OnboardingController

        ctrl = OnboardingController(config_dir=tmp_config_dir)
        parakeet = next(o for o in ctrl.MODEL_OPTIONS if o["name"] == "parakeet")
        assert "English-only" not in parakeet["description"]
        assert "English only" not in parakeet["description"]


class TestRecommendedI18n:
    def test_models_keys_exist_in_all_locales(self):
        # ``badgeLanguages`` ("25 languages") was a hardcoded claim: the
        # wizard now renders the model's DECLARED count instead.
        keys = ["allModels", "badgeRecommended", "badgeFast"]
        en_models = _onboarding("en")["models"]
        for locale in LOCALES:
            models = _onboarding(locale)["models"]
            for key in keys:
                assert key in models, f"{locale}.json missing onboarding.models.{key}"
                assert isinstance(models[key], str) and models[key].strip()
        assert en_models["allModels"] == "All Models"
        assert "badgeLanguages" not in en_models, (
            "the fixed '25 languages' badge is gone; the count comes from languages.length"
        )

    def test_language_count_badge_has_a_placeheld_translation(self):
        for locale in LOCALES:
            onboarding = _onboarding(locale)
            value = onboarding.get("languageCountBadge")
            assert isinstance(value, str) and value.strip(), f"{locale}.json missing onboarding.languageCountBadge"
            assert "{count}" in value, f"{locale}.json languageCountBadge must interpolate {{count}}"

    def test_non_english_locales_are_translated(self):
        en_models = _onboarding("en")["models"]
        for locale in LOCALES:
            if locale == "en":
                continue
            models = _onboarding(locale)["models"]
            for key, en_value in en_models.items():
                assert models[key] != en_value, (
                    f"{locale}.json onboarding.models.{key} is English fallback: {en_value!r}"
                )
