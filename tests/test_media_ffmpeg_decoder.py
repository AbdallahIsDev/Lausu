"""ffmpeg decoder: argv/whitelist/cancel/parity/safety contract tests.

Tests that need a real executable resolve it through the same production
resolver and skip clearly when it is absent.
"""

from __future__ import annotations

import io
import math
import os
import re
import struct
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from voice_typer.server.media_ingest import decoder, downloader, errors, ffmpeg_binaries

ROOT = Path(__file__).resolve().parents[1]
REPO_WAV = ROOT / "tests" / "fixtures" / "test_440hz_1s_16k.wav"
# Real executable so the strict production gate passes; Popen is faked in argv tests.
REAL_BIN = sys.executable


def _binaries() -> ffmpeg_binaries.BinaryPair | None:
    return ffmpeg_binaries.resolve_binaries()


requires_ffmpeg = pytest.mark.skipif(_binaries() is None, reason="ffmpeg/ffprobe not available on PATH or bundle")
def _has_ffprobe() -> bool:
    pair = _binaries()
    return pair is not None and pair.ffprobe is not None


_FFPROBE_AVAILABLE = _has_ffprobe()


def _ffprobe() -> str:
    pair = _binaries()
    assert pair is not None and pair.ffprobe is not None
    return pair.ffprobe
requires_ffprobe = pytest.mark.skipif(not _FFPROBE_AVAILABLE, reason="ffprobe parity oracle not available")


def _write_wav(path: Path, seconds: float, rate: int = 16_000, amplitude: int = 3000) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        payload = bytearray()
        for i in range(int(seconds * rate)):
            payload += struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / rate)))
        wf.writeframes(bytes(payload))


def _ffmpeg(*args: str) -> None:
    pair = _binaries()
    assert pair is not None
    subprocess.run([pair.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args], check=True)


def _long_wav(path: Path, seconds: int = 20) -> None:
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=16000",
        "-t",
        str(seconds),
        "-c:a",
        "pcm_s16le",
        str(path),
    )


class _FakeProc:
    """A finished process: no output, no work, but a real pipe API."""

    def __init__(self) -> None:
        self.stdout = io.BytesIO(b"")
        self.stderr = io.BytesIO(b"")

    def poll(self) -> int:
        return 0

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


def _capture_popen(monkeypatch, proc=None):
    calls: list[tuple[list[str], dict]] = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        return proc if proc is not None else _FakeProc()

    monkeypatch.setattr(decoder.subprocess, "Popen", fake)
    return calls


def _fake_binaries(monkeypatch, ffprobe: str | None = None) -> None:
    monkeypatch.setattr(
        ffmpeg_binaries,
        "resolve_binaries",
        lambda: ffmpeg_binaries.BinaryPair(ffmpeg=REAL_BIN, ffprobe=ffprobe),
    )


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pids_alive(pids: list[int]) -> set[int]:
    """One batch scan; returns the subset of PIDs still alive."""
    want = set(pids)
    if not want:
        return set()
    alive: set[int] = set()
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False).stdout
        for line in out.splitlines():
            cols = line.split('","')
            if len(cols) >= 2:
                try:
                    alive.add(int(cols[1].strip('"')))
                except ValueError:
                    continue
        return want & alive
    for pid in want:
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        alive.add(pid)
    return alive


