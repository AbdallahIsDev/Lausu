"""Provider keys are only ever displayed masked."""

from __future__ import annotations

from voice_typer.server.model_providers.vault import mask_secret, provider_key_field


def test_a_long_key_keeps_only_four_leading_and_four_trailing_chars() -> None:
    masked = mask_secret("sk-or-v1-0123456789abcdef")
    assert masked.startswith("sk-o")
    assert masked.endswith("cdef")
    assert "0123456789ab" not in masked


def test_a_short_key_is_fully_masked() -> None:
    assert mask_secret("abcdef") == "******"


def test_absent_key_masks_to_empty() -> None:
    assert mask_secret("") == ""
    assert mask_secret(None) == ""


def test_each_provider_has_its_own_config_field() -> None:
    fields = {provider_key_field(p) for p in ("openrouter", "ollama", "lmstudio", "custom")}
    assert len(fields) == 4
