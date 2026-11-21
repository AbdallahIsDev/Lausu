"""ffmpeg-backed decode to 16 kHz mono float32 chunks (ADR-0023 tiers 0/1/4).

One ffmpeg process per job, stdout streamed as raw ``pcm_f32le``; the process
is always terminated and reaped when the generator is closed or fails.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from voice_typer.server.autostart._spawn_env import _spawn_flags
from voice_typer.server.media_ingest import ffmpeg_binaries

log = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16_000
CHUNK_SAMPLES = TARGET_SAMPLE_RATE * 5
CHUNK_BYTES = CHUNK_SAMPLES * 4
_READ_BLOCK_BYTES = CHUNK_BYTES
_LOCAL_PROTOCOLS = "file"
_REMOTE_PROTOCOLS = "http,https,tcp,tls,crypto"
_STDERR_TAIL_LINES = 64
# ffmpeg prefixes each line with "[in#0 @ HEXADDR]"; bare digit runs there
# collide with the HTTP-status patterns in the error taxonomy.
_LOG_CONTEXT_RE = re.compile(r"\[[^\]]*@[^\]]*\]")
# ffmpeg prints the container header (including this line) to stderr when it
# is given an input and no output. ffprobe is NOT needed for a duration read.
_DURATION_LINE_RE = re.compile(r"\bDuration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)", re.IGNORECASE)
_REMOTE_AUDIO_STREAM_RE = re.compile(r"^\s*Stream #\d+:\d+[^:]*: Audio:", re.MULTILINE)
_TERM_TIMEOUT_SECONDS = 5.0
_KILL_TIMEOUT_SECONDS = 2.0
_DRAIN_JOIN_SECONDS = 2.0
# Kept for callers/tests that pinned the old timeouts; ffmpeg uses seconds.
OPEN_TIMEOUT_US = 15_000_000
READ_TIMEOUT_US = 30_000_000

_NO_AUDIO_PATTERNS = (
    "matches no streams",
    "no audio stream",
    "does not contain any audio",
)
_EXPIRED_PATTERNS = ("403", "forbidden", "access denied")
_STALLED_PATTERNS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "timed out",
    "timeout",
    "network is unreachable",
    "connection reset",
    "connection refused",
    "temporarily unavailable",
)


def _protocols(remote: bool) -> str:
    return _REMOTE_PROTOCOLS if remote else _LOCAL_PROTOCOLS


def _input_arg(source: str, *, remote: bool) -> str:
    """Prefix local paths with ``file:`` so a leading ``-`` is never an option."""
    if remote:
        return source
    return source if source.startswith("file:") else "file:" + str(Path(source))


def _check_remote_scheme(source: str) -> None:
    from voice_typer.server.media_ingest.errors import DECODE_FAILED, MediaIngestError

    if urlparse(source).scheme.lower() not in ("http", "https"):
        raise MediaIngestError(DECODE_FAILED, "This media link cannot be opened. Check the link and try again.")


def _decode_argv(ffmpeg: str, source: str, *, remote: bool, start_seconds: float) -> list[str]:
    argv = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-protocol_whitelist",
        _protocols(remote),
    ]
    if start_seconds > 0:
        argv += ["-ss", f"{start_seconds:.6f}"]
    argv += [
        "-i",
        _input_arg(source, remote=remote),
        "-vn",
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-c:a",
        "pcm_f32le",
        "-f",
        "f32le",
        "-",
    ]
    return argv


@contextmanager
def _managed_process(argv: list[str]) -> Iterator[tuple[subprocess.Popen, deque[str]]]:
    """Run ffmpeg with a bounded stderr tail; always terminate and reap."""
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **_spawn_flags(hidden=True),
    )
    tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)

    def _drain() -> None:
        try:
            assert proc.stderr is not None
            for raw in iter(proc.stderr.readline, b""):
                tail.append(raw.decode("utf-8", "replace").rstrip())
        except (OSError, ValueError):
            pass  # the pipe was closed by teardown

    # RACE-008: the bounded stderr reader must never keep the process alive;
    # it only follows a pipe that we close in the finally block below.
    reader = threading.Thread(target=_drain, name="media-ffmpeg-stderr", daemon=True)
    reader.start()
    try:
        yield proc, tail
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=_TERM_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=_KILL_TIMEOUT_SECONDS)
        else:
            proc.wait()  # reap: never leave a zombie behind
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                with suppress(OSError):
                    stream.close()
        reader.join(timeout=_DRAIN_JOIN_SECONDS)


def _ffmpeg_usable(path: str) -> bool:
    """Production gate: the resolved ffmpeg must exist and be executable."""
    candidate = Path(path)
    try:
        return candidate.is_file() and os.access(candidate, os.X_OK)
    except OSError:
        return False


def decode_chunks(
    source: str,
    *,
    remote: bool = False,
    start_seconds: float = 0.0,
    cancel_event: Any | None = None,
) -> Iterator[Any]:
    """Yield mono float32 16 kHz chunks from a local file or remote URL.

    ``start_seconds`` skips already-transcribed audio so a stalled stream can
    resume without duplicating text. ``cancel_event`` is the CALLER's scoped
    Event (never the engine-wide abort flag, C-MEDIA-2): when it flips, or the
    consumer closes this generator, ffmpeg is terminated and reaped.
    """
    from voice_typer.server.media_ingest.errors import DECODE_FAILED, MediaIngestError

    if remote:
        _check_remote_scheme(source)
    elif not Path(source).is_file():
        raise MediaIngestError(DECODE_FAILED, f"media file not found: {source}")

    binaries = ffmpeg_binaries.resolve_binaries()
    if binaries is None or not _ffmpeg_usable(binaries.ffmpeg):
        from voice_typer.server.media_ingest.errors import FFMPEG_MISSING

        raise MediaIngestError(
            FFMPEG_MISSING,
            "Audio decoding is unavailable. Reinstall the app to restore it.",
        )

    argv = _decode_argv(binaries.ffmpeg, source, remote=remote, start_seconds=start_seconds)
    log.info(
        "[MEDIA] ingest: remote=%s seek=%.3f argv=%s",
        remote,
        start_seconds,
        " ".join(argv[1:]),
    )
    import numpy as np

    pending = bytearray()
    with _managed_process(argv) as (proc, tail):
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    break
                assert proc.stdout is not None
                block = proc.stdout.read(_READ_BLOCK_BYTES)  # bounded: never a whole-file load
                if not block:
                    break
                pending.extend(block)
                while len(pending) >= CHUNK_BYTES:
                    raw = bytes(pending[:CHUNK_BYTES])
                    del pending[:CHUNK_BYTES]
                    yield np.frombuffer(raw, dtype=np.float32).copy()
        except (OSError, ValueError):  # a closed pipe/partial read ends the stream
            log.debug("[MEDIA] ffmpeg stdout ended early", exc_info=True)
        # stdout EOF can precede process exit: wait before deciding success.
        try:
            rc = proc.wait(timeout=_TERM_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            rc = None
        if rc not in (0, None) and not (cancel_event is not None and cancel_event.is_set()):
            stderr = _LOG_CONTEXT_RE.sub("", "\n".join(tail))
            raise _classify_ffmpeg_failure(rc, stderr, remote=remote)
        usable = len(pending) - (len(pending) % 4)
        if usable:
            yield np.frombuffer(bytes(pending[:usable]), dtype=np.float32).copy()
        elif pending:
            log.warning("[MEDIA] ffmpeg emitted %d trailing bytes (not whole float32 samples)", len(pending))


@dataclass(frozen=True)
class RemoteProbe:
    """What a remote URL proved about itself before we streamed it.

    ``audio_streams`` is the count ffprobe found (a web page served as HTML
    has none) and ``duration_seconds`` is the container-header duration,
    which a stream tier needs for percent/ETA and the truncation gate.
    """

    audio_streams: int
    duration_seconds: float | None


def _duration_probe_argv(ffmpeg: str, source: str, *, remote: bool) -> list[str]:
    """Input-only ffmpeg: stderr carries the container header, no decode pass."""
    return [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-protocol_whitelist",
        _protocols(remote),
        "-i",
        _input_arg(source, remote=remote),
    ]


def _run_duration_probe(argv: list[str], timeout: float) -> str | None:
    """Run the info-only ffmpeg probe; read stderr even on its expected non-zero exit.

    ``ffmpeg -i SRC`` with no output ends with "At least one output file must
    be specified" (rc=1) AFTER printing the Duration line, so unlike
    ``_run_probe`` we must not discard output on a non-zero return code.
    """
    try:
        completed: subprocess.CompletedProcess[bytes] = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            **_spawn_flags(hidden=True),
        )
    except (OSError, subprocess.TimeoutExpired):
        log.debug("[MEDIA] ffmpeg duration probe failed to run", exc_info=True)
        return None
    return completed.stderr.decode("utf-8", "replace")


def _duration_from_ffmpeg_log(log_text: str) -> float | None:
    """Parse ``Duration: HH:MM:SS.ss`` from ffmpeg's stderr (N/A → None)."""
    match = _DURATION_LINE_RE.search(log_text)
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    try:
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, OverflowError):
        return None


