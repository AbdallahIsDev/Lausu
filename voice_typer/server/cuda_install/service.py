"""Single-flight CUDA install job: download → verify → install → pending.

Progress is a sticky-notification contract: every state change publishes
``cuda_progress`` so the renderer's persistent toast survives navigation and
never has to poll. The job never touches ``config.device``; it writes the
pending activation record and the respawned sidecar proves the stack.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time

from voice_typer.server.cuda_install import installer, state
from voice_typer.server.cuda_install.downloader import (
    CancelledError,
    DownloadError,
    download,
    verify_file,
)
from voice_typer.server.cuda_install.installer import InstallError
from voice_typer.server.cuda_install.manifest import (
    Artifact,
    artifacts_for_current_runtime,
    total_bytes,
)
from voice_typer.server.cuda_install.paths import cuda_root, downloads_dir
from voice_typer.server.duration import format_duration
from voice_typer.server.platform_utils import is_windows

log = logging.getLogger(__name__)

IDLE = "idle"
DOWNLOADING = "downloading"
VERIFYING = "verifying"
INSTALLING = "installing"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"

# Headroom on top of the artifact bytes: extraction needs room for the
# expanded tree while the wheels are still on disk.
_DISK_HEADROOM_BYTES = 1024 * 1024 * 1024
_EMIT_INTERVAL_S = 0.1
_SPEED_WINDOW_S = 3.0


class CudaInstallService:
    """Owns the one live CUDA install job for this process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = IDLE
        self._error: str | None = None
        self._artifact: str | None = None
        self._artifact_index = 0
        self._artifact_count = 0
        self._bytes_done = 0
        self._bytes_total = 0
        self._started_at = 0.0
        self._last_emit = 0.0
        self._speed = 0.0
        self._speed_mark_bytes = 0
        self._speed_mark_at = 0.0

    # ---- public API -------------------------------------------------

    def start(self) -> dict:
        """Start the install, or return the running job's snapshot."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._snapshot_locked()
            artifacts = artifacts_for_current_runtime()
            if not artifacts:
                return self._fail_locked("unsupported_python")
            if not is_windows():
                return self._fail_locked("unsupported_platform")
            needed = total_bytes(artifacts)
            try:
                cuda_root().mkdir(parents=True, exist_ok=True)
                free = shutil.disk_usage(str(cuda_root())).free
            except OSError:
                return self._fail_locked("disk_unavailable")
            if free < needed + _DISK_HEADROOM_BYTES:
                return self._fail_locked("insufficient_disk")
            self._cancel = threading.Event()
            self._status = DOWNLOADING
            self._error = None
            self._artifact = None
            self._artifact_index = 0
            self._artifact_count = len(artifacts)
            self._bytes_done = 0
            self._bytes_total = needed
            self._started_at = time.monotonic()
            self._speed = 0.0
            self._speed_mark_bytes = 0
            self._speed_mark_at = self._started_at
            self._last_emit = 0.0
            self._thread = threading.Thread(
                target=self._run,
                args=(artifacts,),
                name="cuda-install",
                daemon=True,
            )
            self._thread.start()
            snapshot = self._snapshot_locked()
        self._emit(snapshot)
        log.info("[CUDA] install started: %d artifacts, %d bytes", len(artifacts), needed)
        return snapshot

    def cancel(self) -> dict:
        """Ask the running job to stop at the next chunk boundary."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                return self._snapshot_locked()
            self._cancel.set()
            return self._snapshot_locked()

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_locked()

    # ---- job --------------------------------------------------------

    def _run(self, artifacts: tuple[Artifact, ...]) -> None:
        _t0 = time.monotonic()
        try:
            wheels = {}
            base = 0
            for index, artifact in enumerate(artifacts):
                self._set_artifact(index, artifact.key)
                cached = downloads_dir() / artifact.filename
                if verify_file(artifact, cached, self._cancel):
                    base += artifact.size
                    self._set_bytes(base)
                    wheels[artifact.key] = cached
                    continue
                wheels[artifact.key] = download(
                    artifact,
                    downloads_dir(),
                    cancel=self._cancel,
                    on_bytes=lambda written, base=base: self._set_bytes(base + written),
                )
                base += artifact.size
                self._set_bytes(base)

            self._set_status(VERIFYING)
            self._set_status(INSTALLING)
            installer.install(artifacts, wheels)
            state.write_pending([a.filename for a in artifacts])
            self._set_status(COMPLETED)
            log.info(
                "[CUDA] install completed and verified, activation pending%s",
                format_duration(time.monotonic() - _t0),
            )
        except CancelledError:
            self._set_status(CANCELLED)
            log.info("[CUDA] install cancelled by user%s", format_duration(time.monotonic() - _t0))
        except DownloadError as exc:
            self._fail(exc.code, exc.detail, _t0)
        except InstallError as exc:
            self._fail(exc.code, exc.detail, _t0)
        except Exception as exc:  # never leave the sticky toast spinning
            log.exception("[CUDA] install failed unexpectedly")
            self._fail("internal", str(exc), _t0)

    def _set_artifact(self, index: int, key: str) -> None:
        with self._lock:
            self._artifact_index = index
            self._artifact = key
        self._emit(self.snapshot())

    def _set_bytes(self, value: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._bytes_done = max(0, min(value, self._bytes_total))
            elapsed = now - self._speed_mark_at
            if elapsed >= _SPEED_WINDOW_S:
                delta = self._bytes_done - self._speed_mark_bytes
                self._speed = delta / elapsed if elapsed > 0 else 0.0
                self._speed_mark_bytes = self._bytes_done
                self._speed_mark_at = now
        self._emit(self.snapshot(), force=False)

    def _set_status(self, status: str) -> None:
        with self._lock:
            self._status = status
        self._emit(self.snapshot(), force=True)

    def _fail(self, code: str, detail: str, started_at: float) -> None:
        with self._lock:
            self._status = FAILED
            self._error = code
        log.warning(
            "[CUDA] install failed: %s (%s)%s",
            code,
            detail or "no detail",
            format_duration(time.monotonic() - started_at),
        )
        self._emit(self.snapshot(), force=True)

    def _fail_locked(self, code: str) -> dict:
        self._status = FAILED
        self._error = code
        snapshot = self._snapshot_locked()
        self._emit(snapshot, force=True)
        return snapshot

    # ---- plumbing ---------------------------------------------------

    def _emit(self, snapshot: dict, *, force: bool = True) -> None:
        now = time.monotonic()
        if not force and now - self._last_emit < _EMIT_INTERVAL_S:
            return
        self._last_emit = now
        try:
            from voice_typer.server import event_bus

            event_bus.publish({"type": "cuda_progress", "data": snapshot})
        except Exception:
            log.debug("[CUDA] progress publish failed", exc_info=True)

    def _snapshot_locked(self) -> dict:
        total = self._bytes_total
        done = self._bytes_done
        percent = round(done * 100.0 / total, 1) if total else 0.0
        eta = None
        if self._speed > 0 and total > done:
            eta = int((total - done) / self._speed)
        return {
            "status": self._status,
            "artifact": self._artifact,
            "artifact_index": self._artifact_index,
            "artifact_count": self._artifact_count,
            "bytes_done": done,
            "bytes_total": total,
            "percent": percent,
            "speed_bps": int(self._speed),
            "eta_seconds": eta,
            "error": self._error,
        }


_service: CudaInstallService | None = None
_service_lock = threading.Lock()


def get_service() -> CudaInstallService:
    """Process-wide install service (one live job at a time)."""
    global _service
    with _service_lock:
        if _service is None:
            _service = CudaInstallService()
        return _service
