"""Native (ctranslate2) stderr lines must land in canonical log format + file."""

from __future__ import annotations

import logging
import os
import re

from voice_typer.worker.whisper.native_stderr import (
    _shorten,
    capture_native_stderr,
    parse_native_line,
)

_NATIVE = b"[2026-10-12 03:41:25.228] [ctranslate2] [thread 22868] [warning] The compute type is float32.\n"


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
        assert parse_native_line("[ctranslate2] The compute type is float32.") is None


class TestShorten:
    def test_inferred_compute_fallback_is_compressed(self):
        long = (
            "The compute type inferred from the saved model is float16, but the "
            "target device or backend do not support efficient float16 computation. "
            "The model weights have been automatically converted to use the float32 "
            "compute type instead."
        )
        assert _shorten(long) == "compute float16 unsupported, weights converted to float32"

    def test_unknown_message_passes_through(self):
        assert _shorten("The compute type is float32.") == "The compute type is float32."


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
        assert "[ctranslate2] The compute type is float32." in caplog.text
        raw = sink.read_bytes()
        assert b"plain passthrough\n" in raw
        assert b"ctranslate2" not in raw

    def test_fd_setup_failure_fails_open(self, monkeypatch):
        import voice_typer.worker.whisper.native_stderr as mod

        monkeypatch.setattr(mod.os, "dup", lambda _: (_ for _ in ()).throw(OSError()))
        with mod.capture_native_stderr():
            pass


class TestWriteAll:
    """Forwarded bytes must land completely: the tail is usually a newline."""

    def test_short_writes_are_retried(self, tmp_path, monkeypatch):
        import voice_typer.worker.whisper.native_stderr as mod

        sink = tmp_path / "forwarded.bin"
        payload = b"15:47:41  WARN  [MIC-GUARD] Microphone at 45%\n"
        real_write = os.write
        with open(sink, "wb") as handle:
            fd = handle.fileno()

            def short_write(target_fd, data):
                if target_fd == fd:
                    data = bytes(data)[:4]
                return real_write(target_fd, data)

            monkeypatch.setattr(mod.os, "write", short_write)
            mod._write_all(fd, payload)

        assert sink.read_bytes() == payload

    def test_passthrough_line_keeps_its_newline_under_short_writes(self, tmp_path, monkeypatch):
        import voice_typer.worker.whisper.native_stderr as mod

        sink = tmp_path / "stderr_short.bin"
        real_write = os.write
        with open(sink, "wb") as handle:
            saved = os.dup(2)
            os.dup2(handle.fileno(), 2)
            forward_fd = saved

            def short_write(target_fd, data):
                if target_fd == forward_fd:
                    data = bytes(data)[:5]
                return real_write(target_fd, data)

            monkeypatch.setattr(mod.os, "write", short_write)
            try:
                with capture_native_stderr(target=logging.getLogger("test_native_stderr")):
                    real_write(2, b"plain passthrough\n")
            finally:
                monkeypatch.undo()
                os.dup2(saved, 2)
                os.close(saved)

        assert sink.read_bytes() == b"plain passthrough\n"


class TestSystemWhisperWrapped:
    def test_both_model_constructions_capture_native_stderr(self):
        # Both WhisperModel sites in system_whisper.py must route through
        # the fd capture, otherwise ctranslate2 warnings land raw on
        # stderr. Source-pinned (same precedent as the wire-trace guard):
        # a behavioral test would need real weights + GPU.
        import pathlib

        src = pathlib.Path("voice_typer/server/system_whisper.py").read_text(encoding="utf-8")
        assert src.count("faster_whisper.WhisperModel(") == 4
        # …two per site: the fail-open branch (capture module absent in
        # the frozen sidecar) plus the wrapped branch. Both sites wrap.
        assert src.count("with _capture(target=log):") == 2
        # Whitespace-insensitive: `ruff format` joins or wraps this call, and
        # the pin must follow the import, not the line-breaking.
        assert len(re.findall(r'import_module\(\s*"voice_typer\.worker\.whisper\.native_stderr"', src)) == 2
