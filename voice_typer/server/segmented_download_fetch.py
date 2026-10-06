"""Segment fetching and the segmented download orchestrator.

Owns ``_fetch_segment`` (resume + retry + pause/cancel gate), the
interruptible backoff wrapper, and ``download_file_segmented`` (state
reconciliation, bounded thread pool, mark-done state writes, assembly +
sha256 verification). Moved verbatim out of
``voice_typer.server.segmented_download`` (which re-exports every name).
``RETRY_BACKOFF_S`` / ``_is_transient_http`` are read through the facade
at call time because tests patch them on ``segmented_download``.
"""

from __future__ import annotations

import concurrent.futures
import errno
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.branding import APP_NAME
from voice_typer.server.retry import (
    delay_for_attempt,
    sleep_interruptible as _shared_sleep_interruptible,
)
from voice_typer.server.segmented_download_base import (
    MAX_SEGMENTS,
    READ_CHUNK_BYTES,
    REQUEST_TIMEOUT_S,
    SEGMENT_ATTEMPTS,
    SEGMENT_TARGET_BYTES,
    GateCheck,
    ProgressCb,
    SegmentedDownloadError,
    SegmentRange,
    plan_segments,
)
from voice_typer.server.segmented_download_http import (
    _body_matches_segment,
    _make_request,
    _parse_retry_after,
    _RangeUnsupportedError,
    _status_of,
    build_opener,
)
from voice_typer.server.segmented_download_state import (
    _assemble_and_verify,
    _discard_resume_state,
    _reconcile_state,
    _safe_filename,
    part_path_for,
    read_state,
    state_matches,
    state_path_for,
    write_state,
)

# Lazy proxy: the facade imports this module, so a direct import would be
# circular; the proxy also makes test monkeypatching of the facade's
# retry knobs visible here at call time.
_dl = lazy_module("voice_typer.server.segmented_download")


def _sleep_interruptible(delay_s: float, gate_check: GateCheck | None) -> None:
    """Sleep, but wake promptly for cancel (and park on pause)."""
    # Chunked gate polling lives in the shared helper; same 0.2s cadence.
    _shared_sleep_interruptible(delay_s, gate_check=gate_check)


def _fetch_segment(
    *,
    opener: Any,
    url: str,
    seg: SegmentRange,
    part_path: Path,
    headers: dict[str, str],
    timeout_s: float,
    gate_check: GateCheck | None,
    on_bytes: Callable[[int], None],
) -> int:
    """Fetch one segment with resume + retry. Returns bytes written."""
    offset = part_path.stat().st_size if part_path.exists() else 0
    if offset > seg.length:
        # Torn state (part longer than its segment), restart it.
        part_path.unlink(missing_ok=True)
        offset = 0
    if offset == seg.length:
        return 0  # already complete (verified by caller)

    last_error: Exception | None = None
    for attempt in range(SEGMENT_ATTEMPTS):
        if gate_check is not None:
            gate_check()
        req_headers = dict(headers)
        req_headers["Range"] = f"bytes={seg.start + offset}-{seg.end}"
        try:
            with opener.open(_make_request(url, req_headers), timeout=timeout_s) as resp:
                status = _status_of(resp)
                if _dl._is_transient_http(status):
                    delay = _parse_retry_after(resp.getheader("Retry-After"))
                    if delay <= 0:
                        delay = delay_for_attempt(_dl.RETRY_BACKOFF_S, attempt)
                    _sleep_interruptible(delay, gate_check)
                    last_error = SegmentedDownloadError(f"HTTP {status}")
                    continue
                if status == 416:
                    # Range unsatisfiable: our offset is likely already
                    if part_path.exists() and part_path.stat().st_size >= seg.length:
                        return 0
                    offset = 0
                    part_path.unlink(missing_ok=True)
                    last_error = SegmentedDownloadError("HTTP 416")
                    continue
                if status == 200 and (offset > 0 or not _body_matches_segment(resp, seg)):
                    # Server ignored Range: only acceptable when the body
                    raise _RangeUnsupportedError("server ignored Range request (HTTP 200)")
                if status not in (200, 206):
                    raise SegmentedDownloadError(f"unexpected HTTP {status}")
                expected = seg.length - offset
                got = 0
                mode = "ab" if offset > 0 else "wb"
                with open(part_path, mode) as f:
                    while True:
                        if gate_check is not None:
                            gate_check()
                        chunk = resp.read(READ_CHUNK_BYTES)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        on_bytes(len(chunk))
                if got < expected:
                    # Truncated stream (dropped connection): resume on
                    offset = part_path.stat().st_size
                    last_error = SegmentedDownloadError(f"truncated segment {seg.index}: got {got}/{expected}")
                    continue
                return got
        except OSError as e:
            if e.errno == errno.ENOSPC:
                raise  # disk-full is fatal, never retried
            last_error = e
            _sleep_interruptible(delay_for_attempt(_dl.RETRY_BACKOFF_S, attempt), gate_check)
        except Exception as e:  # noqa: BLE001, transport errors retried uniformly
            # NOTE: ModelDownloadAborted is a BaseException, so it is NOT
            last_error = e
            _sleep_interruptible(delay_for_attempt(_dl.RETRY_BACKOFF_S, attempt), gate_check)
    raise SegmentedDownloadError(f"segment {seg.index} failed after {SEGMENT_ATTEMPTS} attempts: {last_error}")