def _wait_until(predicate, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate(), "condition never became true"


class TestArgvContract:
    def test_exact_local_argv_is_a_list_with_no_shell(self, monkeypatch, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        _fake_binaries(monkeypatch)
        calls = _capture_popen(monkeypatch)
        list(decoder.decode_chunks(str(wav)))
        argv, kwargs = calls[0]
        assert isinstance(argv, list)
        assert argv[0] == REAL_BIN
        assert argv[1:] == [
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-protocol_whitelist",
            "file",
            "-i",
            "file:" + str(wav),
            "-vn",
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "-",
        ]
        assert kwargs.get("shell", False) is False

    def test_remote_argv_uses_the_http_whitelist(self, monkeypatch):
        _fake_binaries(monkeypatch)
        calls = _capture_popen(monkeypatch)
        list(decoder.decode_chunks("https://cdn.example/a.m4a", remote=True))
        argv = calls[0][0]
        assert argv[argv.index("-protocol_whitelist") + 1] == "http,https,tcp,tls,crypto"
        assert argv[argv.index("-i") + 1] == "https://cdn.example/a.m4a"

    def test_seek_precedes_the_input(self, monkeypatch, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        _fake_binaries(monkeypatch)
        calls = _capture_popen(monkeypatch)
        list(decoder.decode_chunks(str(wav), start_seconds=2.5))
        argv = calls[0][0]
        assert argv[argv.index("-ss") + 1] == "2.500000"
        assert argv.index("-ss") < argv.index("-i")

    @pytest.mark.parametrize("url", ["ftp://cdn.example/a.mp3", "file:///etc/passwd", "data:audio/mp3,x", "a.mp3"])
    def test_decode_chunks_rejects_non_http_schemes_before_spawning(self, monkeypatch, url):
        _fake_binaries(monkeypatch)
        calls = _capture_popen(monkeypatch)
        with pytest.raises(errors.MediaIngestError) as info:
            list(decoder.decode_chunks(url, remote=True))
        assert info.value.code == errors.DECODE_FAILED
        assert calls == []

    def test_duration_probe_argv_uses_the_same_whitelist(self, monkeypatch, tmp_path):
        """Duration probing is ffmpeg-only: input-only argv, no output, no ffprobe."""
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        _fake_binaries(monkeypatch, ffprobe=None)
        seen: list[tuple[list[str], dict]] = []

        def fake_run(argv, **kwargs):
            seen.append((argv, kwargs))

            class Done:
                returncode = 1  # ffmpeg has no output file: rc=1 after the header
                stdout = b""
                stderr = b"  Stream #0:0: Audio: pcm_s16le\n  Duration: 00:00:01.00, start: 0.000000\n"

            return Done()

        monkeypatch.setattr(decoder.subprocess, "run", fake_run)
        assert decoder.probe_duration_seconds(str(wav)) == 1.0
        argv, kwargs = seen[0]
        assert argv == [
            REAL_BIN,
            "-hide_banner",
            "-nostdin",
            "-protocol_whitelist",
            "file",
            "-i",
            "file:" + str(wav),
        ]
        assert kwargs.get("timeout") == decoder.OPEN_TIMEOUT_US / 1_000_000.0
        assert kwargs.get("shell", False) is False


class TestSafety:
    @requires_ffmpeg
    def test_leading_dash_filename_is_not_an_option(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        wav = tmp_path / "-lead.wav"
        _write_wav(wav, 1)
        chunks = list(decoder.decode_chunks(wav.name))
        assert sum(c.size for c in chunks) == decoder.TARGET_SAMPLE_RATE

    @requires_ffmpeg
    def test_unicode_and_arabic_paths_decode(self, tmp_path):
        wav = tmp_path / "ملف_صوتي.wav"
        _write_wav(wav, 1)
        chunks = list(decoder.decode_chunks(str(wav)))
        assert sum(c.size for c in chunks) == decoder.TARGET_SAMPLE_RATE
        assert all(c.dtype == np.float32 and c.ndim == 1 for c in chunks)

    def test_missing_binary_raises_a_friendly_error(self, monkeypatch, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        monkeypatch.setattr(ffmpeg_binaries, "resolve_binaries", lambda: None)
        calls = _capture_popen(monkeypatch)
        with pytest.raises(errors.MediaIngestError) as info:
            list(decoder.decode_chunks(str(wav)))
        assert info.value.code == errors.FFMPEG_MISSING
        message = info.value.message.lower()
        assert "reinstall the app" in message
        assert "traceback" not in message and "ffmpeg" not in message
        assert calls == []

    def test_nonexistent_binary_is_rejected_by_the_strict_gate(self, monkeypatch, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        monkeypatch.setattr(
            ffmpeg_binaries,
            "resolve_binaries",
            lambda: ffmpeg_binaries.BinaryPair(ffmpeg=str(tmp_path / "no-such-ffmpeg"), ffprobe=None),
        )
        calls = _capture_popen(monkeypatch)
        with pytest.raises(errors.MediaIngestError) as info:
            list(decoder.decode_chunks(str(wav)))
        assert info.value.code == errors.FFMPEG_MISSING
        assert calls == []

    def test_stderr_flood_does_not_deadlock(self, monkeypatch, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        _fake_binaries(monkeypatch)
        real = subprocess.Popen
        calls: list[list[str]] = []

        def fake(argv, **kwargs):
            calls.append(argv)
            script = "import sys; sys.stderr.write('x'*2000000); sys.stderr.flush()"
            return real([sys.executable, "-c", script], **kwargs)

        monkeypatch.setattr(decoder.subprocess, "Popen", fake)
        started = time.monotonic()
        assert list(decoder.decode_chunks(str(wav))) == []
        assert time.monotonic() - started < 15.0, "stderr flood deadlocked the decoder"

    @requires_ffmpeg
    def test_generator_close_terminates_and_reaps_ffmpeg(self, monkeypatch, tmp_path):
        long_wav = tmp_path / "long.wav"
        _long_wav(long_wav)
        real = subprocess.Popen
        spawned: list[subprocess.Popen] = []

        def spy(argv, **kwargs):
            proc = real(argv, **kwargs)
            spawned.append(proc)
            return proc

        monkeypatch.setattr(decoder.subprocess, "Popen", spy)
        gen = decoder.decode_chunks(str(long_wav))
        assert next(gen).shape == (decoder.CHUNK_SAMPLES,)
        pid = spawned[0].pid
        assert _pid_alive(pid)
        cast(Any, gen).close()
        _wait_until(lambda: not _pid_alive(pid))
        assert spawned[0].poll() is not None, "ffmpeg was killed but never reaped"

    @requires_ffmpeg
    def test_scoped_cancel_event_stops_the_process(self, monkeypatch, tmp_path):
        long_wav = tmp_path / "long.wav"
        _long_wav(long_wav)
        real = subprocess.Popen
        spawned: list[subprocess.Popen] = []

        def spy(argv, **kwargs):
            proc = real(argv, **kwargs)
            spawned.append(proc)
            return proc

        monkeypatch.setattr(decoder.subprocess, "Popen", spy)
        event = threading.Event()
        gen = decoder.decode_chunks(str(long_wav), cancel_event=event)
        assert next(gen).shape == (decoder.CHUNK_SAMPLES,)
        pid = spawned[0].pid
        event.set()
        with pytest.raises(StopIteration):
            next(gen)
        _wait_until(lambda: not _pid_alive(pid))
        assert not _pid_alive(pid)

    def test_exception_in_consumer_still_reaps(self, monkeypatch, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        _fake_binaries(monkeypatch)
        real = subprocess.Popen
        spawned: list[subprocess.Popen] = []
        script = "import sys,time; sys.stdout.buffer.write(b'\\0'*320000); sys.stdout.buffer.flush(); time.sleep(20)"

        def spy(argv, **kwargs):
            proc = real([sys.executable, "-c", script], **kwargs)
            spawned.append(proc)
            return proc

        monkeypatch.setattr(decoder.subprocess, "Popen", spy)

        def consume():
            gen = decoder.decode_chunks(str(wav))
            for chunk in gen:
                assert chunk.shape == (decoder.CHUNK_SAMPLES,)
                raise RuntimeError("consumer failed")

        with pytest.raises(RuntimeError):
            consume()
        pid = spawned[0].pid
        _wait_until(lambda: not _pid_alive(pid))
        assert spawned[0].poll() is not None


class TestErrorMapping:
    @requires_ffmpeg
    def test_video_only_file_maps_no_audio(self, tmp_path):
        avi = tmp_path / "video.avi"
        # mpeg4 is FFmpeg's own encoder: no libx264/libx265 needed.
        _ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=32x32:r=2",
            "-frames:v",
            "3",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-f",
            "avi",
            str(avi),
        )
        with pytest.raises(errors.MediaIngestError) as info:
            list(decoder.decode_chunks(str(avi)))
        assert info.value.code == errors.NO_AUDIO

    @requires_ffmpeg
    def test_corrupt_file_maps_decode_failed(self, tmp_path):
        bad = tmp_path / "bad.wav"
        bad.write_bytes(b"not a wave file at all")
        with pytest.raises(errors.MediaIngestError) as info:
            list(decoder.decode_chunks(str(bad)))
        assert info.value.code == errors.DECODE_FAILED

    def test_log_context_address_does_not_mimic_an_http_status(self):
        stderr = "[in#0 @ 00000000007b8500] Invalid data found; [in#0 @ 00000000007b8403] end of file"
        err = decoder._classify_ffmpeg_failure(1, decoder._LOG_CONTEXT_RE.sub("", stderr), remote=False)
        assert err.code == errors.DECODE_FAILED

    @requires_ffmpeg
    def test_truncated_file_maps_decode_failed(self, tmp_path):
        ogg = tmp_path / "short.ogg"
        _ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000",
            "-t",
            "5",
            "-c:a",
            "libvorbis",
            str(ogg),
        )
        data = ogg.read_bytes()
        ogg.write_bytes(data[: max(64, len(data) // 2)])
        with pytest.raises(errors.MediaIngestError) as info:
            list(decoder.decode_chunks(str(ogg)))
        assert info.value.code == errors.DECODE_FAILED


class TestEofRaceStress:
    @requires_ffmpeg
    def test_200_rounds_per_bad_input_classify_and_reap(self, monkeypatch, tmp_path):
        corrupt = tmp_path / "corrupt.wav"
        corrupt.write_bytes(b"not a wave file at all")
        truncated = tmp_path / "truncated.ogg"
        _ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000",
            "-t",
            "2",
            "-c:a",
            "libvorbis",
            str(truncated),
        )
        raw = truncated.read_bytes()
        truncated.write_bytes(raw[: max(64, len(raw) // 2)])
        video = tmp_path / "video.avi"
        _ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=32x32:r=2",
            "-frames:v",
            "3",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-f",
            "avi",
            str(video),
        )

        real_popen = subprocess.Popen
        spawned: list[subprocess.Popen] = []

        def spy(argv, **kwargs):
            proc = real_popen(argv, **kwargs)
            spawned.append(proc)
            return proc

        monkeypatch.setattr(decoder.subprocess, "Popen", spy)
        for path, code in (
            (corrupt, errors.DECODE_FAILED),
            (truncated, errors.DECODE_FAILED),
            (video, errors.NO_AUDIO),
        ):
            first = len(spawned)
            for _ in range(200):
                with pytest.raises(errors.MediaIngestError) as info:
                    list(decoder.decode_chunks(str(path)))
                assert info.value.code == code, (path.name, info.value.code)
            batch = spawned[first:]
            unreaped = [p.pid for p in batch if p.poll() is None]
            assert not unreaped, f"{path.name}: unreaped ffmpeg PIDs {unreaped}"
            assert _pids_alive([p.pid for p in batch]) == set(), f"{path.name}: orphaned ffmpeg"


class TestProbes:
    @requires_ffmpeg
    def test_duration_probe_reads_the_header(self, tmp_path):
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 3)
        assert decoder.probe_duration_seconds(str(wav)) == pytest.approx(3.0, abs=0.05)
        assert decoder.probe_duration_seconds(str(tmp_path / "missing.wav")) is None

    def test_probes_fail_soft_without_any_binary(self, monkeypatch, tmp_path):
        """With no resolver result at all, both probes fail soft to None."""
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        monkeypatch.setattr(ffmpeg_binaries, "resolve_binaries", lambda: None)
        assert decoder.probe_duration_seconds(str(wav)) is None
        assert decoder.probe_remote("https://cdn.example/a.mp3") is None

    def test_probe_remote_reads_audio_streams_and_duration_without_ffprobe(self, monkeypatch):
        log_text = (
            "  Stream #0:0(und): Audio: aac (LC), 44100 Hz, stereo, fltp\n"
            "  Stream #0:1(und): Video: h264 (High), yuv420p\n"
            "  Duration: 00:00:12.50, start: 0.000000\n"
        )
        monkeypatch.setattr(decoder, "_run_duration_probe", lambda *a, **k: log_text)
        monkeypatch.setattr(
            ffmpeg_binaries,
            "resolve_binaries",
            lambda: ffmpeg_binaries.BinaryPair(REAL_BIN, None),
        )
        probe = decoder.probe_remote("https://cdn.example/a.mp4")
        assert probe is not None
        assert probe.audio_streams == 1
        assert probe.duration_seconds == pytest.approx(12.5)
        assert decoder.probe_remote("ftp://cdn.example/a.mp4") is None


class TestDurationParityFfprobeToFfmpeg:
    """The retired ffprobe duration path vs the new ffmpeg stderr parser.

    Both paths are called on the SAME inputs; parity is the condition for
    dropping ffprobe from the shipped Windows binary set.
    """

    @staticmethod
    def _old(source: str, ffprobe: str, *, remote: bool = False) -> float | None:
        """Independent ffprobe oracle (C-TEST-10): its own argv, not production helpers."""
        argv = [
            ffprobe,
            "-v",
            "error",
            "-protocol_whitelist",
            "http,https,tcp,tls,crypto" if remote else "file",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            source if remote else "file:" + source,
        ]
        try:
            completed = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=(decoder.READ_TIMEOUT_US if remote else decoder.OPEN_TIMEOUT_US) / 1_000_000.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", completed.stdout.decode("utf-8", "replace"))
        return float(match.group(0)) if match else None

    @classmethod
    def _assert_parity(cls, source: str, ffprobe: str, *, remote: bool = False) -> tuple[float | None, float | None]:
        old = cls._old(source, ffprobe, remote=remote)
        new = decoder.probe_duration_seconds(source, remote=remote)
        if old is None:
            assert new is None, f"ffprobe={old!r} ffmpeg={new!r} for {source}"
        else:
            assert new is not None and new == pytest.approx(old, abs=0.02), (old, new, source)
        return old, new

    @requires_ffmpeg
    @requires_ffprobe
    @pytest.mark.parametrize("path", [REPO_WAV], ids=["repo_fixture"])
    def test_repo_fixture(self, path):
        old, new = self._assert_parity(str(path), _ffprobe())
        assert old == new == pytest.approx(1.0, abs=0.02)

    @requires_ffmpeg
    @requires_ffprobe
    @pytest.mark.parametrize("seconds", [1, 12])
    def test_generated_tone(self, tmp_path, seconds):
        wav = tmp_path / f"tone_{seconds}.wav"
        _write_wav(wav, seconds)
        old, new = self._assert_parity(str(wav), _ffprobe())
        assert old == new == pytest.approx(float(seconds), abs=0.02)

    @requires_ffmpeg
    @requires_ffprobe
    def test_truncated(self, tmp_path):
        ogg = tmp_path / "short.ogg"
        _ffmpeg(
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
            "-t", "5", "-c:a", "libvorbis", str(ogg),
        )
        raw = ogg.read_bytes()
        ogg.write_bytes(raw[: max(64, len(raw) // 2)])
        old, new = self._assert_parity(str(ogg), _ffprobe())
        assert old is None and new is None

    @requires_ffmpeg
    @requires_ffprobe
    def test_video_only(self, tmp_path):
        avi = tmp_path / "video.avi"
        # mpeg4 is FFmpeg's own encoder: no libx264/libx265 needed.
        _ffmpeg(
            "-f", "lavfi", "-i", "color=c=black:s=32x32:r=2",
            "-frames:v", "3", "-c:v", "mpeg4", "-pix_fmt", "yuv420p",
            "-f", "avi", str(avi),
        )
        old, new = self._assert_parity(str(avi), _ffprobe())
        assert old == new == pytest.approx(1.5, abs=0.02)

    @requires_ffmpeg
    @requires_ffprobe
    def test_corrupt(self, tmp_path):
        bad = tmp_path / "bad.wav"
        bad.write_bytes(b"not a wave file at all")
        old, new = self._assert_parity(str(bad), _ffprobe())
        assert old is None and new is None

    def test_remote_mocked(self, monkeypatch):
        """One faked 12.5 s source, both paths, identical whitelist."""
        _fake_binaries(monkeypatch, ffprobe="ffprobe-bin")
        seen: list[list[str]] = []

        class Done:
            returncode = 0

            def __init__(self, stdout: bytes, stderr: bytes) -> None:
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(argv, **kwargs):
            seen.append(argv)
            if argv[0] == "ffprobe-bin":
                return Done(b"12.5\n", b"")
            return Done(b"", b"  Stream #0:0: Audio: aac\n  Duration: 00:00:12.50, start: 0.000000\n")

        monkeypatch.setattr(decoder.subprocess, "run", fake_run)
        old, new = self._assert_parity("https://cdn.example/a.mp3", "ffprobe-bin", remote=True)
        assert old == new == pytest.approx(12.5)
        assert len(seen) == 2
        for argv in seen:
            assert argv[argv.index("-protocol_whitelist") + 1] == "http,https,tcp,tls,crypto"

    def test_duration_probe_never_needs_ffprobe(self, monkeypatch, tmp_path):
        """Production invariant: ffprobe=None still yields a duration."""
        wav = tmp_path / "clip.wav"
        _write_wav(wav, 1)
        monkeypatch.setattr(
            ffmpeg_binaries,
            "resolve_binaries",
            lambda: ffmpeg_binaries.BinaryPair(REAL_BIN, None),
        )
        seen: list[list[str]] = []

        def fake_run(argv, **kwargs):
            seen.append(argv)

            class Done:
                returncode = 1
                stdout = b""
                stderr = b"  Duration: 00:00:01.00, start: 0.000000\n"

            return Done()

        monkeypatch.setattr(decoder.subprocess, "run", fake_run)
        assert decoder.probe_duration_seconds(str(wav)) == 1.0
        assert len(seen) == 1 and "ffprobe" not in seen[0]


class TestBinaryResolver:
    def test_env_override_wins(self, monkeypatch, tmp_path):
        ffmpeg = tmp_path / "my-ffmpeg"
        ffprobe = tmp_path / "my-ffprobe"
        ffmpeg.write_bytes(b"x")
        ffprobe.write_bytes(b"x")
        monkeypatch.setenv(ffmpeg_binaries.ENV_FFMPEG, str(ffmpeg))
        monkeypatch.setenv(ffmpeg_binaries.ENV_FFPROBE, str(ffprobe))
        pair = ffmpeg_binaries.resolve_binaries()
        assert pair == ffmpeg_binaries.BinaryPair(str(ffmpeg), str(ffprobe))

    def test_shipped_binary_beats_path(self, monkeypatch, tmp_path, caplog):
        import logging

        for name in (ffmpeg_binaries.ENV_FFMPEG, ffmpeg_binaries.ENV_FFPROBE):
            monkeypatch.delenv(name, raising=False)
        ext = ".exe" if os.name == "nt" else ""
        for program in ("ffmpeg", "ffprobe"):
            (tmp_path / (program + ext)).write_bytes(b"shipped")
        monkeypatch.setattr(ffmpeg_binaries, "_shipped_dirs", lambda: (tmp_path,))
        monkeypatch.setattr(ffmpeg_binaries, "shutil", type("S", (), {"which": staticmethod(lambda n: "/path/" + n)})())
        with caplog.at_level(logging.WARNING, logger="voice_typer.server.media_ingest.ffmpeg_binaries"):
            pair = ffmpeg_binaries.resolve_binaries()
        assert pair is not None
        assert pair.ffmpeg == str(tmp_path / ("ffmpeg" + ext))
        assert "from PATH" not in caplog.text

    def test_dev_path_fallback_warns_about_gpl(self, monkeypatch, caplog):
        import logging

        for name in (ffmpeg_binaries.ENV_FFMPEG, ffmpeg_binaries.ENV_FFPROBE):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(ffmpeg_binaries, "_frozen", lambda: False)
        monkeypatch.setattr(ffmpeg_binaries, "_shipped", lambda program: None)
        monkeypatch.setattr(
            ffmpeg_binaries,
            "shutil",
            type("S", (), {"which": staticmethod(lambda n: "/dev/bin/" + n)})(),
        )
        with caplog.at_level(logging.WARNING, logger="voice_typer.server.media_ingest.ffmpeg_binaries"):
            pair = ffmpeg_binaries.resolve_binaries()
        assert pair is not None
        assert "never be bundled" in caplog.text

    def test_frozen_build_never_falls_back_to_path(self, monkeypatch):
        for name in (ffmpeg_binaries.ENV_FFMPEG, ffmpeg_binaries.ENV_FFPROBE):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(ffmpeg_binaries, "_frozen", lambda: True)
        monkeypatch.setattr(ffmpeg_binaries, "_shipped", lambda program: None)
        monkeypatch.setattr(
            ffmpeg_binaries,
            "shutil",
            type("S", (), {"which": staticmethod(lambda n: "/dev/bin/" + n)})(),
        )
        assert ffmpeg_binaries.resolve_binaries() is None


class TestYtDlpPinning:
    def test_fixups_are_pinned_off_without_changing_the_format(self, monkeypatch):
        import types

        module = types.ModuleType("yt_dlp")
        seen: dict = {}

        class FakeYDL:
            def __init__(self, options):
                seen.update(options)

            def download(self, urls):
                out = Path(seen["outtmpl"].replace("%(ext)s", "m4a"))
                out.write_bytes(b"audio")

        cast(Any, module).YoutubeDL = FakeYDL
        monkeypatch.setitem(sys.modules, "yt_dlp", module)
        with downloader.temp_audio_download("https://x"):
            pass
        assert seen["fixup"] == "never"
        assert seen["format"] == "bestaudio/best"
        assert "postprocessors" not in seen

    def test_ffmpeg_presence_does_not_reroute_typical_audio(self):
        pytest.importorskip("yt_dlp")
        import importlib

        dl = importlib.import_module("yt_dlp.downloader")
        get_suitable = dl.get_suitable_downloader
        # yt_dlp/downloader/__init__.py:106-123 keys on protocol, not ffmpeg availability.
        cases = (
            ({"protocol": "https", "url": "https://cdn.example/a.m4a", "ext": "m4a"}, dl.HttpFD),
            (
                {"protocol": "http_dash_segments", "url": "https://cdn.example/a.m4a", "ext": "m4a"},
                dl.DashSegmentsFD,
            ),
            ({"protocol": "m3u8_native", "url": "https://cdn.example/a.m3u8", "ext": "mp4"}, dl.HlsFD),
        )
        options = {"format": "bestaudio/best", "fixup": "never", "quiet": True, "noplaylist": True}
        for info, expected in cases:
            assert get_suitable(dict(info), dict(options)) is expected, info["protocol"]
        live = {"protocol": "m3u8", "url": "https://cdn.example/a.m3u8", "is_live": True}
        assert get_suitable(live, dict(options)) is dl.FFmpegFD


class TestNoAvInProduction:
    def test_no_module_under_voice_typer_imports_av(self):
        offenders = []
        for path in (ROOT / "voice_typer").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\b(?:import\s+av|from\s+av)\b", text):
                offenders.append(str(path.relative_to(ROOT)))
        assert offenders == [], f"production code still imports av: {offenders}"


class TestParityWithPyavReference:
    """The new decoder must be interchangeable with the retired one."""

    @staticmethod
    def _compare(path: Path, **kwargs) -> tuple[int, int, int, float]:
        from tests import _reference_av_decoder as reference

        old = list(reference.decode_chunks(str(path), **kwargs))
        new = list(decoder.decode_chunks(str(path), **kwargs))
        assert len(old) == len(new)
        assert [c.shape for c in old] == [c.shape for c in new]
        assert {c.dtype for c in old} == {c.dtype for c in new} == {np.dtype("float32")}
        assert all(c.ndim == 1 for c in old + new)
        samples = sum(c.size for c in new)
        diffs = [
            float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64)))) for a, b in zip(old, new, strict=True)
        ]
        diff = max(diffs, default=0.0)
        return len(new), decoder.CHUNK_SAMPLES, samples, diff

    @requires_ffmpeg
    @pytest.mark.parametrize("path", [REPO_WAV], ids=["repo_fixture"])
    def test_repo_fixture_is_bit_identical(self, path):
        chunks, chunk_size, samples, diff = self._compare(path)
        assert (chunks, chunk_size, samples, diff) == (1, 80_000, 16_000, 0.0)

    @requires_ffmpeg
    @pytest.mark.parametrize("rate", [16_000, 44_100])
    def test_generated_tone_is_bit_identical(self, tmp_path, rate):
        wav = tmp_path / f"tone_{rate}.wav"
        _write_wav(wav, 12, rate=rate)
        chunks, chunk_size, samples, diff = self._compare(wav)
        assert (chunks, chunk_size, samples) == (3, 80_000, 192_000)
        assert diff == 0.0

    @requires_ffmpeg
    def test_seek_is_bit_identical(self, tmp_path):
        wav = tmp_path / "seek.wav"
        _write_wav(wav, 12)
        chunks, chunk_size, samples, diff = self._compare(wav, start_seconds=2.0)
        assert (chunks, chunk_size, samples) == (2, 80_000, 160_000)
        assert diff == 0.0
