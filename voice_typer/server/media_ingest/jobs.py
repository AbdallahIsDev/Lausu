"""Single-active-job manager with cancellation (ADR-0023 E14)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from voice_typer.server.duration import format_duration

log = logging.getLogger(__name__)


@dataclass
class MediaJob:
    """One background ingest job."""

    job_id: str
    source: str
    status: str = "running"
    progress: float = 0.0
    cancel_event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: str | None = None


_OnEvent = Callable[[dict], None]


class MediaJobManager:
    """Owns at most one active job; cancel is cooperative via event."""

    def __init__(self, on_event: _OnEvent | None = None) -> None:
        self._lock = threading.Lock()
        self._active: MediaJob | None = None
        self._last: MediaJob | None = None
        self._thread: threading.Thread | None = None
        self._on_event = on_event or (lambda _e: None)

    def start(self, source: str, runner: Callable[[MediaJob], dict[str, Any]]) -> MediaJob:
        """Start ``runner`` on a daemon thread; raise if a job is active."""
        from voice_typer.server.media_ingest.errors import JOB_BUSY

        with self._lock:
            if self._active is not None and self._active.status == "running":
                from voice_typer.server.media_ingest.errors import MediaIngestError

                raise MediaIngestError(JOB_BUSY, "a transcription job is already running")
            job = MediaJob(job_id=uuid.uuid4().hex[:12], source=source)
            self._active = job
            started = threading.Event()

        def _run() -> None:
            started.set()
            started_at = time.perf_counter()
            # One start line + one outcome line per job: the in-app toast is
            # ephemeral, the log is the only durable record of the outcome.
            log.info("[MEDIA] job start: id=%s source=%s", job.job_id, job.source)
            try:
                job.result = runner(job)
                job.status = "cancelled" if job.cancel_event.is_set() else "completed"
                result = job.result or {}
                log.info(
                    "[MEDIA] job %s: id=%s row_id=%s chars=%s%s",
                    job.status,
                    job.job_id,
                    result.get("row_id"),
                    result.get("chars"),
                    format_duration(time.perf_counter() - started_at),
                )
            except Exception as exc:  # noqa: BLE001, captured into job state
                job.status = "failed"
                job.error = str(exc)
                code = getattr(exc, "code", None)
                if code is None:
                    # ASR "pack/model missing" surfaces as RuntimeError
                    # subclasses without .code — map to the renderer's
                    # no_model action instead of a generic internal_error.
                    from voice_typer.server.asr_errors import (
                        ModelIntegrityError,
                        ModelNotDownloadedError,
                    )

                    if isinstance(exc, (ModelNotDownloadedError, ModelIntegrityError)):
                        from voice_typer.server.ipc.validation import ErrorCodes

                        # Namespaced code (the registry test rejects bare
                        # literals). ``isNoModelError()`` in the renderer
                        # accepts both this and the old ``no_engine_loaded``
                        # alias, and it is checked BEFORE ``mediaErrorKey()``,
                        # so the localized copy is unchanged.
                        code = ErrorCodes.NO_MODEL
                    else:
                        code = "internal_error"
                log.exception(
                    "[MEDIA] job failed: id=%s code=%s source=%s error=%s%s",
                    job.job_id,
                    code,
                    job.source,
                    job.error,
                    format_duration(time.perf_counter() - started_at),
                )
                with suppress(Exception):
                    self._on_event(
                        {
                            "type": "media_transcribe_error",
                            "data": {"job_id": job.job_id, "code": str(code), "message": job.error},
                        }
                    )
            finally:
                with self._lock:
                    if self._active is job:
                        self._active = None
                    self._last = job

        thread = threading.Thread(target=_run, name="media-ingest", daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()
        started.wait(timeout=5)
        return job

    def wait(self, timeout: float = 5.0) -> None:
        """Join the current/last job thread (deterministic outcome reads).

        ``job.status`` flips before the outcome line is logged, so callers
        that read the log or the result must join instead of polling status.
        """
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def cancel(self) -> bool:
        """Signal cancellation; True when a running job was found."""
        with self._lock:
            job = self._active
        if job is None or job.status != "running":
            return False
        job.cancel_event.set()
        return True

    def snapshot(self) -> dict[str, Any] | None:
        """Return the active (or last finished) job snapshot, None when idle."""
        with self._lock:
            job = self._active if self._active is not None else self._last
        if job is None:
            return None
        return {
            "job_id": job.job_id,
            "source": job.source,
            "status": job.status,
            "progress": job.progress,
            "error": job.error,
        }

    def publish(self, event: dict) -> None:
        """Forward a job event to the subscriber (event_bus wiring)."""
        self._on_event(event)


_MANAGER: MediaJobManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_job_manager() -> MediaJobManager:
    """Process-wide job manager singleton (errors/complete → event_bus)."""
    global _MANAGER
    if _MANAGER is None:
        with _MANAGER_LOCK:
            if _MANAGER is None:
                from voice_typer.server import event_bus

                def _publish(event: dict) -> None:
                    event_bus.publish(event)

                _MANAGER = MediaJobManager(on_event=_publish)
    return _MANAGER
