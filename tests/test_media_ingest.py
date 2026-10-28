"""Unit tests for the media_ingest package (ADR-0023 Phase 1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from voice_typer.server.media_ingest import errors as errors_mod
from voice_typer.server.media_ingest.jobs import MediaJobManager
from voice_typer.server.media_ingest.sources import classify_source


class TestClassifySource:
    def test_http_url(self):
        assert classify_source("https://example.com/a.mp4").kind == "url"

    def test_file_path(self):
        src = classify_source("C:\\media\\clip.mp4")
        assert src.kind == "file"

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            classify_source("   ")


class TestJobManager:
    def test_start_and_snapshot(self):
        mgr = MediaJobManager()
        job = mgr.start("f", lambda j: {"ok": True})
        assert job.job_id
        mgr.wait(5.0)
        # A finished job leaves the running snapshot empty.
        assert mgr.snapshots() == []

    def test_running_snapshot_carries_phase_and_progress(self):
        import threading

        mgr = MediaJobManager()
        release = threading.Event()
        entered = threading.Event()

        def _runner(job):
            job.phase = "transcribing"
            job.progress = 0.5
            entered.set()
            release.wait(timeout=5)
            return {}

        job = mgr.start("a", _runner)
        assert entered.wait(timeout=5)
        snaps = mgr.snapshots()
        assert [s["job_id"] for s in snaps] == [job.job_id]
        assert snaps[0]["phase"] == "transcribing"
        assert snaps[0]["progress"] == 0.5
        release.set()
        mgr.wait(5.0)

    def test_start_rejected_at_capacity(self):
        import threading

        mgr = MediaJobManager(max_jobs=2)
        gate = threading.Event()
        release = threading.Event()

        def _runner(job):
            gate.set()
            release.wait(timeout=5)
            return {}

        mgr.start("a", _runner)
        mgr.start("b", _runner)
        assert gate.wait(timeout=5)
        assert mgr.running_count() == 2
        assert mgr.has_capacity() is False
        with pytest.raises(errors_mod.MediaIngestError):
            mgr.start("c", lambda j: {})
        release.set()
        mgr.wait(5.0)
        # A freed slot accepts the next job immediately.
        assert mgr.has_capacity() is True

    def test_jobs_run_concurrently(self):
        """Two jobs are inside their runner at the same time (the whole point)."""
        import threading

        mgr = MediaJobManager(max_jobs=2)
        inside = threading.Semaphore(0)
        both = threading.Barrier(2, timeout=5)

        def _runner(job):
            inside.release()
            both.wait()  # raises BrokenBarrierError unless both threads arrive
            return {}

        mgr.start("a", _runner)
        mgr.start("b", _runner)
        assert inside.acquire(timeout=5)
        assert inside.acquire(timeout=5)
        mgr.wait(5.0)
        assert mgr.running_count() == 0

    def test_cancel_signals_event(self):
        import threading

        mgr = MediaJobManager()
        gate = threading.Event()
        release = threading.Event()

        def _runner(job):
            gate.set()
            release.wait(timeout=5)
            return {}

        job = mgr.start("a", _runner)
        assert gate.wait(timeout=5)
        assert mgr.cancel() == [job.job_id]
        release.set()
        mgr.wait(5.0)

    def test_cancel_one_of_many_leaves_the_others_running(self):
        import threading

        mgr = MediaJobManager(max_jobs=3)
        gate = threading.Event()
        release = threading.Event()

        def _runner(job):
            gate.set()
            release.wait(timeout=5)
            return {}

        first = mgr.start("a", _runner)
        second = mgr.start("b", _runner)
        assert gate.wait(timeout=5)
        assert mgr.cancel(first.job_id) == [first.job_id]
        assert first.cancel_event.is_set()
        assert not second.cancel_event.is_set()
        release.set()
        mgr.wait(5.0)

    def test_cancel_idle_returns_empty(self):
        assert MediaJobManager().cancel() == []

    def test_cancel_unknown_id_is_a_no_op(self):
        import threading

        mgr = MediaJobManager()
        release = threading.Event()
        gate = threading.Event()

        def _runner(job):
            gate.set()
            release.wait(timeout=5)
            return {}

        mgr.start("a", _runner)
        assert gate.wait(timeout=5)
        assert mgr.cancel("does-not-exist") == []
        release.set()
        mgr.wait(5.0)


class TestAsrLane:
    """The shared model decodes one job at a time, and abort never crosses."""

    def test_lane_serializes_decodes(self):
        import threading
        import time

        mgr = MediaJobManager(max_jobs=2)
        order: list[tuple[str, str]] = []
        lock = threading.Lock()

        def _runner(job):
            with mgr.asr_lane(job):
                with lock:
                    order.append(("enter", job.job_id))
                time.sleep(0.05)
                with lock:
                    order.append(("exit", job.job_id))
            return {}

        mgr.start("a", _runner)
        mgr.start("b", _runner)
        mgr.wait(5.0)
        # Strictly alternating enter/exit: no two decodes overlap.
        assert [kind for kind, _ in order] == ["enter", "exit", "enter", "exit"]

    def test_the_manager_has_no_engine_handle_to_abort(self):
        """The manager cannot fire the shared flag: it never holds a backend.

        The previous version built a fake backend and asserted it saw zero
        ``request_abort``/``clear_abort`` calls — but the manager was never
        given that object, so the assertion held no matter what the lane did.
        Pin the structure that makes the guarantee real instead: no attribute
        of the manager exposes an abort-capable object, so ``asr_lane`` (and
        ``cancel``) have nothing engine-shaped to reach.
        """
        mgr = MediaJobManager()
        job = mgr.start("a", lambda j: {})
        mgr.wait(5.0)
        assert job.status == "completed"
        abort_capable = [
            name
            for name, value in vars(mgr).items()
            if callable(getattr(value, "request_abort", None))
            or callable(getattr(value, "clear_abort", None))
        ]
        assert abort_capable == [], (
            f"the job manager holds an abort-capable handle ({abort_capable}): "
            "the ASR lane or a cancel could then fire the shared engine flag"
        )

    def test_cancel_sets_only_the_jobs_own_event(self):
        """Cancel is scoped: the job's Event flips and no sibling's does."""
        import threading

        mgr = MediaJobManager(max_jobs=2)
        holding = threading.Event()
        release = threading.Event()

        def _runner(job):
            with mgr.asr_lane(job):
                holding.set()
                release.wait(timeout=5)
            return {}

        job = mgr.start("a", _runner)
        # Second job blocks on the lane, so it is still running when the
        # cancel lands on the first one.
        other = mgr.start("b", _runner)
        assert holding.wait(timeout=5)
        assert mgr.cancel(job.job_id) == [job.job_id]
        assert job.cancel_event.is_set() is True, "cancel must set the job's own Event"
        assert other.cancel_event.is_set() is False, "cancel leaked to another job"
        release.set()
        mgr.wait(5.0)

    def test_cancelling_a_waiting_job_never_aborts_the_owner(self):
        """A queued job's cancel must not touch the decode holding the model."""
        import threading

        mgr = MediaJobManager(max_jobs=2)
        holding = threading.Event()
        release = threading.Event()

        def _holder(job):
            with mgr.asr_lane(job):
                holding.set()
                release.wait(timeout=5)
            return {}

        def _waiter(job):
            with mgr.asr_lane(job):
                return {}

        owner = mgr.start("a", _holder)
        assert holding.wait(timeout=5)
        waiter = mgr.start("b", _waiter)
        assert mgr.cancel(waiter.job_id) == [waiter.job_id]
        assert owner.cancel_event.is_set() is False, "the owner's own Event was cancelled"
        release.set()
        mgr.wait(5.0)


