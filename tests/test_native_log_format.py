"""Native key-listener logs must use the canonical file shape (C-LOG-1).

``native-windows.log`` (and its Linux/macOS siblings) previously used
``YYYY-MM-DDTHH:MM:SS.mmm [pid] msg``. They must emit
``YYYY-MM-DD  HH:MM:SS  LEVEL  msg`` like every other file log, with
the level derived from the message's embedded severity prefix.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NATIVE_DIR = REPO_ROOT / "voice_typer" / "server" / "native"

# Mirror of ``tests/test_logging.py::_EXACT_FILE_LINE_RE`` (kept local so
_CANONICAL_LINE_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}  \d{2}:\d{2}:\d{2}  "  # clean ts + 2 spaces
    r"(?:DEBUG|INFO|WARN|ERROR|CRITICAL) {1,2}"  # level label + aligned spacing
    r".+"  # message (unmodified)
)


def _read(name: str) -> str:
    path = NATIVE_DIR / name
    assert path.is_file(), f"missing native source: {name}"
    return path.read_text(encoding="utf-8")


class TestCanonicalSamples:
    """Representative new-shape lines match the canonical template."""

    SAMPLES = [
        "2026-09-18  12:00:00  INFO  windows-key-listener starting; spec=<f2>",
        "2026-09-18  12:00:00  INFO  stdin reader thread started (PING/PONG enabled)",
        "2026-09-18  12:00:00  INFO  keyboard hook installed",
        "2026-09-18  12:00:00  INFO  READY emitted; version=1.0.0",
        "2026-09-18  12:00:01  WARN  failed to open --log-file (errno=13)",
        "2026-09-18  12:00:02  ERROR  SetWindowsHookEx failed (error=5)",
    ]

    def test_samples_match_canonical_shape(self):
        for line in self.SAMPLES:
            assert _CANONICAL_LINE_RE.fullmatch(line), f"not canonical: {line!r}"

    def test_old_shape_no_longer_matches(self):
        old = [
            "2026-09-18T12:00:00.000 [1234] windows-key-listener starting; spec=<f2>",
            "2026-09-18T12:00:00.010 [1234] keyboard hook installed",
        ]
        for line in old:
            assert not _CANONICAL_LINE_RE.fullmatch(line), f"old shape must fail: {line!r}"


class TestNativeSourcesEmitCanonicalShape:
    """The three listeners' log helpers must format the canonical shape."""

    def test_windows_uses_canonical_snprintf(self):
        src = _read("windows-key-listener.c")
        assert '"%04d-%02d-%02d  %02d:%02d:%02d  %s  %s\\n"' in src
        assert "T%02d:%02d:%02d.%03d [%lu]" not in src
        assert "GetCurrentProcessId(), msg)" not in src

    def test_linux_uses_canonical_snprintf(self):
        src = _read("linux-key-listener.c")
        assert '"%Y-%m-%d  %H:%M:%S"' in src
        assert '"%s  %s  %s\\n", ts, level, text' in src
        assert "%Y-%m-%dT%H:%M:%S" not in src
        assert "(int)getpid(), msg" not in src

    def test_macos_uses_canonical_date_format(self):
        src = _read("macos-key-listener.swift")
        assert '"yyyy-MM-dd  HH:mm:ss"' in src
        assert "withFractionalSeconds" not in src
        assert "[\\(pid)]" not in src

    def test_level_comes_from_message_severity(self):
        for name in ("windows-key-listener.c", "linux-key-listener.c"):
            src = _read(name)
            assert 'strncmp(msg, "ERROR:", 6)' in src
            assert 'strncmp(msg, "WARN:", 5)' in src
        swift = _read("macos-key-listener.swift")
        assert '["ERROR:", "WARN:"]' in swift

    def test_timestamps_use_local_time(self):
        """Native log timestamps must match Python ``time.localtime`` / Rust
        ``GetLocalTime`` so cross-file correlation lines up."""
        win = _read("windows-key-listener.c")
        assert "GetLocalTime(&st)" in win
        assert "GetSystemTime(&st)" not in win
        linux = _read("linux-key-listener.c")
        assert "localtime_r(&now, &tm_buf)" in linux
        assert "gmtime_r(&now, &tm_buf)" not in linux
        swift = _read("macos-key-listener.swift")
        assert "TimeZone.current" in swift
        assert 'TimeZone(identifier: "UTC")' not in swift
