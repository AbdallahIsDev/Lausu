"""RNNoise model-loading + lazy-resampler-init"""

from __future__ import annotations

import numpy as np
import pytest

scipy = pytest.importorskip("scipy.signal")  # skips the whole module if missing

from voice_typer.server._audio_constants import RNNOISE_SAMPLE_RATE  # noqa: E402
from voice_typer.server.audio_filters import noise_suppressor as _ns  # noqa: E402
from voice_typer.server.audio_filters.noise_suppressor import (  # noqa: E402
    NoiseSuppressor,
    _StreamingResampler,
)
from voice_typer.server.audio_filters.rnnoise_ctypes import LibraryLoadError  # noqa: E402


class _FakeRNNoise:
    """Minimal stand-in for our ctypes RNNoise backend."""

    def __init__(self, sample_rate: int = RNNOISE_SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self.channels = 1  # set by _process_rnnoise before denoise_frame

    def denoise_frame(self, frame_i16: np.ndarray) -> tuple[float, np.ndarray]:
        return (0.0, frame_i16)

    def reset(self) -> None:
        pass


def _install_fake_backend(monkeypatch: pytest.MonkeyPatch, backend_cls: type = _FakeRNNoise) -> None:
    """Patch the one seam ``_init_rnnoise`` uses to build its backend."""
    monkeypatch.setattr(_ns, "_make_rnnoise_backend", lambda sample_rate: backend_cls(sample_rate))


def _install_unavailable_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a missing native library (clean GTCRN fallback path)."""

    def _raise(sample_rate: int) -> None:
        raise LibraryLoadError("native RNNoise library not found")

    monkeypatch.setattr(_ns, "_make_rnnoise_backend", _raise)


class TestLazyResamplerInitMemoization:
    """same rate must NOT recreate the resamplers (the FIR filter design"""

    def test_lazy_init_runs_once_and_memoized(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Construct a NoiseSuppressor with a stubbed RNNoise backend,"""
        _install_fake_backend(monkeypatch)
        ns = NoiseSuppressor(method="rnnoise", sample_rate=16000)
        assert ns._backend is not None, "RNNoise backend must be constructed when the native library is available"
        assert ns.is_degraded is False, "NoiseSuppressor must NOT be degraded when RNNoise init succeeds"

        # Spy on _StreamingResampler.__init__ to count constructions.
        init_calls: list[tuple[int, int]] = []
        original_init = _StreamingResampler.__init__

        def _counting_init(self, up: int, down: int) -> None:
            init_calls.append((up, down))
            original_init(self, up, down)

        monkeypatch.setattr(_StreamingResampler, "__init__", _counting_init)

        # First process() call, lazy resampler init runs.
        audio = np.random.randn(480).astype(np.float32) * 0.1
        result1 = ns.process(audio, 16000)
        # Capture the resampler identities after the first call.
        upsampler_after_first = ns._upsampler
        downsampler_after_first = ns._downsampler
        assert upsampler_after_first is not None, "upsampler must be constructed after the first process() call"
        assert downsampler_after_first is not None, "downsampler must be constructed after the first process() call"

        # Second process() call, memoization guard must skip recreation.
        result2 = ns.process(audio, 16000)

        # 1. The resamplers were constructed (lazy init ran).
        assert ns._upsampler is not None
        assert ns._downsampler is not None

        # 2. _StreamingResampler.__init__ was called exactly TWICE (once
        assert len(init_calls) == 2, (
            f"_StreamingResampler.__init__ must be called exactly "
            f"twice (once for upsampler, once for downsampler) across two "
            f"process() calls at the same rate; got {len(init_calls)} calls "
            f"— memoization guard failed and the resamplers were recreated"
        )

        assert ns._upsampler is upsampler_after_first, (
            "upsampler object identity must be stable across process() calls (memoized, not recreated)"
        )
        assert ns._downsampler is downsampler_after_first, (
            "downsampler object identity must be stable across process() calls (memoized, not recreated)"
        )

        # Sanity: both process() calls produced output (not None).
        assert result1 is not None
        assert result2 is not None


class TestSampleRateResamplerConstruction:
    """when the ``process()`` sample rate is NOT the RNNoise"""

    def test_sample_rate_resampler_constructed_when_input_not_16k(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Construct a NoiseSuppressor with a stubbed RNNoise backend,"""
        _install_fake_backend(monkeypatch)
        ns = NoiseSuppressor(method="rnnoise", sample_rate=44100)

        # Before process(), resamplers are NOT yet constructed (lazy).
        assert ns._upsampler is None, "upsampler must NOT be constructed before the first process() call (lazy init)"
        assert ns._downsampler is None, (
            "downsampler must NOT be constructed before the first process() call (lazy init)"
        )

        # 44100 is not the RNNoise native rate (48000), resamplers
        audio = np.random.randn(480).astype(np.float32) * 0.1
        ns.process(audio, 44100)

        # 1. Upsampler constructed (44100 != 48000 → resampling needed).
        assert ns._upsampler is not None, (
            "upsampler must be constructed when process() sample rate (44100) != RNNOISE_SAMPLE_RATE (48000)"
        )
        # 2. Downsampler constructed (round-trip back to 44100).
        assert ns._downsampler is not None, (
            "downsampler must be constructed for the 48k→44100 round-trip back to the source rate"
        )
        # 3. _resampler_rate is set to the process sample rate.
        assert ns._resampler_rate == 44100, (
            f"_resampler_rate must be set to the process sample rate (44100); got {ns._resampler_rate}"
        )

    def test_no_resampler_at_native_rate(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """At the RNNoise native rate (48000), NO resampler is"""
        _install_fake_backend(monkeypatch)
        ns = NoiseSuppressor(method="rnnoise", sample_rate=48000)

        audio = np.random.randn(480).astype(np.float32) * 0.1
        ns.process(audio, 48000)

        # Both resamplers stay None (native rate, no resampling needed).
        assert ns._upsampler is None, (
            "upsampler must stay None at the RNNoise native rate (48000), no resampling needed"
        )
        assert ns._downsampler is None, (
            "downsampler must stay None at the RNNoise native rate (48000), no resampling needed"
        )
        # _resampler_rate is set so a subsequent rate change is detected.
        assert ns._resampler_rate == 48000


class TestInitFailureClearError:
    """when ``RNNoise(sample_rate=48000)`` raises (model file"""

    def test_init_failure_raises_clear_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A non-library backend failure keeps the old clear-error path."""

        class _FailingRNNoise:
            def __init__(self, sample_rate: int = RNNOISE_SAMPLE_RATE) -> None:
                raise RuntimeError("model file not found")

        _install_fake_backend(monkeypatch, _FailingRNNoise)

        ns = NoiseSuppressor(method="rnnoise", sample_rate=16000)

        # 1. is_degraded is True (init failure caught).
        assert ns.is_degraded is True, (
            "NoiseSuppressor must be degraded when RNNoise init "
            "raises (the exception is caught and the filter falls back "
            "to passthrough)"
        )

        # 2. degraded_reason contains "rnnoise" (which backend failed).
        assert "rnnoise" in ns.degraded_reason.lower(), (
            f"degraded_reason must mention 'rnnoise' so the user knows WHICH backend failed; got {ns.degraded_reason!r}"
        )

        # 3. degraded_reason contains the original exception message.
        assert "model file not found" in ns.degraded_reason, (
            f"degraded_reason must surface the original exception "
            f"message ('model file not found') so the user can act on the "
            f"specific failure; got {ns.degraded_reason!r}"
        )

        # 4. _method fell back to "none" (passthrough).
        assert ns._method == "none", (
            f"_method must fall back to 'none' (passthrough) when RNNoise init fails; got {ns._method!r}"
        )

        # 5. _backend is None (no RNNoise instance kept).
        assert ns._backend is None, (
            "_backend must be None when RNNoise init fails (no instance to keep, the constructor raised)"
        )

    def test_native_library_missing_degraded_reason_mentions_rnnoise(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A missing native library serves GTCRN with ONE clear warning."""
        import logging

        _install_unavailable_backend(monkeypatch)
        monkeypatch.setattr(_ns, "_backend_ready_logged", set())

        with caplog.at_level(logging.WARNING, logger="voice_typer.server.audio_filters.noise_suppressor"):
            ns = NoiseSuppressor(method="rnnoise", sample_rate=16000)

        assert ns.is_degraded is True, (
            "NoiseSuppressor must be degraded when the native library is missing"
        )
        assert "rnnoise" in ns.degraded_reason.lower(), (
            f"degraded_reason must mention 'rnnoise' on library failure; got {ns.degraded_reason!r}"
        )
        # rnnoise unavailable: the bundled gtcrn substitute serves instead
        # of silent none (real GtcrnBackend constructs in this env).
        assert ns._method == "gtcrn", (
            f"_method must substitute bundled 'gtcrn' when the library is missing; got {ns._method!r}"
        )
        assert ns._backend is not None, "substitute backend must be live"
        warnings = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING and "rnnoise unavailable" in r.getMessage()
        ]
        assert len(warnings) == 1, f"exactly one clear WARNING expected; got {warnings}"

    def test_library_missing_both_missing_falls_back_to_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Native library absent AND gtcrn unloadable → none, degraded, both named."""
        _install_unavailable_backend(monkeypatch)

        class _FailingGtcrn:
            def __init__(self) -> None:
                raise RuntimeError("gtcrn model unavailable in test")

        from voice_typer.server.audio_filters import gtcrn_backend as _gtcrn_module

        monkeypatch.setattr(_gtcrn_module, "GtcrnBackend", _FailingGtcrn)

        ns = NoiseSuppressor(method="rnnoise", sample_rate=16000)

        assert ns.is_degraded is True
        assert ns._method == "none", f"both backends down must yield 'none'; got {ns._method!r}"
        assert "rnnoise" in ns.degraded_reason.lower()
