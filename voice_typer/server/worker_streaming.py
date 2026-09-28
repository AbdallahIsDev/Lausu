"""Slim-side worker streaming session (ADR-0025 C6).

One purpose only: mirror the ``StreamingTranscriptionSession`` surface
(``start`` / ``finalize`` / ``cancel`` / ``is_running``) while the window
planner, overlap dedup, and inference run in the runtime-pack worker.
Live ``transcription_partial`` pushes arrive through the client's route
and are published to the event bus, exactly like the in-process path.

Failure contract: every worker failure degrades to ``""`` (empty text),
never an exception — the pipeline's existing empty-transcription path
(batch retry, then UX) owns the fallback, same as an empty in-process
result. ``start()`` is the only boolean: ``False`` tells the coordinator
to build the in-process session instead.
"""

from __future__ import annotations

import base64
import logging
import threading
from typing import Any

from voice_typer.server.worker_client import build_streaming_frame

log = logging.getLogger(__name__)

# Push cadence for live audio; each push is a fraction of a second of
# PCM, far under the frame cap.
_PUSH_INTERVAL_SECONDS = 0.5
# Raw PCM bytes per push frame (same bound as the C3 chunker).
_PUSH_RAW_BYTES = 720 * 1024
# Open handshake budget; the worker answers from memory, no inference.
_OPEN_TIMEOUT_SECONDS = 10.0
# Finalize budget: one tail inference on a warm worker.
_FINALIZE_TIMEOUT_SECONDS = 120.0


def _to_f32_bytes(audio: Any) -> bytes:
    """Coerce recorder audio to raw float32 PCM bytes (never raises)."""
    import numpy as _np

    try:
        return _np.asarray(audio, dtype=_np.float32).reshape(-1).tobytes()
    except Exception:
        return b""


