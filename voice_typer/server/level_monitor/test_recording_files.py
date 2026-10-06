"""Mic-test WAV disk transport: recordings dir, persist, TTL expiry, slices.

Split from ``voice_typer/server/level_monitor/test_recording.py``
(create-first); the facade re-exports every name so the historical import
path keeps resolving. ``_test_recordings_dir`` is resolved through the
facade at call time because tests monkeypatch it there.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import threading
import time
import uuid
from pathlib import Path

from voice_typer.server._lazy_import import lazy_module

# Call-time facade access: tests patch ``_test_recordings_dir`` on the
# facade, so same-module callers must re-resolve it there (never by value).
_facade = lazy_module("voice_typer.server.level_monitor.test_recording")

log = logging.getLogger("voice_typer.server.level_monitor")

# The completed test's WAV payloads are ~0.9 MB each (10 s @ 44.1/48 kHz
_TEST_RECORDINGS_DIRNAME = "mic-test-recordings"

# Mic-test WAV disk TTL: auto-delete a test's persisted WAVs this many
MIC_TEST_RECORDING_TTL_SEC = 300

# Live per-file expiry timers (threading.Timer, daemon like
_test_recording_expiry_timers: set[threading.Timer] = set()


def _test_recordings_dir() -> Path:
    """Return (and create) the mic-test recordings dir under the config dir."""
    from voice_typer.server.config_internals.paths import _config_dir

    d = Path(_config_dir()) / _TEST_RECORDINGS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        _delete_expired_recordings()
    return d


def _remove_recordings_dir_if_empty() -> None:
    """Best-effort remove of the recordings dir when it holds no files."""
    try:
        from voice_typer.server.config_internals.paths import _config_dir

        with contextlib.suppress(OSError):
            (Path(_config_dir()) / _TEST_RECORDINGS_DIRNAME).rmdir()
    except Exception:
        log.debug("[LEVEL-MON] recordings-dir remove failed", exc_info=True)


def _purge_test_recordings() -> None:
    """Best-effort delete of leftover test WAVs from previous tests."""
    try:
        d = _facade._test_recordings_dir()
        for pattern in ("*.wav", "*.wav.tmp"):
            for f in d.glob(pattern):
                try:
                    f.unlink()
                except OSError:
                    log.debug("[LEVEL-MON] could not unlink leftover test WAV: %s", f)
        _remove_recordings_dir_if_empty()
    except Exception:
        log.debug("[LEVEL-MON] test-recording purge failed", exc_info=True)


def _delete_test_recording_paths(paths) -> None:
    """Best-effort unlink of exactly the given persisted WAV paths."""
    try:
        targets = [str(p) for p in (paths or []) if p]
        if not targets:
            return
        deleted = 0
        for p in targets:
            try:
                Path(p).unlink()
                deleted += 1
            except FileNotFoundError:
                continue
            except OSError:
                log.debug("[LEVEL-MON] could not unlink expired test WAV: %s", p)
        log.debug(
            "[LEVEL-MON] expired mic-test WAV delete: %d/%d files removed",
            deleted,
            len(targets),
        )
        _remove_recordings_dir_if_empty()
    except Exception:
        log.debug("[LEVEL-MON] expired mic-test WAV delete failed", exc_info=True)


def _schedule_test_recording_expiry(paths, ttl_sec: float = MIC_TEST_RECORDING_TTL_SEC) -> threading.Timer | None:
    """Schedule best-effort deletion of exactly *paths* after *ttl_sec*.

    Mirrors the _test_auto_stop_timer daemon pattern. Never raises.
    """
    try:
        targets = [str(p) for p in (paths or []) if p]
        if not targets:
            return None
        timer: threading.Timer | None = None

        def _fire() -> None:
            try:
                _delete_test_recording_paths(targets)
            finally:
                with contextlib.suppress(Exception):
                    _test_recording_expiry_timers.discard(timer)

        timer = threading.Timer(ttl_sec, _fire)
        timer.daemon = True
        _test_recording_expiry_timers.add(timer)
        timer.start()
        log.debug(
            "[LEVEL-MON] scheduled mic-test WAV expiry in %ss for %d files",
            ttl_sec,
            len(targets),
        )
        return timer
    except Exception:
        log.debug("[LEVEL-MON] failed to schedule mic-test WAV expiry", exc_info=True)
        return None


def _delete_expired_recordings(max_age_sec: float = MIC_TEST_RECORDING_TTL_SEC) -> int:
    """Best-effort unlink of mic-test WAVs older than *max_age_sec* by mtime."""
    try:
        from voice_typer.server.config_internals.paths import _config_dir

        d = Path(_config_dir()) / _TEST_RECORDINGS_DIRNAME
        if not d.is_dir():
            return 0
        now = time.time()
        deleted = 0
        for pattern in ("*.wav", "*.wav.tmp"):
            try:
                files = list(d.glob(pattern))
            except OSError:
                continue
            for f in files:
                try:
                    if now - f.stat().st_mtime > max_age_sec:
                        f.unlink()
                        deleted += 1
                except FileNotFoundError:
                    continue
                except OSError:
                    log.debug("[LEVEL-MON] could not unlink expired test WAV: %s", f)
        if deleted:
            log.debug("[LEVEL-MON] expired mic-test WAV sweep removed %d files", deleted)
        _remove_recordings_dir_if_empty()
        return deleted
    except Exception:
        log.debug("[LEVEL-MON] expired mic-test WAV sweep failed", exc_info=True)
        return 0


def _write_test_wav(buf: io.BytesIO, kind: str) -> dict | None:
    """Write *buf*'s WAV bytes to a unique file; return {"path","bytes"}.

    Returns None when the payload is empty (nothing to persist). The
    """
    data = buf.getvalue()
    if not data:
        return None
    d = _facade._test_recordings_dir()
    # Re-ensure: the TTL sweep inside _test_recordings_dir() may have
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"test-{kind}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.wav"
    tmp = path.with_suffix(".wav.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    from voice_typer.server.platform_utils import is_windows

    if not is_windows():
        # POSIX only: keep biometric voice data owner-readable.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
    return {"path": str(path), "bytes": len(data)}


def read_test_recording_slice(path: str, offset: int, length: int) -> dict:
    """Return a base64 slice [offset, offset+length) of a test WAV file."""
    import base64 as _b64

    try:
        requested = Path(path)
        root = _facade._test_recordings_dir().resolve()
        resolved = requested.resolve()
        if resolved.parent != root or resolved.suffix.lower() != ".wav":
            return {
                "success": False,
                "data_b64": "",
                "bytes_read": 0,
                "total_bytes": 0,
                "eof": True,
                "message": "path outside microphone-test recordings",
            }
        if not resolved.is_file():
            return {
                "success": False,
                "data_b64": "",
                "bytes_read": 0,
                "total_bytes": 0,
                "eof": True,
                "message": "recording not found",
            }
        total = resolved.stat().st_size
        length = max(0, min(int(length), 256 * 1024))
        # BASE64-SAFE SLICING INVARIANT: every NON-FINAL slice must be a
        length -= length % 3
        offset = max(0, int(offset))
        remaining = total - offset
        if remaining <= 0:
            return {
                "success": True,
                "data_b64": "",
                "bytes_read": 0,
                "total_bytes": total,
                "eof": True,
                "message": "ok",
            }
        if length == 0:
            # Requests of 1-2 bytes align down to a 0-byte slice, which
            length = 3 if remaining >= 3 else remaining
        with open(resolved, "rb") as fh:
            fh.seek(offset)
            chunk = fh.read(length)
        return {
            "success": True,
            "data_b64": _b64.b64encode(chunk).decode("ascii"),
            "bytes_read": len(chunk),
            "total_bytes": total,
            "eof": offset + len(chunk) >= total,
            "message": "ok",
        }
    except Exception as exc:
        log.warning("[LEVEL-MON] read_test_recording_slice failed: %s", exc)
        return {
            "success": False,
            "data_b64": "",
            "bytes_read": 0,
            "total_bytes": 0,
            "eof": True,
            "message": type(exc).__name__,
        }