def download_file_segmented(
    *,
    url: str,
    filename: str,
    total_size: int,
    etag: str | None,
    expected_sha256: str | None,
    scratch_dir: Path,
    progress_cb: ProgressCb | None = None,
    gate_check: GateCheck | None = None,
    headers: dict[str, str] | None = None,
    num_segments: int | None = None,
    segment_target: int = SEGMENT_TARGET_BYTES,
    max_segments: int = MAX_SEGMENTS,
    opener_factory: Callable[[], Any] | None = None,
    timeout_s: float = REQUEST_TIMEOUT_S,
) -> Path:
    """Download one file as concurrent Range segments; return the"""
    if expected_sha256 is None:
        raise TypeError("expected_sha256 is required for segmented downloads")
    if not expected_sha256:
        raise ValueError("expected_sha256 must not be empty")

    scratch_dir.mkdir(parents=True, exist_ok=True)
    opener = opener_factory() if opener_factory else build_opener(None, user_agent=f"{APP_NAME}/segmented-downloader")
    segments = plan_segments(total_size, segment_target=segment_target, max_segments=max_segments)
    if num_segments is not None and total_size >= num_segments:
        # Explicit segment count (tests + callers that already know the
        segments = plan_segments(
            total_size,
            segment_target=max(1, -(-total_size // num_segments)),
            max_segments=num_segments,
        )

    state_path = state_path_for(scratch_dir, filename)
    state = read_state(state_path)
    if state is None or not state_matches(
        state,
        url=url,
        etag=etag,
        total_size=total_size,
        expected_sha256=expected_sha256,
    ):
        _discard_resume_state(scratch_dir, filename, state_path)
        done_flags = [False] * len(segments)
    else:
        done_flags = _reconcile_state(scratch_dir, filename, segments, state.get("segments", []))

    lock = threading.Lock()
    bytes_done = [sum(s.length for s, d in zip(segments, done_flags, strict=True) if d)]

    def on_bytes(n: int) -> None:
        with lock:
            bytes_done[0] += n
            total_now = bytes_done[0]
        if progress_cb is not None:
            progress_cb(total_now, total_size)

    def mark_done(index: int) -> None:
        with lock:
            done_flags[index] = True
            snapshot = [
                {
                    "index": s.index,
                    "start": s.start,
                    "end": s.end,
                    "done": done_flags[s.index],
                }
                for s in segments
            ]
        write_state(
            state_path,
            url=url,
            etag=etag,
            total_size=total_size,
            expected_sha256=expected_sha256,
            segments=snapshot,
        )

    active = [s for s, d in zip(segments, done_flags, strict=True) if not d]
    if active:
        base_headers = dict(headers or {})
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active), thread_name_prefix="segdl") as pool:
            futures = {
                pool.submit(
                    _fetch_segment,
                    opener=opener,
                    url=url,
                    seg=s,
                    part_path=part_path_for(scratch_dir, filename, s.index),
                    headers=base_headers,
                    timeout_s=timeout_s,
                    gate_check=gate_check,
                    on_bytes=on_bytes,
                ): s
                for s in active
            }
            try:
                for fut in concurrent.futures.as_completed(futures):
                    fut.result()  # raises on segment failure
                    mark_done(futures[fut].index)
            except BaseException:
                # Be polite: don't leave not-started work queued behind
                for f in futures:
                    f.cancel()
                raise

    assembled = scratch_dir / f"{_safe_filename(filename)}.assembled.tmp"
    _assemble_and_verify(scratch_dir, filename, segments, expected_sha256, assembled)
    # Success: resume state + parts are now redundant. Remove them so a
    _discard_resume_state(scratch_dir, filename, state_path)
    return assembled
