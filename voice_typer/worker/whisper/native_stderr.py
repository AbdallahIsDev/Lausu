"""Capture C-extension fd-2 output (ctranslate2) into canonical logging."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
import threading
from collections.abc import Iterator

log = logging.getLogger("voice_typer.worker.whisper")

_NATIVE_LINE_RE = re.compile(
    r"^(?:\[[^\]]+\]\s+)?\[ctranslate2\]\s*"
    r"(?:\[thread\s+\d+\]\s*)?\[(?P<level>[A-Za-z]+)\]\s*(?P<msg>.*)$"
)

_LEVEL_BY_NAME = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
    "critical": logging.CRITICAL,
}


def parse_native_line(line: str) -> tuple[int, str] | None:
    """Split a native ``[ctranslate2]`` stderr line into (level, message)."""
    _match = _NATIVE_LINE_RE.match(line.strip())
    if _match is None:
        return None
    return (
        _LEVEL_BY_NAME.get(_match.group("level").lower(), logging.WARNING),
        _match.group("msg"),
    )


@contextlib.contextmanager
def capture_native_stderr(
    tag: str = "[MODEL]",
    target: logging.Logger | None = None,
) -> Iterator[None]:
    """Capture fd-level stderr for the block; re-emit native lines via logging."""
    _dest = target if target is not None else log
    try:
        _saved = os.dup(2)
        _read, _write = os.pipe()
    except OSError:
        yield
        return
    with contextlib.suppress(Exception):
        sys.stderr.flush()
    os.dup2(_write, 2)
    os.close(_write)

    def _emit(_raw: bytes) -> None:
        _parsed = parse_native_line(_raw.decode("utf-8", errors="replace"))
        if _parsed is None:
            with contextlib.suppress(OSError):
                os.write(_saved, _raw)
        else:
            _dest.log(_parsed[0], "%s ctranslate2: %s", tag, _parsed[1])

    def _reader() -> None:
        _buf = bytearray()
        while True:
            try:
                _chunk = os.read(_read, 65536)
            except OSError:
                break
            if not _chunk:
                break
            _buf += _chunk
            while True:
                _nl = _buf.find(b"\n")
                if _nl < 0:
                    break
                _emit(bytes(_buf[: _nl + 1]))
                del _buf[: _nl + 1]
        if _buf:
            _emit(bytes(_buf) + b"\n")

    # RACE-008: daemon is acceptable — the reader only forwards log bytes and
    # must never keep the worker alive; the finally-join below bounds its end.
    _thread = threading.Thread(target=_reader, name="native-stderr", daemon=True)
    _thread.start()
    try:
        yield
    finally:
        # RACE-016: bounded join so cleanup never blocks process exit.
        # Restoring fd 2 closes the pipe's last write end, so the reader
        # drains the buffer, sees EOF, and exits on its own.
        with contextlib.suppress(OSError):
            os.dup2(_saved, 2)
        _thread.join(timeout=5.0)
        with contextlib.suppress(OSError):
            os.close(_read)
        with contextlib.suppress(OSError):
            os.close(_saved)
