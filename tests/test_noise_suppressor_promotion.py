"""A chain built before the DPDFNet preload must still be able to promote.

The shipped machine has no ``pyrnnoise``, so the cold-start fallback is the
gtcrn substitute, and ``_promote_dpdfnet`` used to require ``_method ==
"rnnoise"`` — every session stayed on gtcrn while the UI said DPDFNet
(docs/microphone-filter-failures.md §3.2, issue B1).
"""

from __future__ import annotations

import pytest
from voice_typer.server.audio_filters import dpdfnet_backend, gtcrn_backend, noise_suppressor


class _FakeGtcrn:
    """Stands in for the bundled ONNX model (no session, no weights)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def process_hop(self, hop):  # noqa: ANN001, ANN201 - test double
        return hop, 0.0

    def reset(self) -> None:
        pass


class _FakeDpdfnet:
    """Stands in for the loaded DPDFNet runtime."""

    latency_ms = 20.0

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def process_chunk(self, chunk, sample_rate):  # noqa: ANN001, ANN201 - test double
        return chunk

    def reset(self) -> None:
        pass


@pytest.fixture()
def cold_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """No runtime yet, and no gtcrn model to load."""

    def _unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("dpdfnet runtime not loaded yet")

    monkeypatch.setattr(dpdfnet_backend, "DpdfnetBackend", _unavailable)
    monkeypatch.setattr(dpdfnet_backend, "has_runtime", lambda: False)
    monkeypatch.setattr(gtcrn_backend, "GtcrnBackend", _FakeGtcrn)


def _serving_gtcrn() -> noise_suppressor.NoiseSuppressor:
    sup = noise_suppressor.NoiseSuppressor("dpdfnet", sample_rate=16_000, quiet=True)
    # Force the substitute explicitly: with pyrnnoise installed the constructor
    # would stop at rnnoise, and both are the same "fallback is serving" state.
    if sup.effective_method != "gtcrn":
        assert sup._try_gtcrn_substitute() is True
    return sup


def test_a_gtcrn_substitute_promotes_once_the_runtime_lands(cold_start: None, monkeypatch) -> None:
    sup = _serving_gtcrn()
    assert sup.effective_method == "gtcrn"
    assert sup.name == "NoiseSuppressor(gtcrn)", "the display name must name what is serving"
    assert sup.backend_signature == ("gtcrn", "_FakeGtcrn")

    # The preload finishes.
    monkeypatch.setattr(dpdfnet_backend, "has_runtime", lambda: True)
    monkeypatch.setattr(dpdfnet_backend, "DpdfnetBackend", _FakeDpdfnet)

    assert sup.refresh_backend() is True
    assert sup.effective_method == "dpdfnet"
    assert sup.name == "NoiseSuppressor(dpdfnet)"
    assert sup.backend_signature == ("dpdfnet", "_FakeDpdfnet")
    assert sup._dpdfnet_pending is False
    assert sup.is_degraded is False
    assert sup.degraded_reason == ""


def test_promotion_is_a_one_shot(cold_start: None, monkeypatch) -> None:
    sup = _serving_gtcrn()
    monkeypatch.setattr(dpdfnet_backend, "has_runtime", lambda: True)
    monkeypatch.setattr(dpdfnet_backend, "DpdfnetBackend", _FakeDpdfnet)

    assert sup.refresh_backend() is True
    assert sup.refresh_backend() is False, "a promoted instance must not rebuild on every call"


def test_no_promotion_while_the_runtime_is_still_missing(cold_start: None) -> None:
    sup = _serving_gtcrn()
    assert sup.refresh_backend() is False
    assert sup.effective_method == "gtcrn", "no runtime means the fallback keeps serving"


def test_reset_promotes_without_being_promoted_twice(cold_start: None, monkeypatch) -> None:
    """``reset()`` is the recording-start promotion point (§3.3 double-promote check)."""
    sup = _serving_gtcrn()
    monkeypatch.setattr(dpdfnet_backend, "has_runtime", lambda: True)
    monkeypatch.setattr(dpdfnet_backend, "DpdfnetBackend", _FakeDpdfnet)

    sup.reset()
    assert sup.effective_method == "dpdfnet"
    sup.reset()
    assert sup.effective_method == "dpdfnet"
    assert sup._dpdfnet_pending is False
