"""Audio status must name the denoiser that is SERVING (C-UI-15).

Config says what the user asked for; a fallback, a missing runtime or a late
preload decides what actually runs. Printing the request over a gtcrn chain is
exactly how "DPDFNet is on" coexisted with a −10.6 dB meter for a whole session
(docs/microphone-filter-failures.md §3.2, issue B3).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server.audio_filters.effective_backend import (
    REASON_BACKEND_UNAVAILABLE,
    effective_noise_suppression,
)
from voice_typer.server.service.status import StatusMixin


class _Suppressor:
    def __init__(self, method: str, degraded: bool = False) -> None:
        self.effective_method = method
        self.is_degraded = degraded
        self.backend_signature = (method, f"{method.title()}Backend")


class _Processor:
    """A chain whose suppressor is serving ``method``."""

    def __init__(self, method: str, *, requested: str = "dpdfnet", enabled: bool = True) -> None:
        self._chain = SimpleNamespace(filters=[_Suppressor(method)])
        self._config = SimpleNamespace(noise_suppression_method=requested, noise_filter_enabled=enabled)
        self.filter_names = [f"NoiseSuppressor({method})"]
        self.is_degraded = method != requested
        self.degraded_reasons = [] if not self.is_degraded else ["fallback"]
        self.total_latency_ms = 20.0


def _config(**overrides) -> SimpleNamespace:
    base = {
        "noise_suppression_method": "dpdfnet",
        "noise_filter_enabled": True,
        "use_silero_vad": False,
        "sample_rate": 16_000,
        "config_dir": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _service(**kwargs) -> StatusMixin:
    service = object.__new__(StatusMixin)
    service._app = SimpleNamespace(
        _audio_processor=kwargs.get("processor"),
        config=kwargs.get("config") or _config(),
        tray=SimpleNamespace(state=SimpleNamespace(value="idle"), _message=""),
        recorder=SimpleNamespace(_xruns=0),
        models=None,
    )
    service._get_offline_pack_status = lambda: {}  # type: ignore[method-assign]
    return service


@pytest.fixture()
def level_chain(monkeypatch: pytest.MonkeyPatch):
    """Install a level-monitor chain in the shared state (and clean it up)."""
    # The package proxies `_`-prefixed names to the singleton, so import the
    # submodule's own binding rather than `level_monitor._state`.
    from voice_typer.server.level_monitor._state import _state as shared_state

    def install(processor: object | None, config: dict | None = None) -> None:
        monkeypatch.setattr(shared_state, "_level_processor", processor, raising=False)
        monkeypatch.setattr(shared_state, "_level_processor_config", config, raising=False)

    return install


# ── the reporter itself ───────────────────────────────────────────────────


def test_a_fallback_reports_requested_and_effective_with_a_reason() -> None:
    status = effective_noise_suppression(_Processor("gtcrn"))

    assert status["requested"] == "dpdfnet"
    assert status["effective"] == "gtcrn"
    assert status["degraded"] is True
    assert status["reason_code"] == REASON_BACKEND_UNAVAILABLE


def test_a_matching_backend_is_not_degraded() -> None:
    status = effective_noise_suppression(_Processor("dpdfnet"))

    assert status["effective"] == "dpdfnet"
    assert status["degraded"] is False
    assert status["reason_code"] == ""


def test_filter_off_is_not_a_degradation() -> None:
    """Preset off = no denoiser ON PURPOSE, so nothing may be reported as fallen back."""
    status = effective_noise_suppression(None, "dpdfnet", enabled=False)

    assert status == {
        "enabled": False,
        "requested": "dpdfnet",
        "effective": "none",
        "degraded": False,
        "reason_code": "",
    }


def test_no_chain_reports_none() -> None:
    assert effective_noise_suppression(None, "dpdfnet")["effective"] == "none"


# ── the two status surfaces ───────────────────────────────────────────────


def test_get_audio_status_reports_the_dictation_and_meter_chains(level_chain) -> None:
    level_chain(_Processor("gtcrn"), {"noise_suppression_method": "dpdfnet", "noise_filter_enabled": True})
    service = _service(processor=_Processor("dpdfnet"))

    status = service.get_audio_status()

    assert status["noise_suppression"]["effective"] == "dpdfnet"
    assert status["noise_suppression"]["degraded"] is False
    assert status["level_monitor"]["noise_suppression"]["effective"] == "gtcrn"
    assert status["level_monitor"]["noise_suppression"]["degraded"] is True


def test_get_audio_status_reports_no_meter_chain_before_the_page_opens(level_chain) -> None:
    level_chain(None, None)

    status = _service(processor=None).get_audio_status()

    assert status["noise_suppression"] is None
    assert status["level_monitor"]["noise_suppression"] is None


def test_get_status_carries_the_effective_denoiser(level_chain) -> None:
    level_chain(None, None)
    service = _service(processor=_Processor("gtcrn"))

    payload = service.get_status()

    assert payload["noise_suppression"]["requested"] == "dpdfnet"
    assert payload["noise_suppression"]["effective"] == "gtcrn"
    assert payload["level_monitor_noise_suppression"] is None


def test_the_status_payload_names_no_paths_or_exceptions(level_chain) -> None:
    """The renderer only ever sees codes; detail stays in the log (C-UXERR)."""
    level_chain(None, None)
    status = _service(processor=_Processor("gtcrn")).get_audio_status()["noise_suppression"]

    text = str(status)
    assert "/" not in text and "Traceback" not in text and "Error" not in text


def test_a_stale_config_cannot_make_the_meter_chain_look_healthy(level_chain) -> None:
    """The meter's OWN config decides its requested method, not the app config."""
    level_chain(_Processor("gtcrn"), {"noise_suppression_method": "rnnoise", "noise_filter_enabled": True})
    service = _service(config=_config(noise_suppression_method="dpdfnet"))

    status = service.get_audio_status()["level_monitor"]["noise_suppression"]

    assert status["requested"] == "rnnoise"
    assert status["effective"] == "gtcrn"
    assert status["degraded"] is True


def test_get_audio_status_builds_without_a_processor(level_chain) -> None:
    level_chain(None, None)
    service = _service(processor=None)

    status = service.get_audio_status()

    assert status["filter_chain"] == []
    assert status["vad_backend"] == "rms"


def test_a_meter_chain_that_cannot_be_inspected_never_claims_to_denoise(level_chain) -> None:
    """An unreadable chain must report ``none``, not the requested backend."""

    class _Broken:
        @property
        def _chain(self):
            raise RuntimeError("chain unavailable")

        _config = SimpleNamespace(noise_suppression_method="dpdfnet", noise_filter_enabled=True)

    level_chain(_Broken(), {"noise_suppression_method": "dpdfnet", "noise_filter_enabled": True})

    status = _service(processor=None).get_audio_status()["level_monitor"]["noise_suppression"]

    assert status["effective"] == "none"
    assert status["degraded"] is True
