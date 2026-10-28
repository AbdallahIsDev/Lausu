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

Cancellation is SCOPED. Each job owns a `cancel_event`, and that Event is
threaded into the job's own decode call as its abort source, so cancelling a
job stops its window between segments and touches nothing else — not another
media job, not an in-flight dictation recording. The engine's single shared
`_abort_event` is never fired or cleared from here: one shared flag is exactly
how a cancel used to truncate whichever decode happened to be running.
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


@dataclass
class MediaJob:
    """One background ingest job."""

    job_id: str
    source: str
    status: str = "running"
    # Coarse stage the renderer shows before its first progress push.
    phase: str = "starting"
    progress: float = 0.0
    # Renderer-generated correlation token, echoed on every event this job
    # publishes. It is what lets the renderer bind a push to the exact row
    # it created, including a push that beats the start ack.
    client_id: str | None = None
    # Where this job writes its transcript, when the caller asked for an
    # export. Two running jobs must never share one destination: they would
    # write over each other and the survivor's content would be arbitrary.
    export_path: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    started_at: float = field(default_factory=time.perf_counter)


_OnEvent = Callable[[dict], None]


class MediaJobManager:
    """Runs up to ``max_jobs`` ingest jobs; ASR itself is serialized.

    The registry holds RUNNING jobs only: a job is dropped from ``_jobs`` the
    moment its thread finishes. Finished state is not re-read from here —
    ``snapshots()`` feeds mount-time hydration for jobs the user can still
    see as in-flight, and the outcome of a finished job reaches the renderer
    through its completion/error event (plus the durable log line).
    """

    def __init__(self, on_event: _OnEvent | None = None, *, max_jobs: int = MAX_CONCURRENT_JOBS) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, MediaJob] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._max_jobs = max(1, int(max_jobs))
        # One model, one decoder at a time.
        self._asr_gate = threading.Semaphore(1)
        self._on_event = on_event or (lambda _e: None)

    @property
    def max_jobs(self) -> int:
        return self._max_jobs

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.status == "running")

    def has_capacity(self) -> bool:
        return self.running_count() < self._max_jobs

    def start(
        self,
        source: str,
        runner: Callable[[MediaJob], dict[str, Any]],
        *,
        client_id: str | None = None,
        export_path: str | None = None,
    ) -> MediaJob:
        """Start ``runner`` on a daemon thread; raise ``JOB_BUSY`` when full.

        ``client_id`` is the renderer's own correlation token; it is echoed on
        every event so the renderer can bind a push to the row it created
        without guessing which of several in-flight starts it belongs to.
        ``export_path`` is recorded so a second job cannot be pointed at the
        same destination while this one is still writing there.
        """
        from voice_typer.server.media_ingest.errors import JOB_BUSY, MediaIngestError

        with self._lock:
            running = sum(1 for job in self._jobs.values() if job.status == "running")
            if running >= self._max_jobs:
                raise MediaIngestError(
                    JOB_BUSY, f"{self._max_jobs} transcription jobs are already running"
                )
            job = MediaJob(
                job_id=uuid.uuid4().hex[:12],
                source=source,
                client_id=client_id,
                export_path=export_path,
            )
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
                            "data": {
                                "job_id": job.job_id,
                                "client_id": job.client_id,
                                "code": str(code),
                                "message": job.error,
                            },
                        }
                    )
            finally:
                with self._lock:
                    self._threads.pop(job.job_id, None)
                    # Finished jobs are not re-readable: the outcome has
                    # already been published (event + log line), so keeping
                    # the object would only grow the registry for the life of
                    # the process.
                    self._jobs.pop(job.job_id, None)

        thread = threading.Thread(target=_run, name=f"media-ingest-{job.job_id}", daemon=True)
        with self._lock:
            self._threads[job.job_id] = thread
        thread.start()
        started.wait(timeout=5)
        return job

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

        Only ``job.cancel_event`` is set. That Event is the SCOPED abort
        source threaded into the job's own decode call, so the engine stops
        this job's window between segments and nothing else: not another
        media job, and not an in-flight dictation recording. The engine-wide
        ``request_abort()`` is deliberately NOT fired — it is a single shared
        flag, and firing it here was the cross-talk that silently truncated
        whichever decode happened to be running.
        """
        with self._lock:
            targets = [
                job
                for job in self._jobs.values()
                if job.status == "running" and (job_id is None or job.job_id == job_id)
            ]
            for job in targets:
                job.cancel_event.set()
            return [job.job_id for job in targets]

    def snapshots(self) -> list[dict[str, Any]]:
        """Running-job snapshots in start order (finished jobs are not kept)."""
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.status == "running"]
        return [
            {
                "job_id": job.job_id,
                "client_id": job.client_id,
                "source": job.source,
                "status": job.status,
                "phase": job.phase,
                "progress": job.progress,
                "error": job.error,
            }
            for job in jobs
        ]

    def export_path_in_use(self, export_path: str) -> bool:
        """True when a RUNNING job already writes to ``export_path``."""
        with self._lock:
            return any(
                job.status == "running" and job.export_path == export_path
                for job in self._jobs.values()
            )

    @contextmanager
    def asr_lane(self, job: MediaJob) -> Iterator[None]:
        """Serialize one decode against the shared model.

        The lane deliberately does NOT touch the engine's abort flag. Media
        decodes poll ``job.cancel_event`` (a scoped source threaded into the
        decode call), so a stale engine-wide flag — set by a dictation cancel
        — can no longer truncate a media window, and clearing it here would
        swallow that dictation cancel instead.
        """
        self._asr_gate.acquire()
        try:
            yield
        finally:
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
