"""Interruptible retry-wait tests for the cloud engine's retry skeleton."""

from __future__ import annotations

import io
import threading
import time
from email.message import Message
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import numpy as np
import pytest
from voice_typer.server.asr_errors import CloudAuthError, CloudEngineError
from voice_typer.server.cloud_engines import CloudEngine

_ABORT_MESSAGE = "transcription aborted by user"


def _make_engine() -> CloudEngine:
    return CloudEngine(
        provider="openai",
        api_key="valid-key",
        api_url="https://api.openai.com/v1/audio/transcriptions",
        consent_given=True,
    )


def _audio() -> np.ndarray:
    return np.ones(16000, dtype=np.float32) * 0.05


class TestRetryAfterWaitIsInterruptible:
    def test_abort_during_retry_after_wait_returns_immediately(self) -> None:
        engine = _make_engine()
        attempt_count = {"n": 0}

        def rate_limited_open(*args, **kwargs):
            attempt_count["n"] += 1
            if attempt_count["n"] == 1:
                engine.request_abort()
            hdrs = Message()
            hdrs["Retry-After"] = "60"
            raise HTTPError(
                url="https://api.openai.com/v1/audio/transcriptions",
                code=429,
                msg="Too Many Requests",
                hdrs=hdrs,
                fp=io.BytesIO(b'{"error": "rate_limit_exceeded"}'),
            )

        mock_opener_open = rate_limited_open
        t0 = time.perf_counter()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                mock_opener_open,
            )
            with pytest.raises(CloudEngineError) as exc_info:
                engine.transcribe(_audio())
        elapsed = time.perf_counter() - t0

        # The abort error must be the engine's canonical abort error
        assert _ABORT_MESSAGE in str(exc_info.value), f"expected the abort error message, got {exc_info.value!r}"
        # A plain time.sleep(60) would take 60s; the interruptible wait
        assert elapsed < 5.0, f"abort during Retry-After wait must return immediately; took {elapsed:.2f}s"
        # Only one HTTP attempt was issued before the abort.
        assert attempt_count["n"] == 1


class TestBackoffWaitIsInterruptible:
    def test_abort_during_urlerror_backoff_returns_immediately(self) -> None:
        engine = _make_engine()
        attempt_count = {"n": 0}

        def network_down_open(*args, **kwargs):
            attempt_count["n"] += 1
            if attempt_count["n"] == 1:
                engine.request_abort()
            raise URLError("network-down")

        t0 = time.perf_counter()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                network_down_open,
            )
            with pytest.raises(CloudEngineError) as exc_info:
                engine.transcribe(_audio())
        elapsed = time.perf_counter() - t0

        assert _ABORT_MESSAGE in str(exc_info.value), f"expected the abort error message, got {exc_info.value!r}"
        assert elapsed < 5.0, f"abort during backoff wait must return immediately; took {elapsed:.2f}s"
        assert attempt_count["n"] == 1

    def test_abort_during_backoff_wait_deepgram_path(self) -> None:
        """Same contract on the Deepgram leg (both provider paths share"""
        engine = CloudEngine(
            provider="deepgram",
            api_key="valid-key",
            api_url="https://api.deepgram.com/v1/listen",
            model="nova-2",
            consent_given=True,
        )
        attempt_count = {"n": 0}

        def network_down_open(*args, **kwargs):
            attempt_count["n"] += 1
            if attempt_count["n"] == 1:
                engine.request_abort()
            raise URLError("network-down")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                network_down_open,
            )
            with pytest.raises(CloudEngineError) as exc_info:
                engine.transcribe(_audio())

        assert _ABORT_MESSAGE in str(exc_info.value)
        assert attempt_count["n"] == 1