class TestJobErrorCodes:
    """The ``media_transcribe_error`` code must be a REGISTERED code.

    ``tests/test_error_codes_registry.py`` only proves the literal is
    registered; this pins WHICH code, because the renderer branches on it
    (``isNoModelError``) to offer the "Open Models" recovery action.
    """

    @staticmethod
    def _code_for(exc: Exception) -> str:
        import threading

        events: list[dict] = []
        ready = threading.Event()
        mgr = MediaJobManager(on_event=lambda e: (events.append(e), ready.set()))

        def _runner(_job):
            raise exc

        job = mgr.start("src", _runner)
        assert ready.wait(timeout=5), "the job thread never emitted an event"
        assert job.status == "failed"
        errors = [e for e in events if e.get("type") == "media_transcribe_error"]
        assert errors, f"expected a media_transcribe_error event, got {events!r}"
        return str(errors[0]["data"]["code"])

    def test_missing_model_maps_to_namespaced_no_model(self):
        """A missing/corrupt model must surface as ``server.no_model``.

        The old bare ``no_engine_loaded`` literal was not in the error registry,
        which failed ``test_error_codes_registry``.
        """
        from voice_typer.server.asr_errors import ModelNotDownloadedError

        assert self._code_for(ModelNotDownloadedError("no model")) == "server.no_model"

    def test_model_integrity_failure_maps_to_no_model(self):
        from voice_typer.server.asr_errors import ModelIntegrityError

        assert self._code_for(ModelIntegrityError("corrupt")) == "server.no_model"

    def test_unrelated_failure_stays_internal_error(self):
        """Only the ASR model errors get the no-model treatment."""
        assert self._code_for(RuntimeError("boom")) == "internal_error"


