"""Chunked window transcription over decoder PCM (ADR-0023 engine loop)."""

from __future__ import annotations

import inspect
import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from voice_typer.server.transcription_batching import _BATCHED_SUPER_CHUNK_S

log = logging.getLogger(__name__)

# One window = one batched decode call: above the engine's batched minimum the
# parallel (batch_size=8) pipeline runs, and at the super-chunk size that
# pipeline gets the window as a SINGLE piece (no silence split) — so a media
# job stops paying a sequential decode per 30 s slice.
WINDOW_SECONDS = _BATCHED_SUPER_CHUNK_S
TARGET_SAMPLE_RATE = 16_000


class WindowBackend(Protocol):
    """Structural contract: active ASR backend chunk transcription."""

    def transcribe_with_fallback(self, audio: Any, *args: object, **kwargs: object) -> str: ...

    def request_abort(self) -> None: ...


@dataclass
class WindowsState:
    """Accumulated transcript + decoded offset, survives stream retries.

    Shared across re-opened streams so a stall/expiry resume (E9/E10)
    continues appending instead of losing the partial transcript.
    """

    texts: list[str] = field(default_factory=list)
    decoded_seconds: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(self.texts).strip()


# (fraction, eta_seconds); eta is None until a stable rate is known.
ProgressCallback = Callable[[float, float | None], None]

# Serializes a decode against the ONE shared model. Supplied by the job
# manager so concurrent media jobs interleave ingest but never inference.
LaneFactory = Callable[[], Any]

_WORKER_WINDOW_TIMEOUT_S = 300.0


def _accepts_scoped_abort(backend: Any) -> bool:
    """True when this backend can take a per-call ``abort_event``.

    The whisper engine threads it into the decode loop; the cloud / parakeet
    / qwen engines have their own cancellation and no ``**kwargs``, so asking
    them would raise ``TypeError`` rather than abort anything.
    """
    try:
        params = inspect.signature(backend.transcribe_with_fallback).parameters
    except (TypeError, ValueError):  # builtins / C callables
        return False
    if "abort_event" in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _shared_worker_client() -> Any | None:
    try:
        from voice_typer.server import worker_client

        return worker_client.get_shared_client()
    except Exception:  # noqa: BLE001, worker hop is optional
        return None


def _worker_path_available(backend: object) -> bool:
    """Single-gate delegate: the policy lives in ``worker_path`` (E7)."""
    from voice_typer.server import worker_path

    ok, _reason = worker_path.worker_path_for_backend(backend)
    return ok


class WorkerWindowBackend:
    """Worker hop for one media window, satisfying ``WindowBackend``.

    Raises on any worker failure so the caller falls back in-process.
    """

    def __init__(
        self,
        *,
        language: str | None = None,
        timeout: float = _WORKER_WINDOW_TIMEOUT_S,
        client: Any | None = None,
    ) -> None:
        self._language = language
        self._timeout = float(timeout)
        self._client_override = client
        self._current_request_id: int | None = None
        self._current_future: Any | None = None

    def transcribe_with_fallback(self, audio: Any, *args: object, **kwargs: object) -> str:
        import numpy as np

        language = kwargs.get("language", self._language)
        if language is not None and not isinstance(language, str):
            language = self._language
        arr = np.asarray(audio, dtype=np.float32).reshape(-1)
        audio_bytes = arr.tobytes()
        client = self._client_override if self._client_override is not None else _shared_worker_client()
        if client is None:
            raise RuntimeError("worker client unavailable")
        future = client.request_samples(audio_bytes, TARGET_SAMPLE_RATE, language, timeout=self._timeout)
        if future is None:
            raise RuntimeError("worker not connected")
        self._current_future = future
        try:
            seq = getattr(client, "_request_seq", None)
            self._current_request_id = int(seq) if isinstance(seq, int) else None
        except Exception:  # noqa: BLE001, id tracking is best-effort
            self._current_request_id = None
        try:
            result = future.result(timeout=self._timeout)
        except Exception:
            import contextlib as _contextlib

            with _contextlib.suppress(Exception):
                self.request_abort()
            raise
        finally:
            self._current_future = None
        if isinstance(result, dict):
            if result.get("error"):
                self._current_request_id = None
                raise RuntimeError(str(result.get("error")))
            text = str(result.get("text") or "")
            self._current_request_id = None
            return text
        self._current_request_id = None
        return str(result or "")

    def request_abort(self) -> None:
        request_id = self._current_request_id
        client = self._client_override if self._client_override is not None else _shared_worker_client()
        if client is None:
            return
        if request_id is None:
            return
        try:
            send = getattr(client, "send_abort", None)
            if callable(send):
                send(int(request_id))
        except Exception:  # noqa: BLE001, abort is best-effort
            log.debug("[MEDIA] worker abort send failed", exc_info=True)
        try:
            cancel = getattr(client, "cancel_request", None)
            if callable(cancel):
                cancel(int(request_id))
        except Exception:  # noqa: BLE001, abort is best-effort
            log.debug("[MEDIA] worker abort cancel failed", exc_info=True)


