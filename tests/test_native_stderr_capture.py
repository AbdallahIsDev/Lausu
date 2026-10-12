"""Native (ctranslate2) stderr lines must land in canonical log format + file."""

from __future__ import annotations

import logging
import os

from voice_typer.worker.whisper.native_stderr import (
    capture_native_stderr,
    parse_native_line,
)

_NATIVE = (
    b"[2026-10-12 03:41:25.228] [ctranslate2] [thread 22868] [warning] "
    b"The compute type is float32.\n"
)


class TestParseNativeLine:
    def test_warning_splits_level_and_message(self):
        level, msg = parse_native_line(_NATIVE.decode())
        assert level == logging.WARNING
        assert msg == "The compute type is float32."
        assert "thread" not in msg

    def test_error_maps_to_error(self):
        level, _ = parse_native_line("[ctranslate2] [thread 1] [error] boom")
        assert level == logging.ERROR

    def test_unknown_level_defaults_to_warning(self):
        level, _ = parse_native_line("[ctranslate2] [thread 1] [babble] x")
        assert level == logging.WARNING

    def test_plain_line_is_none(self):
        assert parse_native_line("03:41:25  WARN  [MODEL] hello") is None

    def test_reformatted_line_does_not_rematch(self):
        assert parse_native_line("[MODEL] ctranslate2: The compute type is float32.") is None


class TestCaptureNativeStderr:
    def test_native_line_logged_passthrough_forwarded(self, tmp_path, caplog):
        target = logging.getLogger("test_native_stderr")
        sink = tmp_path / "stderr.bin"
        with open(sink, "wb") as handle:
            saved = os.dup(2)
            os.dup2(handle.fileno(), 2)
            try:
                with (
                    caplog.at_level(logging.DEBUG, logger="test_native_stderr"),
                    capture_native_stderr(target=target),
                ):
                    os.write(2, _NATIVE)
                    os.write(2, b"plain passthrough\n")
            finally:
                os.dup2(saved, 2)
                os.close(saved)
        assert "[MODEL] ctranslate2: The compute type is float32." in caplog.text
        raw = sink.read_bytes()
        assert b"plain passthrough\n" in raw
        assert b"ctranslate2" not in raw

    def test_fd_setup_failure_fails_open(self, monkeypatch):
        import voice_typer.worker.whisper.native_stderr as mod

        monkeypatch.setattr(mod.os, "dup", lambda _: (_ for _ in ()).throw(OSError()))
        with mod.capture_native_stderr():
            pass
