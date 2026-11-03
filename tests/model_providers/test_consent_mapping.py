"""Per-domain consent: legacy gates never re-prompt, Ollama cloud always asks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server.model_providers.descriptor import Domain
from voice_typer.server.model_providers.errors import ProviderConsentRequiredError
from voice_typer.server.model_providers.routing import (
    effective_consent,
    provider_requires_consent,
    resolve_llm,
)


def _config(**overrides):
    base = {
        "asr_provider": "",
        "asr_model_id": "",
        "asr_provider_consent": False,
        "asr_provider_fallback": "local",
        "tts_provider": "",
        "tts_model_id": "",
        "tts_provider_consent": False,
        "tts_provider_fallback": "off",
        "llm_provider": "",
        "llm_model_id": "",
        "llm_provider_consent": False,
        "llm_provider_fallback": "off",
        "llm_polish_consent": False,
        "cloud_provider": "groq",
        "cloud_groq_consent": False,
        "asr_backend": "whisper",
        "model_size": "large-v3-turbo",
        "tts_engine": "magpie",
        "llm_api_key": "",
        "llm_model": "gpt-test",
        "llm_api_url": "",
        "llm_preset": "professional",
        "ollama_api_key": "",
        "ollama_base_url": "",
        "language": "en",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_llm_consent_defaults_from_the_legacy_polish_gate() -> None:
    legacy = _config(llm_polish_consent=True)

    assert effective_consent(legacy, Domain.LLM, "cloud_direct") is True
    assert effective_consent(_config(), Domain.LLM, "cloud_direct") is False


def test_asr_consent_defaults_from_the_selected_cloud_provider() -> None:
    legacy = _config(cloud_groq_consent=True)

    assert effective_consent(legacy, Domain.ASR, "cloud_direct") is True
    assert (
        effective_consent(_config(cloud_groq_consent=True, cloud_provider="openai"), Domain.ASR, "cloud_direct")
        is False
    )


def test_tts_consent_has_no_legacy_equivalent() -> None:
    assert effective_consent(_config(tts_provider_consent=True), Domain.TTS, "custom") is True
    assert effective_consent(_config(), Domain.TTS, "custom") is False


def test_local_ollama_never_needs_consent() -> None:
    config = _config(llm_provider="ollama", llm_model_id="llama3.1")

    resolved = resolve_llm(config)

    assert resolved.provider.id == "ollama"
    assert provider_requires_consent(config, "ollama", resolved.provider) is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"ollama_api_key": "key"},
        {"ollama_base_url": "https://ollama.com/v1"},
    ],
)
def test_cloud_mode_ollama_requires_consent(overrides) -> None:
    config = _config(llm_provider="ollama", llm_model_id="gpt-oss:120b", **overrides)

    with pytest.raises(ProviderConsentRequiredError):
        resolve_llm(config)

    consented = _config(
        llm_provider="ollama",
        llm_model_id="gpt-oss:120b",
        llm_provider_consent=True,
        **overrides,
    )
    assert resolve_llm(consented).provider.id == "ollama"


def test_local_onnx_never_asks_for_consent() -> None:
    config = _config(llm_provider="local_onnx", llm_model_id="minicpm5-2b")

    assert resolve_llm(config).provider.id == "local_onnx"