class TestEngineLoop:
    def test_windows_join_text(self):
        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        # 25 x 5 s = one full window (120 s) + a tail flush.
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(25)]

        class _Backend:
            def __init__(self):
                self.calls = 0

            def transcribe_with_fallback(self, audio, *a, **k):
                self.calls += 1
                return f"w{self.calls}"

            def request_abort(self):
                pass

        backend = _Backend()
        state = loop.transcribe_windows(iter(chunks), backend)
        assert state.text == "w1 w2"
        assert state.decoded_seconds == pytest.approx(125.0)
        assert backend.calls == 2

    def test_window_is_one_batched_super_chunk(self):
        """The window size is the engine's batched contract, not a free knob."""
        from voice_typer.server.media_ingest import engine_loop as loop
        from voice_typer.server.transcription_batching import (
            _BATCHED_MIN_DURATION_S,
            _BATCHED_SUPER_CHUNK_S,
        )

        # Above the batched minimum the parallel (batch_size=8) pipeline runs;
        # at the super-chunk size it receives the window as one single piece.
        assert loop.WINDOW_SECONDS == _BATCHED_SUPER_CHUNK_S
        assert loop.WINDOW_SECONDS > _BATCHED_MIN_DURATION_S

    def test_cancel_returns_partial(self):
        import threading

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32)]

        class _NoopBackend:
            def transcribe_with_fallback(self, audio, *a, **k):
                raise AssertionError("must not transcribe after cancel")

            def request_abort(self):
                pass

        event = threading.Event()
        event.set()
        # Cooperative cancel: no raise, the partial state is returned so
        # the caller can persist it (ADR-0023 E14).
        state = loop.transcribe_windows(iter(chunks), _NoopBackend(), cancel_event=event)
        assert state.text == ""
        assert state.decoded_seconds == pytest.approx(0.0)

    def test_lane_wraps_every_decode(self):
        """A window decode runs inside the caller's lane (one shared model)."""
        import contextlib

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(25)]
        depth = {"now": 0, "max": 0}
        lanes: list[int] = []

        @contextlib.contextmanager
        def _lane():
            depth["now"] += 1
            depth["max"] = max(depth["max"], depth["now"])
            lanes.append(1)
            try:
                yield
            finally:
                depth["now"] -= 1

        class _Backend:
            def transcribe_with_fallback(self, audio, *a, **k):
                assert depth["now"] == 1, "decode ran outside the lane"
                return "w"

            def request_abort(self):
                pass

        state = loop.transcribe_windows(iter(chunks), _Backend(), lane=_lane)
        assert state.text == "w w"
        assert len(lanes) == 2, "one lane acquisition per window"
        assert depth["max"] == 1

    def test_cancelled_job_skips_the_decode_once_it_gets_the_lane(self):
        """A job cancelled while queued must not decode when its turn comes."""
        import contextlib
        import threading

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(25)]
        event = threading.Event()

        @contextlib.contextmanager
        def _lane():
            # The cancel lands exactly while this job waits for the model.
            event.set()
            yield

        class _Backend:
            def transcribe_with_fallback(self, audio, *a, **k):
                raise AssertionError("decoded a window nobody wants")

            def request_abort(self):
                pass

        state = loop.transcribe_windows(
            iter(chunks), _Backend(), cancel_event=event, lane=_lane
        )
        assert state.text == ""

    def test_cancelling_a_job_never_fires_the_engine_wide_abort(self):
        """A media cancel must not touch the engine's shared abort signal.

        That signal is a single flag shared with dictation: firing it here
        truncated whichever decode was running (a recording, or another job)
        while the job still reported "completed".
        """
        import threading

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(25)]
        aborts = []

        class _Backend:
            def transcribe_with_fallback(self, audio, *a, **k):
                return "w"

            def request_abort(self):
                aborts.append(1)

            def clear_abort(self):
                aborts.append("clear")

        event = threading.Event()
        event.set()
        state = loop.transcribe_windows(iter(chunks), _Backend(), cancel_event=event)
        assert state.text == ""
        assert aborts == [], "a media cancel fired or cleared the engine-wide abort"

    def test_a_dictation_cancel_does_not_stop_a_media_window(self):
        """The engine-wide flag belongs to dictation; a scoped media call ignores it.

        The previous version set an attribute nothing read and asserted the
        transcript was non-empty, so it passed no matter what the loop passed
        down. This fake polls the flag the way the engines do — the scoped
        Event when it gets one, otherwise ``self.engine_abort`` — so the
        no-argument run is a control that MUST truncate (proving the flag is
        live) while the scoped run must be byte-identical to a clean engine.
        """
        import threading

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(25)]

        class _Backend:
            """Polls exactly what the engines poll: scoped Event, else the flag."""

            def __init__(self, engine_abort: bool) -> None:
                self.engine_abort = engine_abort
                self.calls = 0

            def transcribe_with_fallback(self, audio, *args, **kwargs):
                self.calls += 1
                scoped = kwargs.get("abort_event")
                if scoped is not None:
                    return "" if scoped.is_set() else "window"
                # A dictation cancel left the engine-wide flag set.
                return "" if self.engine_abort else "window"

            def request_abort(self):
                pass

        # Control: the flag is live, so an unscoped call decodes nothing.
        flagged = _Backend(engine_abort=True)
        assert loop.transcribe_windows(iter(chunks), flagged).text == ""
        assert flagged.calls > 0, "the control never reached the decode"

        clean = _Backend(engine_abort=False)
        expected = loop.transcribe_windows(iter(chunks), clean)

        scoped = _Backend(engine_abort=True)
        state = loop.transcribe_windows(iter(chunks), scoped, cancel_event=threading.Event())

        assert expected.text, "the clean control produced no transcript"
        assert state.text == expected.text, "a dictation cancel truncated a media decode"
        assert len(state.texts) == len(expected.texts)

    def test_media_passes_its_own_event_as_the_scoped_abort_source(self):
        """The decode receives ``abort_event=<job event>``, not the engine's."""
        import threading

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(10)]
        seen: list[object] = []

        class _Backend:
            def transcribe_with_fallback(self, audio, *a, **k):
                seen.append(k.get("abort_event"))
                return "w"

            def request_abort(self):
                pass

        event = threading.Event()
        loop.transcribe_windows(iter(chunks), _Backend(), cancel_event=event)
        assert seen and all(item is event for item in seen), (
            "the window decode did not receive the job's own cancel event"
        )

    def test_a_backend_without_scoped_abort_still_decodes(self):
        """A third-party backend taking only ``(audio)`` must not get the kwarg.

        Every built-in engine now accepts ``abort_event``; the probe still has
        to cover the backend that does not, or a plugin would break on a
        keyword it cannot take.
        """
        import threading

        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(10)]

        class _Backend:
            def transcribe_with_fallback(self, audio):
                return "w"

            def request_abort(self):
                pass

        state = loop.transcribe_windows(
            iter(chunks), _Backend(), cancel_event=threading.Event()
        )
        assert state.text, "a backend without abort_event support stopped decoding"

    @pytest.mark.parametrize("engine_name", ["ParakeetEngine", "QwenEngine", "CloudEngine"])
    def test_every_builtin_engine_accepts_the_scoped_event(self, engine_name):
        """Media cancel only works if the real engines take ``abort_event``.

        The probe is feature-detected, so a built-in engine that dropped the
        keyword would silently fall back to the engine-wide flag path — the
        cross-talk this whole design removes. Pin the three real classes.
        """
        from voice_typer.server.cloud._engine import CloudEngine
        from voice_typer.server.media_ingest.engine_loop import _accepts_scoped_abort
        from voice_typer.server.parakeet_engine import ParakeetEngine
        from voice_typer.server.qwen_engine import QwenEngine

        engines = {
            "ParakeetEngine": ParakeetEngine,
            "QwenEngine": QwenEngine,
            "CloudEngine": CloudEngine,
        }
        assert _accepts_scoped_abort(engines[engine_name]) is True

    def test_progress_reports_fraction_and_eta(self):
        from voice_typer.server.media_ingest import engine_loop as loop

        sr = loop.TARGET_SAMPLE_RATE
        chunks = [np.zeros(sr * 5, dtype=np.float32) for _ in range(6)]

        class _Backend:
            def transcribe_with_fallback(self, audio, *a, **k):
                return "w"

            def request_abort(self):
                pass

        seen: list[tuple[float, float | None]] = []
        state = loop.transcribe_windows(
            iter(chunks),
            _Backend(),
            on_progress=lambda frac, eta: seen.append((frac, eta)),
            total_seconds=30.0,
        )
        assert state.decoded_seconds == pytest.approx(30.0)
        assert seen, "progress callback never fired"
        fracs = [f for f, _ in seen]
        assert fracs == sorted(fracs)
        assert 0.0 < fracs[0] < 1.0
        assert seen[-1][0] == pytest.approx(1.0)
        assert seen[-1][1] == pytest.approx(0.0)


