"""Cloud ASR as a first-class backend: ``cloud_backend.CloudAsrBackend``.

Covers the four things that had NO coverage before, because nothing in
production ever constructed a cloud engine:

* provider/key/endpoint/model/consent resolution from the live Config,
  including the deliberate refusal to honour ``cloud_api_url`` on a named
  provider (the SEC-011 endpoint-swap class);
* the ``AsrBackend`` contract the registry drives (``is_loaded`` gating so an
  unconfigured cloud degrades to whisper instead of erroring);
* re-resolution on every load/transcribe, so saving a key in Settings takes
  effect without a restart;
* ``unload()`` NOT clearing readiness — the idle-unload timer calls it, and
  clearing ``_loaded`` would silently demote an idle cloud backend.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server.asr_registry import AsrBackendRegistry
from voice_typer.server.cloud._engine import CloudEngine
from voice_typer.server.cloud_backend import (
    CLOUD_BACKEND_NAME,
    CLOUD_PROVIDER_KEYS,
    CloudAsrBackend,
    consent_field_for,
    resolve_cloud_target,
)


def make_config(**overrides: object) -> SimpleNamespace:
    """A Config stand-in carrying every field the backend reads."""
    base: dict[str, object] = {
        "asr_backend": "cloud",
        "cloud_provider": "",
        "cloud_api_key": "",
        "cloud_api_url": "",
        "cloud_model": "",
        "openai_api_key": "",
        "groq_api_key": "",
        "deepgram_api_key": "",
        "gemini_api_key": "",
        "cloud_openai_consent": False,
        "cloud_groq_consent": False,
        "cloud_deepgram_consent": False,
        "cloud_gemini_consent": False,
        "language": "en",
        # ConfigProtocol surface consumed by RegistryCore / CircuitBreaker.
        "model_size": "large-v3",
        "device": "cpu",
        "beam_size": 5,
        "best_of": 5,
        "condition_on_previous_text": False,
        "disabled_backends": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ── resolve_cloud_target ──────────────────────────────────────────────


def test_resolves_named_provider_to_its_own_key_and_endpoint() -> None:
    cfg = make_config(
        cloud_provider="groq",
        groq_api_key="gsk_test",
        cloud_groq_consent=True,
    )
    provider, api_key, api_url, model, consent = resolve_cloud_target(cfg)  # type: ignore[misc]
    assert provider == "groq"
    assert api_key == "gsk_test"
    assert api_url == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert model == "whisper-large-v3"
    assert consent is True


@pytest.mark.parametrize("provider", CLOUD_PROVIDER_KEYS)
def test_every_catalogue_provider_resolves(provider: str) -> None:
    cfg = make_config(**{"cloud_provider": provider, f"{provider}_api_key": "k"})
    resolved = resolve_cloud_target(cfg)
    assert resolved is not None
    assert resolved[0] == provider
    assert resolved[1] == "k"
    assert resolved[2].startswith("https://")


def test_ignores_cloud_api_url_on_a_named_provider() -> None:
    """SEC-011: a stored key must never be posted to a caller-chosen host."""
    cfg = make_config(
        cloud_provider="openai",
        openai_api_key="sk-test",
        cloud_api_url="https://evil.example.com/v1/audio/transcriptions",
    )
    resolved = resolve_cloud_target(cfg)
    assert resolved is not None
    assert resolved[2] == "https://api.openai.com/v1/audio/transcriptions"


def test_explicit_model_wins_over_the_provider_default() -> None:
    cfg = make_config(cloud_provider="deepgram", deepgram_api_key="k", cloud_model="nova-3")
    resolved = resolve_cloud_target(cfg)
    assert resolved is not None
    assert resolved[3] == "nova-3"


def test_empty_model_falls_back_to_the_provider_default() -> None:
    cfg = make_config(cloud_provider="gemini", gemini_api_key="k")
    resolved = resolve_cloud_target(cfg)
    assert resolved is not None
    assert resolved[3] == "gemini-3.5-transcribe"


@pytest.mark.parametrize("provider", ["", "   ", "not-a-provider", "CLOUD"])
def test_unusable_provider_resolves_to_nothing(provider: str) -> None:
    assert resolve_cloud_target(make_config(cloud_provider=provider)) is None


def test_consent_field_name_is_derived_per_provider() -> None:
    assert consent_field_for("openai") == "cloud_openai_consent"
    assert consent_field_for("gemini") == "cloud_gemini_consent"


# ── CloudAsrBackend: identity + readiness ─────────────────────────────


def test_backend_is_a_cloud_engine_so_pipeline_routing_holds() -> None:
    """``transcribe_step`` branches on ``isinstance(active, CloudEngine)``."""
    assert isinstance(CloudAsrBackend(make_config()), CloudEngine)


def test_not_loaded_without_a_key() -> None:
    cfg = make_config(cloud_provider="openai", cloud_openai_consent=True)
    assert CloudAsrBackend(cfg).is_loaded is False


def test_not_loaded_without_consent() -> None:
    cfg = make_config(cloud_provider="openai", openai_api_key="sk-test")
    assert CloudAsrBackend(cfg).is_loaded is False


def test_loaded_with_key_and_consent() -> None:
    cfg = make_config(
        cloud_provider="openai",
        openai_api_key="sk-test",
        cloud_openai_consent=True,
    )
    assert CloudAsrBackend(cfg).is_loaded is True


def test_not_loaded_when_no_provider_is_selected() -> None:
    assert CloudAsrBackend(make_config()).is_loaded is False


def test_unload_does_not_clear_readiness() -> None:
    """The idle-unload timer calls ``unload``; it must not demote cloud."""
    cfg = make_config(
        cloud_provider="groq",
        groq_api_key="gsk_test",
        cloud_groq_consent=True,
    )
    backend = CloudAsrBackend(cfg)
    assert backend.is_loaded is True
    backend.unload()
    assert backend.is_loaded is True


# ── CloudAsrBackend: live re-resolution ───────────────────────────────


def test_transcribe_re_resolves_the_target_from_the_live_config() -> None:
    cfg = make_config(
        cloud_provider="openai",
        openai_api_key="old",
        cloud_openai_consent=True,
    )
    backend = CloudAsrBackend(cfg)

    cfg.openai_api_key = "new"
    cfg.cloud_model = "gpt-4o-transcribe"
    # transcribe() re-resolves before doing anything; an empty audio buffer
    # returns "" without touching the network.
    assert backend.transcribe(_empty_audio()) == ""
    assert backend.api_key == "new"
    assert backend.model_name == "gpt-4o-transcribe"


def test_switching_provider_takes_effect_without_a_new_backend() -> None:
    cfg = make_config(
        cloud_provider="openai",
        openai_api_key="sk-test",
        cloud_openai_consent=True,
    )
    backend = CloudAsrBackend(cfg)
    assert backend.loaded_via == "cloud/openai/whisper-1"

    cfg.cloud_provider = "deepgram"
    cfg.deepgram_api_key = "dg-test"
    cfg.cloud_deepgram_consent = True
    assert backend.transcribe(_empty_audio()) == ""
    assert backend.loaded_via == "cloud/deepgram/nova-3"
    assert backend.device_info == "cloud/deepgram"


def test_a_media_jobs_scoped_abort_reaches_the_config_backed_backend() -> None:
    """The scoped cancel source must survive the ``CloudAsrBackend`` hop.

    ``CloudAsrBackend`` overrides ``transcribe`` to re-resolve the target, so
    the keyword only reaches ``CloudEngine`` if the override forwards it. A
    job Event that is already set must short-circuit the call while the
    engine-wide flag stays clear, which is what proves the override wins.
    """
    import threading

    import numpy as np

    cfg = make_config(
        cloud_provider="openai",
        openai_api_key="sk-test",
        cloud_openai_consent=True,
    )
    backend = CloudAsrBackend(cfg)
    audio = np.zeros(16000, dtype=np.float32)

    job_event = threading.Event()
    job_event.set()
    assert backend.transcribe(audio, abort_event=job_event) == ""
    assert backend._abort_event.is_set() is False


def test_load_re_resolves_so_an_activation_path_sees_a_new_key() -> None:
    cfg = make_config(cloud_provider="openai", cloud_openai_consent=True)
    backend = CloudAsrBackend(cfg)
    assert backend.is_loaded is False

    cfg.openai_api_key = "sk-later"
    backend.load()
    assert backend.is_loaded is True


# ── Registry wiring ───────────────────────────────────────────────────


def test_registry_constructs_and_registers_the_cloud_backend() -> None:
    cfg = make_config(
        cloud_provider="groq",
        groq_api_key="gsk_test",
        cloud_groq_consent=True,
    )
    registry = AsrBackendRegistry(cfg)
    engine = registry.create(CLOUD_BACKEND_NAME, cloud_kwargs={"config": cfg})

    assert isinstance(engine, CloudAsrBackend)
    assert registry.get(CLOUD_BACKEND_NAME) is engine
    assert CLOUD_BACKEND_NAME in registry.available_backends


class _ReadyStubBackend:
    """Minimal loaded ``AsrBackend`` stand-in (avoids real worker plumbing)."""

    is_loaded = True

    @property
    def device_info(self) -> str:
        return "cpu"

    @property
    def loaded_via(self) -> str:
        return "whisper"

    def load(self, *, progress_callback: object | None = None) -> None:
        return None

    def unload(self) -> None:
        return None

    def request_abort(self) -> None:
        return None

    def clear_abort(self) -> None:
        return None

    def transcribe_with_fallback(self, audio: object, *args: object, **kwargs: object) -> str:
        return ""


def test_registry_falls_back_to_whisper_when_cloud_is_unconfigured() -> None:
    """An activated-but-unconfigured cloud must degrade, never raise."""
    cfg = make_config(cloud_provider="")
    registry = AsrBackendRegistry(cfg)
    cloud_engine = registry.create(CLOUD_BACKEND_NAME, cloud_kwargs={"config": cfg})
    whisper = _ReadyStubBackend()
    registry.register("whisper", whisper)

    assert registry.active_name == "cloud"
    assert cloud_engine is not whisper
    assert registry.get_active() is whisper


def _empty_audio():
    import numpy as np

    return np.zeros(0, dtype=np.float32)
