"""Every log record must end its own line (log-merge regression).

Shipped symptom: a WARN record and the NEXT record rendered on one terminal
row (``WARN [MIC-GUARD] Microphone at 45% 15:47:50 [MODEL] Model loading
via ...``), always across a slow model-load / CUDA warm-up window. The file
sink was clean; the console stream lost the record's terminating newline, so
the following record continued the row.

These tests pin the writer-layer contracts that prevent it:
one terminator per record, in the same write as the payload, never
truncated by a short write, and no two records ever sharing a row under
concurrency.
"""

from __future__ import annotations

import io
import logging
import os
import re
import threading

import pytest
from voice_typer.server.log import _FlushingStreamHandler, _TerminalFormatter

_TERMINAL_LINE = re.compile(r"^\d{2}:\d{2}:\d{2}  (DEBUG|INFO |WARN |ERROR|CRITICAL) \S")


class _ShortWriteStream(io.TextIOBase):
    """Text stream that accepts at most *chunk* characters/bytes per write."""

    encoding = "utf-8"
    errors = "backslashreplace"

    def __init__(self, chunk: int) -> None:
        super().__init__()
        self._chunk = chunk
        self.buffer = _ShortWriteBuffer(chunk)

    def write(self, text: str) -> int:
        take = min(self._chunk, len(text))
        self.buffer.data += text[:take].encode("utf-8")
        return take

    def flush(self) -> None:
        return None


class _ShortWriteBuffer:
    def __init__(self, chunk: int) -> None:
        self._chunk = chunk
        self.data = bytearray()

    def write(self, view) -> int:
        take = min(self._chunk, len(view))
        self.data += bytes(view[:take])
        return take

    def flush(self) -> None:
        return None


def _handler_over(stream) -> _FlushingStreamHandler:
    handler = _FlushingStreamHandler(stream)
    handler.setFormatter(_TerminalFormatter())
    handler.setLevel(logging.DEBUG)
    return handler


def _emit(handler: _FlushingStreamHandler, msg: str, level: int = logging.INFO) -> None:
    record = logging.LogRecord(
        name="voice_typer.server.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    handler.handle(record)


def test_short_write_keeps_the_terminator() -> None:
    """A partial write must never drop the record's newline."""
    stream = _ShortWriteStream(chunk=7)
    _emit(_handler_over(stream), "[MIC-GUARD] Microphone at 45%")

    text = stream.buffer.data.decode("utf-8")
    assert text.endswith("\n"), f"record lost its terminator: {text!r}"
    assert text == f"{text.rstrip(chr(10))}\n"
    assert "[MIC-GUARD] Microphone at 45%" in text


def test_every_record_is_one_line_under_short_writes() -> None:
    stream = _ShortWriteStream(chunk=3)
    handler = _handler_over(stream)
    for i in range(5):
        _emit(handler, f"[MODEL] record {i}")

    lines = stream.buffer.data.decode("utf-8").split("\n")
    assert lines[-1] == ""  # trailing terminator, not a glued fragment
    body = lines[:-1]
    assert len(body) == 5
    assert all(_TERMINAL_LINE.match(line) for line in body), body


def test_formatter_newline_is_not_doubled() -> None:
    """A formatter that already ends with a newline gains no second one."""
    stream = _ShortWriteStream(chunk=4096)
    handler = _handler_over(stream)
    handler.setFormatter(_TrailingNewlineFormatter())
    _emit(handler, "boom")

    assert stream.buffer.data.decode("utf-8") == "15:00:00  INFO  boom\n"


class _TrailingNewlineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        return "15:00:00  INFO  boom\n"


def test_text_only_stream_keeps_one_terminator() -> None:
    """Streams without a binary buffer (StringIO in tests) behave the same."""
    stream = io.StringIO()
    _emit(_handler_over(stream), "[PERF] Warm-up inference completed. CUDA kernels primed 0.2s")

    text = stream.getvalue()
    assert text.endswith("\n")
    assert text.count("\n") == 1


def test_concurrent_records_never_share_a_row() -> None:
    """N records from M threads in -> N template lines out (threaded repro)."""
    read_fd, write_fd = os.pipe()
    stream = os.fdopen(write_fd, "w", encoding="utf-8", errors="backslashreplace")
    handler = _handler_over(stream)
    per_thread = 40
    threads = 4
    collected: list[bytes] = []

    def drain() -> None:
        with os.fdopen(read_fd, "rb") as reader:
            while True:
                chunk = reader.read(65536)
                if not chunk:
                    return
                collected.append(chunk)

    reader_thread = threading.Thread(target=drain)
    reader_thread.start()

    def worker(idx: int) -> None:
        for i in range(per_thread):
            level = logging.WARNING if i % 5 == 0 else logging.INFO
            _emit(handler, f"[MIC-GUARD] thread {idx} record {i}", level)

    workers = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    handler.close()
    stream.close()
    reader_thread.join(timeout=10)
    assert not reader_thread.is_alive()

    raw = b"".join(collected).decode("utf-8")
    lines = raw.split("\n")
    assert lines[-1] == ""
    body = lines[:-1]
    assert len(body) == per_thread * threads, f"{len(body)} rows for {per_thread * threads} records"
    assert all(_TERMINAL_LINE.match(line) for line in body), [
        line for line in body if not _TERMINAL_LINE.match(line)
    ]
    for idx in range(threads):
        assert sum(1 for line in body if f"thread {idx} " in line) == per_thread


@pytest.mark.parametrize("level", [logging.INFO, logging.WARNING])
def test_console_record_survives_a_transient_flush_error(level: int) -> None:
    """One failed flush must not strand the record's newline in the buffer."""

    class _FlakyBuffer(_ShortWriteBuffer):
        """Commits on flush only; the first flush raises."""

        def __init__(self) -> None:
            super().__init__(chunk=4096)
            self.pending = bytearray()
            self.failures = 1

        def write(self, view) -> int:
            self.pending += bytes(view)
            return len(view)

        def flush(self) -> None:
            if self.failures:
                self.failures -= 1
                raise OSError("transient flush failure")
            self.data += self.pending
            self.pending.clear()

    class _FlakyStream(io.TextIOBase):
        encoding = "utf-8"
        errors = "backslashreplace"

        def __init__(self) -> None:
            super().__init__()
            self.buffer = _FlakyBuffer()

        def flush(self) -> None:
            return None

    stream = _FlakyStream()
    _emit(_handler_over(stream), "[MODEL] Model loading via cuda/float16/large-v3 45.7s", level)

    text = stream.buffer.data.decode("utf-8")
    assert text.endswith("\n"), f"terminator lost after a flush error: {text!r}"
    assert _TERMINAL_LINE.match(text.split("\n")[0])
