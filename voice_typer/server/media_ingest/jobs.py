"""Bounded-concurrency media job manager with cancellation (ADR-0023 E14).

Two different limits apply to a media job, and they are deliberately NOT
the same number:

* **Ingest** (URL resolve, audio download, container decode) is I/O plus
  cheap CPU, so several jobs run at once — ``MAX_CONCURRENT_JOBS`` bounds
  how many the user may have in flight.
* **ASR** is a single shared ctranslate2 model guarded by the engine's own
  ``_inference_lock``. It is not thread-safe, so decode stays one job at a
  time behind ``asr_lane()``. That is also what keeps transcription quality
  independent of how many files the user queued: every window is decoded by
  the same model, with the same settings, alone.

The lane also owns the abort signal. ``request_abort`` / ``clear_abort``
flip ONE event on the shared engine, so cancelling a job that is merely
waiting for the lane must never fire it — that would truncate the decode
of whichever job actually holds the model. ``owns_asr()`` is the guard.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import Any, Final

from voice_typer.server.duration import format_duration

log = logging.getLogger(__name__)

# Four is the ingest sweet spot for a desktop app: the downloads of a batch
# overlap (they are the long pole for links), while at most three decode
# threads compete with the one job that is actually inferring. Raising it
# buys little wall time and starts starving the ASR thread of CPU; the ASR
# lane is serial regardless, so no value here can change transcript quality.
MAX_CONCURRENT_JOBS: Final[int] = 4

# Finished jobs stay readable for status hydration (page navigation) but the
# registry is pruned so a long session cannot grow it without bound.
_MAX_FINISHED_KEPT: Final[int] = 20


@dataclass
class MediaJob:
    """One background ingest job."""

    job_id: str
    source: str
    status: str = "running"
    # Coarse stage the renderer shows before its first progress push.
    phase: str = "starting"
    progress: float = 0.0
    cancel_event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    started_at: float = field(default_factory=time.perf_counter)


_OnEvent = Callable[[dict], None]


class MediaJobManager:
    """Runs up to ``max_jobs`` ingest jobs; ASR itself is serialized."""

    def __init__(self, on_event: _OnEvent | None = None, *, max_jobs: int = MAX_CONCURRENT_JOBS) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, MediaJob] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._max_jobs = max(1, int(max_jobs))
        # One model, one decoder at a time.
        self._asr_gate = threading.Semaphore(1)
        self._asr_owner: str | None = None
        self._asr_backend: Any | None = None
        self._on_event = on_event or (lambda _e: None)

    @property
    def max_jobs(self) -> int:
        return self._max_jobs

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.status == "running")

    def has_capacity(self) -> bool:
        return self.running_count() < self._max_jobs

    def start(self, source: str, runner: Callable[[MediaJob], dict[str, Any]]) -> MediaJob:
        """Start ``runner`` on a daemon thread; raise ``JOB_BUSY`` when full."""
        from voice_typer.server.media_ingest.errors import JOB_BUSY, MediaIngestError

        with self._lock:
            running = sum(1 for job in self._jobs.values() if job.status == "running")
            if running >= self._max_jobs:
                raise MediaIngestError(
                    JOB_BUSY, f"{self._max_jobs} transcription jobs are already running"
                )
            job = MediaJob(job_id=uuid.uuid4().hex[:12], source=source)
            self._jobs[job.job_id] = job
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
                job.phase = "done"
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
                job.phase = "error"
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
                job.error_code = str(code)
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
                    self._threads.pop(job.job_id, None)
                    self._prune_locked()

        thread = threading.Thread(target=_run, name=f"media-ingest-{job.job_id}", daemon=True)
        with self._lock:
            self._threads[job.job_id] = thread
        thread.start()
        started.wait(timeout=5)
        return job

    def _prune_locked(self) -> None:
        """Drop the oldest finished jobs beyond ``_MAX_FINISHED_KEPT``."""
        finished = [job for job in self._jobs.values() if job.status != "running"]
        excess = len(finished) - _MAX_FINISHED_KEPT
        for job in finished[:excess] if excess > 0 else ():
            self._jobs.pop(job.job_id, None)

    def wait(self, timeout: float = 5.0, *, job_id: str | None = None) -> None:
        """Join one job thread (or all of them) for deterministic reads.

        ``job.status`` flips before the outcome line is logged, so callers
        that read the log or the result must join instead of polling status.
        """
        with self._lock:
            threads = (
                [self._threads[job_id]]
                if job_id is not None and job_id in self._threads
                else list(self._threads.values())
            )
        for thread in threads:
            thread.join(timeout)

    def cancel(self, job_id: str | None = None) -> list[str]:
        """Cancel one job (or every running job); returns the cancelled ids.

        Abort is fired here, not only between windows: a job that currently
        owns the ASR lane is mid-decode, and the engine polls its abort event
        between segments. A job waiting for the lane is never aborted this
        way — the lane owner's decode would be truncated instead.
        """
        with self._lock:
            targets = [
                job
                for job in self._jobs.values()
                if job.status == "running" and (job_id is None or job.job_id == job_id)
            ]
            for job in targets:
                job.cancel_event.set()
            ids = [job.job_id for job in targets]
            owner = self._asr_owner
            backend = self._asr_backend
        if owner is not None and owner in ids and backend is not None:
            abort = getattr(backend, "request_abort", None)
            if callable(abort):
                with suppress(Exception):
                    abort()
        return ids

    def snapshots(self) -> list[dict[str, Any]]:
        """Running-job snapshots in start order (newest finished excluded)."""
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.status == "running"]
        return [
            {
                "job_id": job.job_id,
                "source": job.source,
                "status": job.status,
                "phase": job.phase,
                "progress": job.progress,
                "error": job.error,
            }
            for job in jobs
        ]

    def owns_asr(self, job_id: str) -> bool:
        """True when ``job_id`` currently holds the single ASR lane."""
        with self._lock:
            return self._asr_owner == job_id

    @contextmanager
    def asr_lane(self, job: MediaJob, backend: Any | None = None) -> Iterator[None]:
        """Serialize one decode against the shared model.

        Clearing the abort flag on entry is not cosmetic: a cancelled job
        leaves it set, and the engine only checks it BETWEEN segments, so a
        stale flag silently truncates the next job's first window.
        """
        self._asr_gate.acquire()
        try:
            with self._lock:
                self._asr_owner = job.job_id
                self._asr_backend = backend
            clear = getattr(backend, "clear_abort", None)
            if callable(clear):
                with suppress(Exception):
                    clear()
            yield
        finally:
            with self._lock:
                if self._asr_owner == job.job_id:
                    self._asr_owner = None
                    self._asr_backend = None
            self._asr_gate.release()

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