class TestJobManagerOutcomeLogging:
    """Every job outcome leaves a durable log line (the toast is ephemeral)."""

    def test_success_logs_start_and_completion(self, caplog):
        import logging

        from voice_typer.server.media_ingest.jobs import MediaJobManager

        manager = MediaJobManager()
        with caplog.at_level(logging.INFO, logger="voice_typer.server.media_ingest.jobs"):
            job = manager.start(
                r"C:\Users\me\Downloads\clip.mp3", lambda j: {"row_id": 7, "chars": 42}
            )
            # Status flips before the outcome line: join, don't poll.
            manager.wait(5.0)

        assert job.status == "completed"
        assert "[MEDIA] job start" in caplog.text
        assert "clip.mp3" in caplog.text
        assert "[MEDIA] job completed" in caplog.text
        assert "row_id=7" in caplog.text

    def test_failure_logs_the_real_cause(self, caplog):
        import logging

        from voice_typer.server.media_ingest.errors import DECODE_FAILED, MediaIngestError
        from voice_typer.server.media_ingest.jobs import MediaJobManager

        def _boom(job):
            raise MediaIngestError(DECODE_FAILED, "media file not found: clip.mp3")

        manager = MediaJobManager()
        with caplog.at_level(logging.ERROR, logger="voice_typer.server.media_ingest.jobs"):
            job = manager.start("clip.mp3", _boom)
            manager.wait(5.0)

        assert job.status == "failed"
        assert "[MEDIA] job failed" in caplog.text
        assert "decode_failed" in caplog.text
        assert "media file not found" in caplog.text