def transcribe_windows(
    chunks: Iterable[Any],
    backend: WindowBackend,
    *,
    cancel_event: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
    total_seconds: float | None = None,
    state: WindowsState | None = None,
    lane: LaneFactory | None = None,
) -> WindowsState:
    """Accumulate 5 s chunks into 30 s windows; transcribe each.

    Cancellation stops the loop cooperatively and returns the partial
    state instead of raising, so the caller can persist it (E14).

    ``lane`` wraps every decode so concurrent jobs share the single model
    safely. ``cancel_event`` is handed to the decoder as a SCOPED abort
    source: the job's own Event, never the engine-wide flag, so cancelling a
    media job cannot truncate a dictation recording or another job's window.
    """
    import numpy as np

    acc = state if state is not None else WindowsState()
    window: list[Any] = []
    window_samples = 0
    window_cap = int(WINDOW_SECONDS * TARGET_SAMPLE_RATE)
    started = time.perf_counter()
    start_offset = acc.decoded_seconds
    worker_backend: WorkerWindowBackend | None = None
    # Decided once per call: the backend cannot change under us, and this is
    # a per-window hot path.
    scoped_abort = cancel_event is not None and _accepts_scoped_abort(backend)

    def _decode(audio: Any) -> str:
        """Transcribe one window (worker hop, else in-process)."""
        nonlocal worker_backend
        if _worker_path_available(backend):
            try:
                if worker_backend is None:
                    worker_backend = WorkerWindowBackend(language=getattr(backend, "language", None))
                else:
                    worker_backend._language = getattr(backend, "language", None)
                text = str(worker_backend.transcribe_with_fallback(audio) or "").strip()
                if text:
                    acc.texts.append(text)
                return text
            except Exception:  # noqa: BLE001, worker failure falls back in-process
                log.debug("[MEDIA] worker window failed, falling back to in-process", exc_info=True)
        kwargs = {"abort_event": cancel_event} if scoped_abort else {}
        text = str(backend.transcribe_with_fallback(audio, **kwargs) or "").strip()
        if text:
            acc.texts.append(text)
        return text

    def _flush() -> None:
        nonlocal window, window_samples
        if not window:
            return
        audio = np.concatenate(window).astype(np.float32, copy=False)
        window = []
        window_samples = 0
        if lane is None:
            _decode(audio)
            return
        with lane():
            # A job cancelled while it waited for the model must not pay for
            # a decode nobody wants: release the lane and let the loop end.
            if cancel_event is not None and cancel_event.is_set():
                return
            _decode(audio)

    def _cancelled() -> bool:
        if cancel_event is None or not cancel_event.is_set():
            return False
        # The in-process decode stops on its own: the same Event is the
        # abort source it polls between segments. Only the worker hop needs
        # an explicit abort (it targets ITS OWN request id, so it is already
        # scoped). Nothing here touches the engine-wide signal any more.
        if worker_backend is not None:
            try:
                worker_backend.request_abort()
            except Exception:  # noqa: BLE001, abort is best-effort
                log.debug("[MEDIA] worker abort failed", exc_info=True)
        return True

    for chunk in chunks:
        if _cancelled():
            break
        window.append(chunk)
        window_samples += int(chunk.shape[0])
        acc.decoded_seconds += float(chunk.shape[0]) / TARGET_SAMPLE_RATE
        if window_samples >= window_cap:
            _flush()
            if _cancelled():
                break
        if on_progress is not None and total_seconds:
            frac = min(1.0, acc.decoded_seconds / total_seconds)
            on_progress(frac, _eta(acc.decoded_seconds - start_offset, started, total_seconds, acc.decoded_seconds))
    if cancel_event is None or not cancel_event.is_set():
        _flush()
        if on_progress is not None:
            on_progress(1.0, 0.0)
    return acc


def _eta(processed: float, started: float, total_seconds: float | None, decoded: float) -> float | None:
    """ETA from the measured decode+transcribe rate of this call."""
    if not total_seconds or processed <= 2.0 or decoded >= total_seconds:
        return None
    elapsed = time.perf_counter() - started
    if elapsed <= 0:
        return None
    rate = processed / elapsed
    if rate <= 0:
        return None
    return round(max(0.0, (total_seconds - decoded) / rate), 1)