def probe_remote(url: str) -> RemoteProbe | None:
    """Probe a resolved URL without decoding it; ``None`` when unusable.

    Streaming is the FALLBACK tier; an expired CDN link, a web page, or a
    non-HTTP scheme must never reach it (that would be a silent zero-chunk
    "success"). One ffprobe call, no decode pass.
    """
    if urlparse(url).scheme.lower() not in ("http", "https"):
        return None
    binaries = ffmpeg_binaries.resolve_binaries()
    if binaries is None or not _ffmpeg_usable(binaries.ffmpeg):
        return None
    argv = _duration_probe_argv(binaries.ffmpeg, url, remote=True)
    log_text = _run_duration_probe(argv, READ_TIMEOUT_US / 1_000_000.0)
    if log_text is None:
        return None
    audio = len(_REMOTE_AUDIO_STREAM_RE.findall(log_text))
    return RemoteProbe(audio_streams=audio, duration_seconds=_duration_from_ffmpeg_log(log_text))


def probe_duration_seconds(source: str, *, remote: bool = False) -> float | None:
    """Container duration in seconds, or ``None`` when unknown (best effort).

    Local jobs need a total for fraction/ETA; URL jobs get it from the
    resolver. ffmpeg prints ``Duration: HH:MM:SS.ss`` while reading the
    header, so no ffprobe binary and no decode pass are needed. The protocol
    whitelist and timeouts are the same ones every other ffmpeg call uses.
    """
    if remote and urlparse(source).scheme.lower() not in ("http", "https"):
        return None
    binaries = ffmpeg_binaries.resolve_binaries()
    if binaries is None or not binaries.ffmpeg:
        return None
    argv = _duration_probe_argv(binaries.ffmpeg, source, remote=remote)
    stderr = _run_duration_probe(argv, (READ_TIMEOUT_US if remote else OPEN_TIMEOUT_US) / 1_000_000.0)
    if stderr is None:
        return None
    return _duration_from_ffmpeg_log(stderr)