class WorkerStreamingSession:
    """Worker-backed hidden streaming session for one recording."""

    def __init__(
        self,
        recorder: Any,
        client: Any,
        config: Any,
        sample_rate: int,
        cycle_id: str = "",
        language: str | None = None,
        poll_interval_seconds: float = _PUSH_INTERVAL_SECONDS,
        thread_registry: Any | None = None,
    ) -> None:
        self._recorder = recorder
        self._client = client
        self._config = config
        self._sample_rate = int(sample_rate)
        self._cycle_id = cycle_id or ""
        self._language = language
        self._poll_interval = float(poll_interval_seconds)
        self._thread_registry = thread_registry
        self._request_id: int | None = None
        self._result_future: Any | None = None
        self._push_index = 0
        self._sent_samples = 0
        self._failed = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """True while the push driver thread is alive."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> bool:
        """Open the worker session; ``False`` means build in-process instead."""
        open_result = self._client.open_streaming_session(self._open_config(), timeout=_OPEN_TIMEOUT_SECONDS)
        if open_result is None:
            return False
        request_id, opened = open_result
        try:
            ack = opened.result(timeout=_OPEN_TIMEOUT_SECONDS)
        except Exception:
            log.debug("[STREAMING] worker open unacknowledged, falling back", exc_info=True)
            self._client.cancel_request(request_id)
            return False
        if not isinstance(ack, dict) or not ack.get("opened"):
            self._client.cancel_request(request_id)
            return False
        self._request_id = request_id
        self._result_future = self._client.expect_streaming_result(request_id, timeout=_FINALIZE_TIMEOUT_SECONDS)
        if self._result_future is None:
            return False
        self._stop_event.clear()
        try:
            self._thread = threading.Thread(
                target=self._drive_pushes,
                name="WorkerStreamingPush",
                daemon=True,
            )
            self._thread.start()
        except (RuntimeError, OSError):
            log.exception("[STREAMING] worker push thread failed to start")
            self._abort_quietly()
            return False
        registry = self._thread_registry
        if registry is not None and self._thread is not None:
            try:
                registry.register(
                    name="WorkerStreamingSession",
                    thread=self._thread,
                    stop_event=self._stop_event,
                    join_timeout=5.0,
                )
            except Exception:
                log.debug("[STREAMING] push thread registry failed", exc_info=True)
        log.info("[STREAMING] worker streaming session started id=%s", request_id)
        return True

    def finalize(self, full_audio: Any) -> str:
        """Push the tail, await the worker's final text; ``""`` on any failure."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=5.0)
        request_id = self._request_id
        if request_id is None or self._failed:
            return ""
        try:
            tail = _to_f32_bytes(full_audio)[self._sent_samples * 4 :]
            if tail:
                self._push_bytes(tail)
            self._client.enqueue_frames([build_streaming_frame("streaming_session_finalize", request_id, {})])
        except Exception:
            log.debug("[STREAMING] worker finalize send failed", exc_info=True)
            return ""
        future = self._result_future
        if future is None:
            return ""
        try:
            result = future.result(timeout=_FINALIZE_TIMEOUT_SECONDS)
        except Exception:
            log.debug("[STREAMING] worker finalize unanswered, falling back", exc_info=True)
            return ""
        if not isinstance(result, dict) or result.get("error"):
            return ""
        return str(result.get("text") or "")

    def cancel(self, *, blocking: bool = False, timeout: float = 10.0) -> None:
        """Stop pushes and abort the worker session (best-effort)."""
        self._stop_event.set()
        thread = self._thread
        if blocking and thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=timeout)
        self._abort_quietly()
        registry = self._thread_registry
        if registry is not None:
            try:
                registry.unregister("WorkerStreamingSession")
            except Exception:
                log.debug("[STREAMING] push thread unregister failed", exc_info=True)

    def _abort_quietly(self) -> None:
        request_id = self._request_id
        self._request_id = None
        if request_id is None:
            return
        try:
            self._client.send_abort(request_id)
        except Exception:
            log.debug("[STREAMING] worker streaming abort failed", exc_info=True)
        try:
            self._client.cancel_request(request_id)
        except Exception:
            log.debug("[STREAMING] worker streaming cancel failed", exc_info=True)

    def _open_config(self) -> dict:
        cfg = self._config
        return {
            "chunk_seconds": float(getattr(cfg, "chunk_seconds", 12.0)),
            "step_seconds": float(getattr(cfg, "step_seconds", 5.0)),
            "left_overlap_seconds": float(getattr(cfg, "left_overlap_seconds", 3.0)),
            "right_guard_seconds": float(getattr(cfg, "right_guard_seconds", 1.5)),
            "min_first_chunk_seconds": float(getattr(cfg, "min_first_chunk_seconds", 6.0)),
            "silence_threshold": float(getattr(cfg, "silence_threshold", 0.003)),
            "sample_rate": self._sample_rate,
            "cycle_id": self._cycle_id,
            "language": self._language,
        }

    def _push_bytes(self, raw: bytes) -> None:
        """Split ``raw`` PCM into push frames and enqueue them all."""
        from voice_typer.server.worker_client import build_streaming_frame

        request_id = self._request_id
        if request_id is None:
            raise RuntimeError("no open worker streaming session")
        frames = []
        for offset in range(0, max(1, len(raw)), _PUSH_RAW_BYTES):
            piece = raw[offset : offset + _PUSH_RAW_BYTES]
            frames.append(
                build_streaming_frame(
                    "streaming_session_push",
                    request_id,
                    {"index": self._push_index, "payload_b64": base64.b64encode(piece).decode("ascii")},
                )
            )
            self._push_index += 1
        if not self._client.enqueue_frames(frames):
            raise RuntimeError("worker outbound queue full")

    def _drive_pushes(self) -> None:
        """Snapshot recorder deltas and push them until stopped/failed."""
        import numpy as _np

        while not self._stop_event.is_set():
            try:
                snapshot = self._recorder.snapshot()
                raw = _np.asarray(snapshot, dtype=_np.float32).reshape(-1).tobytes()
                total_samples = len(raw) // 4
                if total_samples < self._sent_samples:
                    self._sent_samples = 0
                if total_samples > self._sent_samples:
                    self._push_bytes(raw[self._sent_samples * 4 :])
                    self._sent_samples = total_samples
            except Exception:
                log.debug("[STREAMING] worker push failed, stopping pushes", exc_info=True)
                self._failed = True
                return
            self._stop_event.wait(self._poll_interval)