class TestNoAbortStillWaitsFullBudget:
    def test_unset_abort_does_not_raise_from_wait(self) -> None:
        """Sanity: an unset abort event must let the wait run its course"""
        engine = _make_engine()
        # A zero-second Retry-After means the wait completes instantly
        hdrs = Message()
        hdrs["Retry-After"] = "0"
        http_err = HTTPError(
            url="https://api.openai.com/v1/audio/transcriptions",
            code=429,
            msg="Too Many Requests",
            hdrs=hdrs,
            fp=io.BytesIO(b"{}"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda *a, **k: (_ for _ in ()).throw(http_err),
            )
            # Second 429 is NOT retried (retry budget spent) → the typed
            from voice_typer.server.asr_errors import CloudRateLimitError

            with pytest.raises(CloudRateLimitError):
                engine.transcribe(_audio())
        assert not engine._abort_event.is_set()


class TestScopedAbortSource:
    """A media job passes its OWN Event, never the engine-wide flag.

    The engine flag is the dictation cancel signal. Both directions are
    pinned here: a scoped abort must stop the call, and a set engine flag must
    NOT be read as that call's abort (it belongs to a different cycle).
    """

    def test_scoped_event_set_before_the_request_returns_empty(self) -> None:
        engine = _make_engine()
        scoped = threading.Event()
        scoped.set()

        assert engine.transcribe(_audio(), abort_event=scoped) == ""
        assert not engine._abort_event.is_set(), "the scoped abort must not touch the engine-wide flag"

    def test_scoped_event_interrupts_the_retry_after_wait(self) -> None:
        engine = _make_engine()
        scoped = threading.Event()
        attempts = {"n": 0}

        def rate_limited_open(*args, **kwargs):
            attempts["n"] += 1
            scoped.set()
            hdrs = Message()
            hdrs["Retry-After"] = "60"
            raise HTTPError(
                url="https://api.openai.com/v1/audio/transcriptions",
                code=429,
                msg="Too Many Requests",
                hdrs=hdrs,
                fp=io.BytesIO(b"{}"),
            )

        t0 = time.perf_counter()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                rate_limited_open,
            )
            with pytest.raises(CloudEngineError) as exc_info:
                engine.transcribe(_audio(), abort_event=scoped)
        elapsed = time.perf_counter() - t0

        assert _ABORT_MESSAGE in str(exc_info.value)
        assert elapsed < 5.0, f"scoped abort during the Retry-After wait must return immediately; took {elapsed:.2f}s"
        assert attempts["n"] == 1
        assert not engine._abort_event.is_set()

    def test_engine_flag_does_not_abort_a_scoped_call(self) -> None:
        engine = _make_engine()
        engine.request_abort()
        denied = HTTPError(
            url="https://api.openai.com/v1/audio/transcriptions",
            code=401,
            msg="Unauthorized",
            hdrs=Message(),
            fp=io.BytesIO(b"{}"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda *a, **k: (_ for _ in ()).throw(denied),
            )
            # Reaches the network layer and fails on the HTTP status, which
            # proves the engine-wide flag was not read as this call's abort.
            with pytest.raises(CloudAuthError):
                engine.transcribe(_audio(), abort_event=threading.Event())


class TestFallbackReadsTheSameAbortSource:
    """``fall_back_to_local`` gates on the abort source the call polled."""

    def test_scoped_abort_skips_the_local_fallback(self) -> None:
        engine = _make_engine()
        scoped = threading.Event()
        local = MagicMock()
        local.transcribe.return_value = "local text"

        def rate_limited_open(*args, **kwargs):
            scoped.set()
            hdrs = Message()
            hdrs["Retry-After"] = "60"
            raise HTTPError(
                url="https://api.openai.com/v1/audio/transcriptions",
                code=429,
                msg="Too Many Requests",
                hdrs=hdrs,
                fp=io.BytesIO(b"{}"),
            )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                rate_limited_open,
            )
            result = engine.transcribe_with_fallback(_audio(), local_engine=local, abort_event=scoped)

        assert result == ""
        local.transcribe.assert_not_called()
        assert not engine._abort_event.is_set()

    def test_engine_flag_does_not_skip_a_scoped_fallback(self) -> None:
        engine = _make_engine()
        engine.request_abort()
        local = MagicMock()
        local.transcribe.return_value = "local text"
        denied = HTTPError(
            url="https://api.openai.com/v1/audio/transcriptions",
            code=401,
            msg="Unauthorized",
            hdrs=Message(),
            fp=io.BytesIO(b"{}"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda *a, **k: (_ for _ in ()).throw(denied),
            )
            result = engine.transcribe_with_fallback(
                _audio(), local_engine=local, abort_event=threading.Event()
            )

        assert result == "local text"
        local.transcribe.assert_called_once()


class _ScopedLocalEngine:
    """Local engine shape parakeet/qwen expose: keyword-only ``abort_event``."""

    def __init__(self) -> None:
        self.received: list[object] = []

    def transcribe(
        self,
        audio: np.ndarray,
        audio_stats: tuple[float, float, float] | None = None,
        *,
        abort_event: object = None,
    ) -> str:
        self.received.append(abort_event)
        return "local text"


class _WhisperShapedLocalEngine:
    """``SystemWhisperEngine`` shape: only ``transcribe_with_fallback`` takes it."""

    def __init__(self) -> None:
        self.scoped: list[object] = []
        self.plain_calls = 0

    def transcribe(self, audio: np.ndarray, audio_stats: object = None) -> str:
        self.plain_calls += 1
        return "local text"

    def transcribe_with_fallback(
        self, audio: np.ndarray, audio_stats: object = None, *, abort_event: object = None
    ) -> str:
        self.scoped.append(abort_event)
        return "local text"


def _unauthorized() -> HTTPError:
    return HTTPError(
        url="https://api.openai.com/v1/audio/transcriptions",
        code=401,
        msg="Unauthorized",
        hdrs=Message(),
        fp=io.BytesIO(b"{}"),
    )


class TestLocalDecodeGetsTheScopedEvent:
    """The fallback decode polls the caller's Event, never the engine flag."""

    def test_scoped_event_reaches_the_local_decode(self) -> None:
        engine = _make_engine()
        engine.request_abort()
        scoped = threading.Event()
        local = _ScopedLocalEngine()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda *a, **k: (_ for _ in ()).throw(_unauthorized()),
            )
            result = engine.transcribe_with_fallback(
                _audio(), local_engine=local, abort_event=scoped
            )

        assert result == "local text"
        assert local.received == [scoped]

    def test_whisper_shaped_engine_gets_the_event_via_its_richer_surface(self) -> None:
        engine = _make_engine()
        scoped = threading.Event()
        local = _WhisperShapedLocalEngine()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda *a, **k: (_ for _ in ()).throw(_unauthorized()),
            )
            result = engine.transcribe_with_fallback(
                _audio(), local_engine=local, abort_event=scoped
            )

        assert result == "local text"
        assert local.scoped == [scoped]
        assert local.plain_calls == 0

    def test_dictation_fallback_without_an_event_still_decodes(self) -> None:
        engine = _make_engine()
        local = _ScopedLocalEngine()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda *a, **k: (_ for _ in ()).throw(_unauthorized()),
            )
            result = engine.transcribe_with_fallback(_audio(), local_engine=local)

        assert result == "local text"
        assert local.received == [None]
