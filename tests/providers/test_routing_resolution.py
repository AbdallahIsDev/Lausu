"""Routing resolution matrix: defaults, consent, auth and fallback policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from voice_typer.server.model_providers import Domain, resolve_asr, resolve_llm, resolve_tts
from voice_typer.server.model_providers.errors import (
    ProviderAuthRequiredError,
    ProviderCapabilityError,
    ProviderConsentRequiredError,
    ProviderNotFoundError,
)


@dataclass
class Cfg:
    asr_backend: str = "whisper"
    model_size: str = "tiny"
    cloud_provider: str = ""
    cloud_model: str = ""
    tts_engine: str = "off"
    llm_api_url: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-6-luna"
    asr_provider: str = ""
    asr_model_id: str = ""
    asr_provider_consent: bool = False
    asr_provider_fallback: str = "local"
    tts_provider: str = ""
    tts_model_id: str = ""
    tts_provider_consent: bool = False
    tts_provider_fallback: str = "off"
    llm_provider: str = ""
    llm_model_id: str = ""
    llm_provider_consent: bool = False
    llm_provider_fallback: str = "off"
    openrouter_api_key: str = ""
    ollama_api_key: str = ""
    lmstudio_api_key: str = ""
    openai_api_key: str = ""
    llm_api_key: str = ""
    local_onnx_model_dir: str = ""
    local_onnx_model_id: str = ""


def test_defaults_reproduce_todays_behaviour() -> None:
    cfg = Cfg()
    assert resolve_asr(cfg).provider.id == "local"
    assert resolve_asr(cfg).model_id == "tiny"
    assert resolve_tts(cfg).provider.id == "local"
    assert resolve_llm(cfg).provider.id == "cloud_direct"
    assert resolve_llm(cfg).model_id == "gpt-6-luna"


def test_cloud_asr_backend_still_resolves_to_cloud_direct() -> None:
    cfg = Cfg(asr_backend="cloud", cloud_provider="groq", cloud_model="whisper-large-v3")
    resolved = resolve_asr(cfg)
    assert resolved.provider.id == "cloud_direct"
    assert resolved.model_id == "whisper-large-v3"


@pytest.mark.parametrize("domain", [Domain.ASR, Domain.TTS, Domain.LLM])
def test_remote_without_consent_is_a_typed_error(domain: Domain) -> None:
    cfg = Cfg(
        asr_provider="openrouter",
        asr_model_id="x",
        tts_provider="openrouter",
        llm_provider="openrouter",
        openrouter_api_key="sk-test",
    )
    with pytest.raises(ProviderConsentRequiredError) as exc:
        resolve_asr(cfg) if domain is Domain.ASR else resolve_tts(cfg) if domain is Domain.TTS else resolve_llm(cfg)
    assert exc.value.consent_field


def test_remote_without_key_is_a_typed_error() -> None:
    cfg = Cfg(llm_provider="openrouter", llm_provider_consent=True)
    with pytest.raises(ProviderAuthRequiredError):
        resolve_llm(cfg)


def test_local_provider_needs_no_consent_and_no_key() -> None:
    cfg = Cfg(llm_provider="local_onnx", local_onnx_model_id="minicpm5")
    resolved = resolve_llm(cfg)
    assert resolved.provider.id == "local_onnx"
    assert resolved.model_id == "minicpm5"


def test_unknown_provider_id_is_a_typed_error() -> None:
    with pytest.raises(ProviderNotFoundError):
        resolve_llm(Cfg(llm_provider="not-real"))


def test_capability_mismatch_is_a_typed_error() -> None:
    cfg = Cfg(asr_provider="local_onnx", asr_provider_consent=True)
    with pytest.raises(ProviderCapabilityError):
        resolve_asr(cfg)


def test_three_domains_are_independent() -> None:
    cfg = Cfg(
        asr_provider="openrouter",
        asr_provider_consent=True,
        asr_model_id="asr-model",
        openrouter_api_key="sk-test",
        tts_provider="openai",
        tts_provider_consent=True,
        openai_api_key="sk-tts",
        llm_provider="ollama",
        llm_provider_consent=True,
    )
    assert resolve_asr(cfg).provider.id == "openrouter"
    assert resolve_tts(cfg).provider.id == "openai"
    assert resolve_llm(cfg).provider.id == "ollama"


def test_fallback_policy_is_reported_not_silently_applied() -> None:
    cfg = Cfg(asr_provider="cloud_direct", asr_provider_consent=True)
    assert resolve_asr(cfg).fallback == "local"
    assert resolve_llm(Cfg()).fallback == "off"


def test_no_remote_call_happens_during_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        "voice_typer.server.model_providers.openrouter.request_json",
        lambda *a, **k: calls.append((a, k)),
    )
    cfg = Cfg(llm_provider="openrouter", llm_provider_consent=True, openrouter_api_key="sk-test")
    resolve_llm(cfg)
    assert calls == []
