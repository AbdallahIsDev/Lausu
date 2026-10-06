"""Core helpers for hidden streaming transcription.

Implementation split (every moved name is re-exported here, so the
historical import path keeps resolving):
:mod:`voice_typer.server.streaming_windows` (config/word/window types +
window planner), :mod:`voice_typer.server.streaming_assembler`
(committed-word assembler, RACE-031 pins),
:mod:`voice_typer.server.streaming_broadcaster` (live partial publisher).
This module keeps the recorder-audio provenance guard and the session
worker thread.
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable, Iterable
from typing import Any

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.streaming_assembler import StreamingTextAssembler  # noqa: F401  # facade re-export
from voice_typer.server.streaming_broadcaster import PartialTranscriptionBroadcaster  # noqa: F401  # facade re-export
from voice_typer.server.streaming_windows import (  # noqa: F401  # facade re-export
    AudioWindow,
    AudioWindowPlanner,
    StreamingConfig,
    WordTiming,
)

# Token-key normalizer: the MEMOIZED helper shared with text_cleanup is
from voice_typer.server.text_cleanup import _token_key  # noqa: F401  # facade re-export

np = lazy_module("numpy")

log = logging.getLogger(__name__)


def _is_view_of_live_recorder_audio(recorder: Any, arr: Any) -> bool:
    """Provenance check: is ``arr`` a VIEW over audio the live
    recorder still owns?

    The recorder hands out zero-copy snapshot views over TWO backing
    stores, and a destructive ``fill(0)`` on such a view would corrupt the
    recording mid-session (silent transcription windows):

    1. ``recorder._cached_resampled``: the incremental resampled-stream
       cache (snapshot resample path);
    2. ``recorder._audio_pipeline._buffer.storage``, the contiguous raw
       recording buffer itself (the common no-resample path; the buffer
       object may also be a plain deque/list in tests and post-hot-swap
       windows, hence the defensive getattr chain).

    A fresh/owning array (``.base is None``) or any other array is NOT
    recorder-owned and MUST be zeroed after use. Mock recorders in tests
    return auto-attributes that never compare identity-equal, so they keep
    taking the unconditional-zero path.
    """
    base = getattr(arr, "base", None)
    if base is None:
        return False
    cached = getattr(recorder, "_cached_resampled", None)
    if cached is not None and base is cached:
        return True
    # defensive getattr chain (mock/fake recorders in tests may not
    pipeline = getattr(recorder, "_audio_pipeline", None)
    buf = getattr(pipeline, "_buffer", None)
    storage = getattr(buf, "storage", None) if buf is not None else None
    return storage is not None and base is storage


class StreamingTranscriptionSession:
    """Hidden streaming worker for one recording session."""

    def __init__(
        self,
        recorder,
        transcriber,
        config: StreamingConfig,
        sample_rate: int,
        poll_interval_seconds: float = 0.25,
        thread_registry=None,
        local_engine=None,
        cycle_id: str = "",
        busy_check: Callable[[], bool] | None = None,
    ):
        self.recorder = recorder
        self.transcriber = transcriber
        self.config = config
        self.sample_rate = sample_rate
        self.poll_interval_seconds = poll_interval_seconds
        self.planner = AudioWindowPlanner(config)
        self.assembler = StreamingTextAssembler()
        # Live-preview publisher: coalesces committed text into
        self._partial_broadcaster = PartialTranscriptionBroadcaster(
            cycle_id=cycle_id,
        )
        self._cancel_event = threading.Event()
        self._stopped_event = threading.Event()
        self._thread: threading.Thread | None = None
        # set to True if Thread.start() raises; cancel() checks
        self._thread_start_failed: bool = False
        self._fallback_required = False
        # guard _consecutive_failures with a lock, it's
        self._consecutive_failures_lock = threading.Lock()
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._finalizing = False
        # THREAD-REGISTRY: optional central registry for shutdown
        self._thread_registry = thread_registry
        self._cycle_id = cycle_id
        # Residual fence: zero-arg callable returning True when the
        self._busy_check = busy_check
        # optional local engine forwarded to
        self._local_engine = local_engine

    @property
    def confirmed_text(self) -> str:
        return self.assembler.committed_text

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        """Start the background streaming worker.

        previously any exception raised by Thread.__init__
        or .start() (e.g. out of fd, can't start daemon) was silently
        swallowed, leaving the session in a half-initialized state.
        We now catch + record the failure so ``cancel()`` can clean up.

        THREAD-REGISTRY: when a registry was provided to ``__init__``,
        the worker thread is registered so ``shutdown_all()`` can
        signal and join it during ``LausuApp.quit()``. The
        registry entry is removed by ``cancel()`` (after the join, if
        blocking) so a subsequent ``start()`` re-registers cleanly.
        """
        if self.is_running:
            return
        self._cancel_event.clear()
        self._stopped_event.clear()
        # ``finalize()`` sets ``self._finalizing = True`` to gate
        self._finalizing = False
        self._thread_start_failed = False
        try:
            self._thread = threading.Thread(
                target=self._run,
                name="StreamingTranscription",
                daemon=True,
            )
            self._thread.start()
        except (RuntimeError, OSError) as exc:
            # RuntimeError: "can't start new thread" (out of resources)
            log.exception("[STREAMING] Failed to start worker thread: %s", exc)
            self._thread_start_failed = True
            self._thread = None
            # Signal cancelled so any pending cancel() / finalize()
            self._stopped_event.set()
            return
        # THREAD-REGISTRY: register the freshly-started worker so the
        if self._thread_registry is not None and self._thread is not None:
            self._thread_registry.register(
                name="StreamingTranscription",
                thread=self._thread,
                stop_event=self._cancel_event,
                # PERF- reduced from 10.0s to 5.0s. The thread
                join_timeout=5.0,
            )

    def cancel(self, *, blocking: bool = False, timeout: float = 10.0):
        """Stop background streaming work.

        previously ``cancel()`` always called ``thread.join(timeout=10)``,
        which blocked the UI thread for up to 10 seconds when the user
        pressed the mic to stop. We now default to **non-blocking** —
        signal the cancel event and let the worker self-terminate. The
        ``finalize()`` path that needs to wait for the worker still
        passes ``blocking=True``.

        THREAD-REGISTRY: unregisters the worker after a blocking join
        so a subsequent ``start()`` re-registers cleanly. Non-blocking
        cancel leaves the entry in place, ``shutdown_all()`` may still
        need to signal/join the worker if it hasn't exited yet.
        """
        self._cancel_event.set()
        thread = self._thread
        if blocking and thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            # THREAD-REGISTRY: remove the entry after a blocking join
            if self._thread_registry is not None and not thread.is_alive():
                self._thread_registry.unregister("StreamingTranscription")

    def finalize(self, full_audio: np.ndarray) -> str:
        """Return final transcript, using batch fallback if streaming is unsafe."""
        self._finalizing = True
        # Replaced with a short 1.0s defensive wait (covers the rare
        self.cancel(blocking=True)
        thread = self._thread
        if thread is not None and thread.is_alive():
            self._stopped_event.wait(timeout=1.0)
        # Land the last pending partial BEFORE the final result is
        self._partial_broadcaster.flush()
        self._partial_broadcaster.stop()
        return self._finalize_impl(full_audio)

    def process_available_audio_once(self) -> bool:
        """Process one planned window if enough audio is available."""
        if self._finalizing:
            return False
        if self._fallback_required:
            return False

        #  (historical): the pre-fix code held references to
        audio: np.ndarray | None = None
        window: AudioWindow | None = None
        try:
            # skip the snapshot allocation entirely when the
            last_end = self.planner._last_window_end_seconds
            if (
                last_end is not None
                and hasattr(self.recorder, "current_duration_seconds")
                and self.recorder.current_duration_seconds < (last_end + self.config.step_seconds)
            ):
                return False
            audio = self.recorder.snapshot()
            window = self.planner.next_window(audio, self.sample_rate)
            if window is None:
                return False

            words = self.transcriber.transcribe_words(
                window.audio,
                offset_seconds=window.start_seconds,
            )
            self._validate_words(words)
            self.assembler.add_window(
                window,
                words,
                right_guard_seconds=self.config.right_guard_seconds,
            )
            with self._consecutive_failures_lock:
                self._consecutive_failures = 0
            # Live preview: offer the freshly grown committed text to the
            self._partial_broadcaster.push(self.assembler.committed_text)
            return True
        except Exception as exc:
            log.exception("[STREAMING] Chunk transcription failed: %s", exc)
            with self._consecutive_failures_lock:
                self._consecutive_failures += 1
                count = self._consecutive_failures
            if count >= self._max_consecutive_failures:
                log.warning(
                    "[STREAMING] %d consecutive failures, requiring fallback",
                    count,
                )
                self._fallback_required = True
            return False
        finally:
            # the pre-fix ``_secure_clear_audio(audio)`` /
            try:
                if audio is not None and audio.size > 0 and not _is_view_of_live_recorder_audio(self.recorder, audio):
                    audio.fill(0)
                if window is not None and getattr(window, "audio", None) is not None and window.audio.size > 0:
                    waudio = window.audio
                    if not _is_view_of_live_recorder_audio(self.recorder, waudio):
                        waudio.fill(0)
            except (OSError, ValueError, AttributeError):
                # secure-clear is best-effort: a partial zero doesn't
                pass

    def _finalize_impl(self, full_audio: np.ndarray) -> str:
        # Residual fence: if the captured transcriber's backend is
        busy_check = getattr(self, "_busy_check", None)
        if busy_check is not None:
            try:
                backend_busy = bool(busy_check())
            except Exception:
                log.debug(
                    "[STREAMING] finalize busy-check raised (treating as not busy)",
                    exc_info=True,
                )
                backend_busy = False
            if backend_busy:
                log.warning(
                    "[STREAMING] finalize skipped: transcriber backend is busy in "
                    "another thread (finalize-overlap fence), returning "
                    "already-committed streaming text only (cycle=%s)",
                    self._cycle_id,
                )
                with self.assembler._lock:
                    return self.assembler.committed_text

        # Snapshot assembler state under lock at the beginning
        with self.assembler._lock:
            snapshot_committed_text = self.assembler.committed_text
            snapshot_last_committed_time = self.assembler.last_committed_time

        # the pre-fix ``_secure_clear_audio(full_audio)`` call
        try:
            return self._finalize_impl_inner(
                full_audio,
                snapshot_committed_text,
                snapshot_last_committed_time,
            )
        finally:
            # Zero the buffer in
            try:
                if full_audio is not None and full_audio.size > 0:
                    full_audio.fill(0)
            except (OSError, ValueError, AttributeError):
                pass

    def _finalize_impl_inner(
        self,
        full_audio: np.ndarray,
        snapshot_committed_text: str,
        snapshot_last_committed_time: float,
    ) -> str:
        if not snapshot_committed_text:
            # forward the optional local_engine (cloud→local
            return self.transcriber.transcribe_with_fallback(full_audio, local_engine=self._local_engine)
        if self._fallback_required:
            # forward the optional local_engine (cloud→local
            return self.transcriber.transcribe_with_fallback(full_audio, local_engine=self._local_engine)

        # PERF- if the streaming thread's last committed word is
        full_audio_duration = len(full_audio) / self.sample_rate
        try:
            if snapshot_last_committed_time >= full_audio_duration - 1.5:
                log.info(
                    "[STREAMING] Skipping tail re-transcribe: last committed word at %.2fs, audio ends at %.2fs",
                    snapshot_last_committed_time,
                    full_audio_duration,
                )
                return snapshot_committed_text
        except Exception:
            # Tail re-transcribe is best-effort, if the snapshot
            log.debug("[STREAMING] tail re-transcribe skip check failed", exc_info=True)

        try:
            tail_start_seconds = max(
                0.0,
                snapshot_last_committed_time - self.config.left_overlap_seconds,
            )
            start_sample = min(
                len(full_audio),
                int(round(tail_start_seconds * self.sample_rate)),
            )
            tail_audio = full_audio[start_sample:]
            words = self.transcriber.transcribe_words(
                tail_audio,
                offset_seconds=tail_start_seconds,
            )
            self._validate_words(words)
            merge_boundary = snapshot_last_committed_time
            new_tail_words = [word for word in words if word.end_seconds > merge_boundary]
            self.assembler.add_words(new_tail_words, commit_horizon_seconds=math.inf)
            return self.assembler.committed_text
        except Exception as exc:
            log.exception("[STREAMING] Final tail merge failed: %s", exc)
            # forward the optional local_engine (cloud→local
            return self.transcriber.transcribe_with_fallback(full_audio, local_engine=self._local_engine)

    def _run(self):
        try:
            while not self._cancel_event.is_set():
                self.process_available_audio_once()
                self._cancel_event.wait(self.poll_interval_seconds)
        finally:
            # No more windows will be processed. Stop the partial-text
            self._partial_broadcaster.stop()
            self._stopped_event.set()

    def _validate_words(self, words: Iterable[WordTiming]):
        for word in words:
            if not isinstance(word.word, str):
                raise TypeError("word text must be a string")
            if word.start_seconds is None or word.end_seconds is None:
                raise TypeError("word timestamps are required")
            if not (math.isfinite(word.start_seconds) and math.isfinite(word.end_seconds)):
                raise ValueError("word timestamps must be finite")
            if word.end_seconds < word.start_seconds:
                raise ValueError("word end must be >= start")