class TestStorageExport:
    @pytest.mark.parametrize("fmt", ["txt", "srt", "vtt", "json"])
    def test_export_formats(self, tmp_path, fmt):
        from voice_typer.server.media_ingest import storage as storage_mod

        out = storage_mod.export_text("hello world", str(tmp_path / f"out.{fmt}"), fmt=fmt)
        body = Path(out).read_text(encoding="utf-8")
        assert "hello world" in body

    def test_export_bad_format(self, tmp_path):
        from voice_typer.server.media_ingest import storage as storage_mod

        with pytest.raises(ValueError):
            storage_mod.export_text("x", str(tmp_path / "out.zzz"), fmt="zzz")


class TestUrlResolver:
    def test_selects_audio_only_url(self):
        from voice_typer.server.media_ingest import url_resolver as resolver

        class _DL:
            def __init__(self, options):
                self.options = options

            def extract_info(self, url, download=False):
                assert download is False
                audio = {
                    "url": "https://cdn.example/a.m4a",
                    "vcodec": "none",
                    "acodec": "mp4a",
                    "protocol": "https",
                    "abr": 128,
                }
                video = {
                    "url": "https://cdn.example/v.mp4",
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "protocol": "https",
                    "abr": 256,
                }
                return {
                    "title": "Demo",
                    "duration": 61.0,
                    "webpage_url": url,
                    "formats": [audio, video],
                }

        resolved = resolver.resolve_media_url(
            "https://example.com/watch?v=1",
            factory=_DL,
        )
        assert resolved.audio_url == "https://cdn.example/a.m4a"
        assert resolved.title == "Demo"

    def test_rejects_playlist(self):
        from voice_typer.server.media_ingest import url_resolver as resolver

        class _DL:
            def __init__(self, options):
                pass

            def extract_info(self, url, download=False):
                return {"_type": "playlist", "entries": []}

        with pytest.raises(errors_mod.MediaIngestError):
            resolver.resolve_media_url("https://example.com/list", factory=_DL)