def _classify_stream_error(exc: Exception, *, context: str) -> Any:
    """Map a transport exception to the ADR-0023 stall/expiry taxonomy."""
    from voice_typer.server.media_ingest.errors import (
        DECODE_FAILED,
        STREAM_STALLED,
        URL_EXPIRED,
        MediaIngestError,
    )

    text = f"{type(exc).__name__}: {exc}".lower()
    if isinstance(exc, TimeoutError) or any(p in text for p in _STALLED_PATTERNS):
        return MediaIngestError(STREAM_STALLED, "media stream timed out")
    if any(p in text for p in _EXPIRED_PATTERNS):
        return MediaIngestError(URL_EXPIRED, "media link expired")
    verb = "could not open media" if context == "open" else "decode failed"
    return MediaIngestError(DECODE_FAILED, f"{verb}: {exc}")


def _classify_ffmpeg_failure(returncode: int, stderr: str, *, remote: bool) -> Any:
    """Map ffmpeg's exit/stderr onto the existing user-safe error codes."""
    from voice_typer.server.media_ingest.errors import (
        DECODE_FAILED,
        NO_AUDIO,
        STREAM_STALLED,
        URL_EXPIRED,
        MediaIngestError,
    )

    text = stderr.lower()
    log.warning("[MEDIA] ffmpeg exit=%d remote=%s stderr=%s", returncode, remote, stderr[-1024:])
    if any(p in text for p in _NO_AUDIO_PATTERNS):
        return MediaIngestError(NO_AUDIO, "No audio track was found in this media. Try another file.")
    if any(p in text for p in _EXPIRED_PATTERNS):
        return MediaIngestError(URL_EXPIRED, "This media link has expired. Try the link again.")
    if any(p in text for p in _STALLED_PATTERNS):
        return MediaIngestError(STREAM_STALLED, "The media connection stalled. Check your connection and try again.")
    return MediaIngestError(
        DECODE_FAILED, "This media file could not be decoded. Try a different file or re-download it."
    )
