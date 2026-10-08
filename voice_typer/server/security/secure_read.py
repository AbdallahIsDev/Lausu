"""Bounded, symlink-refusing secure reads (SEC-002 / SEC-030).

Extracted verbatim from :mod:`voice_typer.server.security.file_io`
(callers import these names from that facade). POSIX opens with
``O_NOFOLLOW`` and re-verifies the inode mid-read; the byte cap aborts
the read as soon as it is exceeded.
"""

import contextlib
import os

from voice_typer.server.platform_utils import is_windows

# default upper bound on a single ``_secure_read_text`` call.
_DEFAULT_MAX_READ_BYTES = 16 * 1024 * 1024

def _read_with_byte_limit(f, max_bytes: int | None) -> str:
    """bounded read helper used by :func:`_secure_read_text`.

    Reads text from ``f`` in 64 KiB chunks.  After each chunk, encodes
    the chunk to UTF-8 to count its byte length (text-mode ``len()``
    counts CHARACTERS, not bytes, for non-ASCII content those differ by
    up to 4x).  If the running byte total exceeds ``max_bytes``, raises
    ``ValueError`` immediately (does NOT continue reading the rest of
    the file).  If ``max_bytes is None``, reads the whole file
    (unbounded, preserved for backward compat with callers that
    explicitly opt out of the cap).

    Mirrors the chunked-read pattern from
    :func:`voice_typer.server.cloud_engines._read_capped` (SEC-030) so
    the two bounded-read helpers behave consistently.
    """
    if max_bytes is None:
        return f.read()
    chunks: list[str] = []
    total_bytes = 0
    while True:
        chunk = f.read(64 * 1024)
        if not chunk:
            break
        # Encode to UTF-8 to count BYTES, not characters.  For ASCII
        chunk_bytes = len(chunk.encode("utf-8", errors="replace"))
        total_bytes += chunk_bytes
        if total_bytes > max_bytes:
            raise ValueError(
                f"file exceeds max_bytes={max_bytes} "
                f"(read {total_bytes} bytes so far), refusing to "
                f"continue reading to prevent unbounded memory consumption"
            )
        chunks.append(chunk)
    return "".join(chunks)


def _secure_read_text(
    path: os.PathLike,
    *,
    encoding: str = "utf-8",
    max_bytes: int | None = _DEFAULT_MAX_READ_BYTES,
) -> str:
    """SEC-002: Read text from a file securely, refusing to follow symlinks.

        On POSIX, opens the file with ``os.O_RDONLY | os.O_NOFOLLOW`` to
        prevent symlink-TOCTOU attacks. On Windows, checks for reparse
        points before reading.

    the inner ``os.fdopen`` was previously wrapped in a
        try/except that called ``os.close(fd)`` on any exception.  But
        ``f.close()`` in the ``finally`` block ALREADY closes the fd, so
        the except's ``os.close(fd)`` was a DOUBLE-CLOSE.  On a quiet
        fd-table this only emits EBADF (suppressed); but under concurrent
        load the closed fd number can be REUSED by another thread's
        ``os.open``/``socket``/etc., and the second ``os.close(fd)``
        would close that unrelated fd.  The fix uses an ``owned_fd``
        sentinel (set to ``-1`` immediately after ``os.fdopen`` succeeds)
        so the except path only closes the fd if ``os.fdopen`` itself
        failed.

    ``max_bytes`` (default 16 MiB) caps the total bytes read.
        A maliciously planted multi-GB file at the config path would
        otherwise exhaust RAM before the JSON parser saw a single byte.
        The cap is enforced in 64 KiB chunks via
        :func:`_read_with_byte_limit` so the read aborts as soon as the
        cap is exceeded (not after reading the whole file).  Pass
        ``max_bytes=None`` for the legacy unbounded behaviour (used by
        tests that intentionally read large fixtures).
    """
    from pathlib import Path

    p = Path(path)
    if not is_windows():
        # ``owned_fd`` tracks ownership of the raw fd.  ``-1`` is
        owned_fd = -1
        fd = os.open(str(p), os.O_RDONLY | os.O_NOFOLLOW)
        owned_fd = fd
        try:
            stat_before = os.fstat(fd)
            f = os.fdopen(fd, "r", encoding=encoding)
            owned_fd = -1  # fd is now owned by f; sentinel prevents double-close
            try:
                # bounded read, aborts with ValueError if the
                content = _read_with_byte_limit(f, max_bytes)
                stat_after = os.fstat(f.fileno())
                if stat_before.st_ino != stat_after.st_ino or stat_before.st_dev != stat_after.st_dev:
                    raise ValueError(f"SEC-002: inode changed during read of {p} -- possible TOCTOU attack")
            finally:
                f.close()
            return content
        except Exception:
            if owned_fd != -1:
                with contextlib.suppress(OSError):
                    os.close(owned_fd)
            raise
    else:
        # split the try so the deliberate reparse-point raise
        stat_result = None
        try:
            stat_result = os.lstat(str(p)) if hasattr(os, "lstat") else None
            attrs = getattr(stat_result, "st_file_attributes", 0) or 0
        except (AttributeError, OSError):
            attrs = 0
        if attrs & 0x00000400:  # FILE_ATTRIBUTE_REPARSE_POINT
            raise OSError(f"SEC-002: refusing to follow reparse point: {p}")
        # pre-check file size on Windows (no fstat-on-fd pattern
        if max_bytes is not None and stat_result is not None and stat_result.st_size > max_bytes:
            raise ValueError(f"file size {stat_result.st_size} exceeds max_bytes={max_bytes}")
        with open(p, encoding=encoding) as f:
            stat_before = os.fstat(f.fileno())
            content = _read_with_byte_limit(f, max_bytes)
            stat_after = os.fstat(f.fileno())
            if stat_before.st_ino != stat_after.st_ino or stat_before.st_dev != stat_after.st_dev:
                raise ValueError(f"SEC-002: inode changed during read of {p} -- possible TOCTOU attack")
            return content