class TestJsRuntime:
    def test_prefers_deno(self, tmp_path):
        from voice_typer.server.media_ingest import runtime as js_runtime

        def _which(name, path=None):
            return "/bin/deno" if name == "deno" else None

        found = js_runtime.find_js_runtime(which=_which, pack_root=tmp_path)
        assert found is not None and found.name == "deno"
        assert js_runtime.js_runtime_options(found) == {"deno": {"path": "/bin/deno"}}

    def test_options_are_accepted_by_yt_dlp(self):
        """Contract pin: yt-dlp requires ``{runtime: {config}}``.

        A bare path string (``{"deno": "/bin/deno"}``) made every URL
        resolve raise ``ValueError: Invalid js_runtimes format`` at
        ``YoutubeDL`` construction, surfacing as "The media could not be
        transcribed".
        """
        from typing import Any

        from voice_typer.server.media_ingest import runtime as js_runtime
        from yt_dlp import YoutubeDL

        for name, path in (("deno", "/bin/deno"), ("node", "/bin/node")):
            options = js_runtime.js_runtime_options(js_runtime.JsRuntime(name=name, path=path))
            assert options == {name: {"path": path}}
            params: Any = {"quiet": True, "no_warnings": True, "js_runtimes": options}
            with YoutubeDL(params):  # raises ValueError on a bare path string
                pass

    def test_rejects_old_node(self, monkeypatch, tmp_path):
        import subprocess

        from voice_typer.server.media_ingest import runtime as js_runtime

        class _Done:
            returncode = 0
            stdout = "v18.0.0\n"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Done())

        def _which(name, path=None):
            return "/bin/node" if name == "node" else None

        found = js_runtime.find_js_runtime(which=_which, pack_root=tmp_path)
        assert found is None


class TestMiniUpdate:
    def test_installed_versions_prefer_dunder_version(self, monkeypatch):
        """``yt_dlp.version`` is a MODULE: only real version strings"""
        import sys
        import types

        from voice_typer.server.media_ingest import mini_update as extractor_update

        fake_pkg = types.ModuleType("yt_dlp")
        fake_sub = types.ModuleType("yt_dlp.version")  # no __version__ here
        fake_pkg.version = fake_sub
        fake_pkg.__version__ = "2026.8.19"
        fake_ejs = types.ModuleType("yt_dlp_ejs")
        fake_ejs.__version__ = "0.8.0"
        monkeypatch.setitem(sys.modules, "yt_dlp", fake_pkg)
        monkeypatch.setitem(sys.modules, "yt_dlp_ejs", fake_ejs)
        assert extractor_update.installed_extractor_versions() == ("2026.8.19", "0.8.0")

    def test_installed_versions_fall_back_to_submodule(self, monkeypatch):
        """A package exposing its version only via ``<pkg>.version``"""
        import sys
        import types

        from voice_typer.server.media_ingest import mini_update as extractor_update

        fake_pkg = types.ModuleType("yt_dlp")
        fake_sub = types.ModuleType("yt_dlp.version")
        fake_sub.__version__ = "2026.1.1"
        fake_pkg.version = fake_sub
        monkeypatch.setitem(sys.modules, "yt_dlp", fake_pkg)
        monkeypatch.delitem(sys.modules, "yt_dlp_ejs", raising=False)
        backend, _solver = extractor_update.installed_extractor_versions()
        assert backend == "2026.1.1"
        assert "module" not in backend

    def test_installed_versions_accept_plain_version_string(self, monkeypatch):
        """``yt_dlp_ejs.version`` is a plain string (not a module)."""
        import sys
        import types

        from voice_typer.server.media_ingest import mini_update as extractor_update

        fake_pkg = types.ModuleType("yt_dlp")
        fake_pkg.__version__ = "2026.08.19"
        fake_ejs = types.ModuleType("yt_dlp_ejs")
        fake_ejs.version = "0.8.0"
        monkeypatch.setitem(sys.modules, "yt_dlp", fake_pkg)
        monkeypatch.setitem(sys.modules, "yt_dlp_ejs", fake_ejs)
        assert extractor_update.installed_extractor_versions() == ("2026.08.19", "0.8.0")

    def test_newer_remote_marks_update(self, tmp_path):
        from voice_typer.server.media_ingest import mini_update as extractor_update

        state_file = tmp_path / "media-extractor.json"

        def _get(url, max_bytes=0, timeout=0):
            return '{"yt_dlp_version": "2025.01.01"}'

        state = extractor_update.check_refresh(
            local_backend="2024.01.01",
            local_solver="1",
            state_file=state_file,
            now=1,
            http_get=_get,
        )
        assert state.update_available is True
        assert state_file.is_file()
        assert extractor_update.load_state(state_file) is not None


class TestExtractorRefreshStartupCheck:
    """ADR-0023: the launch-time extractor probe is CHECK-ONLY."""

    def test_shutdown_short_circuits_before_any_check(self, monkeypatch):
        import threading

        from voice_typer.server import startup_tasks
        from voice_typer.server.media_ingest import mini_update as extractor_update

        calls = {"n": 0}

        def _spy(**kwargs):
            calls["n"] += 1
            raise AssertionError("must not run after shutdown")

        monkeypatch.setattr(extractor_update, "check_refresh", _spy)
        event = threading.Event()
        event.set()
        result = startup_tasks.check_media_extractor_refresh(object(), event)
        assert result == {"checked": False, "reason": "shutdown"}
        assert calls["n"] == 0

    def test_reports_update_without_downloading(self, monkeypatch):
        from voice_typer.server import startup_tasks
        from voice_typer.server.media_ingest import mini_update as extractor_update

        state = extractor_update.ExtractorRefreshState(
            backend="yt-dlp",
            backend_version="2024.01.01",
            solver_version="1",
            checked_at=123,
            update_available=True,
            remote_backend_version="2025.01.01",
            remote_solver_version="2",
        )
        monkeypatch.setattr(extractor_update, "check_refresh", lambda **kwargs: state)
        result = startup_tasks.check_media_extractor_refresh(object())
        assert result == {"checked": True, "update_available": True, "checked_at": 123}

    def test_failure_is_swallowed(self, monkeypatch):
        from voice_typer.server import startup_tasks
        from voice_typer.server.media_ingest import mini_update as extractor_update

        def _boom(**kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(extractor_update, "check_refresh", _boom)
        assert startup_tasks.check_media_extractor_refresh(object()) == {
            "checked": False,
            "reason": "error",
        }

    def test_module_has_no_install_path(self):
        """The freshness module must stay metadata-only (no exec/download)."""
        import inspect

        from voice_typer.server.media_ingest import mini_update as extractor_update

        source = inspect.getsource(extractor_update)
        for forbidden in ("subprocess", "urlretrieve", "pip install", "shutil.copy"):
            assert forbidden not in source
