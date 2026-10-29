"""Unit tests for ``MediaHandlersMixin`` (ADR-0023 Phase 1)."""

from __future__ import annotations

import pytest


class TestMediaStartValidation:
    def test_missing_source_rejected(self, ipc_server, fake_service):
        resp = ipc_server._handle_media_transcribe_start({}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.missing_field"

    def test_url_requires_media_consent(self, ipc_server, fake_service):
        ipc_server.app.config.media_url_consent = False
        resp = ipc_server._handle_media_transcribe_start({"source": "https://example.com/a.mp4"}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.consent_required"
        assert resp["data"]["consent_field"] == "media_url_consent"

    def test_no_model_selected_rejected(self, ipc_server, fake_service):
        ipc_server.app.config.media_url_consent = True
        ipc_server.app.models.active_transcriber.return_value = None
        ipc_server.app.config.model_size = ""
        resp = ipc_server._handle_media_transcribe_start({"source": "https://example.com/a.mp4"}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.no_model"

    def test_local_file_starts_job(self, ipc_server, fake_service, monkeypatch, tmp_path):
        import voice_typer.server.media_ingest.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        started = {}

        class _Mgr:
            def start(self, source, runner, *, client_id=None, export_path=None):
                started["source"] = source
                started["client_id"] = client_id

                class _J:
                    job_id = "abc123"
                    status = "running"
                    client_id = None

                _J.client_id = client_id
                return _J()

        monkeypatch.setattr(jobs_mod, "get_job_manager", lambda: _Mgr())
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f), "client_id": "media-row-7"}, {})
        assert resp["type"] == "media_transcribe_result"
        assert resp["data"]["job_id"] == "abc123"
        assert started["source"] == str(f)
        # The renderer's correlation token reaches the job (and comes back
        # on the ack), so a push can be bound to the row that asked for it.
        assert started["client_id"] == "media-row-7"
        assert resp["data"]["client_id"] == "media-row-7"


class TestExportPathCollision:
    def test_two_running_jobs_cannot_share_one_export_path(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """Two jobs writing one file would clobber each other's transcript."""
        import threading

        import voice_typer.server.media_ingest.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        mgr = jobs_mod.get_job_manager()
        release = threading.Event()
        started = threading.Event()

        def _hold(_job):
            started.set()
            release.wait(timeout=5)
            return {}

        target = str(tmp_path / "out.txt")
        first = mgr.start("already-running", _hold, export_path=target)
        assert started.wait(timeout=5)

        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f), "export_path": target}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.invalid_field"
        assert resp["data"]["field"] == "export_path"
        assert mgr.running_count() == 1, "the refused start created a job anyway"

        release.set()
        mgr.wait(5.0)
        assert first.job_id

    def test_export_path_is_free_again_once_the_job_finishes(self, ipc_server, fake_service, monkeypatch, tmp_path):
        import voice_typer.server.media_ingest.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        mgr = jobs_mod.get_job_manager()
        target = str(tmp_path / "out.txt")
        done = mgr.start("done-already", lambda _j: {}, export_path=target)
        mgr.wait(5.0)
        assert done.job_id
        # The registry only tracks running jobs, so the path is free again.
        assert mgr.export_path_in_use(target) is False


class TestMediaCancelStatus:
    def test_cancel_idle(self, ipc_server, fake_service, monkeypatch):
        import voice_typer.server.media_ingest.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        resp = ipc_server._handle_media_transcribe_cancel({}, {})
        assert resp["type"] == "media_transcribe_result"
        assert resp["data"] == {"cancelled": 0, "job_ids": []}

    def test_status_idle(self, ipc_server, fake_service, monkeypatch):
        import voice_typer.server.media_ingest.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        resp = ipc_server._handle_media_transcribe_status({}, {})
        assert resp["type"] == "media_transcribe_result"
        # The cap travels with the status so the renderer never guesses it.
        assert resp["data"] == {"jobs": [], "max_jobs": 4}


class TestMediaUrlStart:
    def test_url_is_handed_to_the_job_without_resolving_inline(self, ipc_server, fake_service, monkeypatch):
        """Resolution is a network round trip: it belongs in the job thread,
        otherwise a batch of links starts one-at-a-time behind the IPC ack."""
        import voice_typer.server.media_ingest.jobs as jobs_mod
        import voice_typer.server.media_ingest.runtime as js_runtime
        import voice_typer.server.media_ingest.url_resolver as resolver

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        resolved_calls = []
        monkeypatch.setattr(
            resolver,
            "resolve_media_url",
            lambda url, factory=None, js_runtimes=None: resolved_calls.append(url),
        )
        monkeypatch.setattr(js_runtime, "find_js_runtime", lambda **kwargs: None)
        started = {}

        class _Mgr:
            def start(self, source, runner, *, client_id=None, export_path=None):
                started["source"] = source

                class _J:
                    job_id = "url123"
                    status = "running"
                    client_id = None

                return _J()

        monkeypatch.setattr(jobs_mod, "get_job_manager", lambda: _Mgr())
        resp = ipc_server._handle_media_transcribe_start({"source": "https://example.com/v"}, {})
        assert resp["type"] == "media_transcribe_result"
        assert resp["data"]["job_id"] == "url123"
        assert started["source"] == "https://example.com/v"
        assert resolved_calls == [], "the handler resolved the URL inline"

    def test_missing_js_runtime_has_actionable_error(self, ipc_server, fake_service, monkeypatch):
        import voice_typer.server.media_ingest.jobs as jobs_mod
        import voice_typer.server.media_ingest.runtime as js_runtime
        import voice_typer.server.media_ingest.url_resolver as resolver
        from voice_typer.server.media_ingest.errors import RESOLVE_FAILED, MediaIngestError

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)

        def _boom(url, factory=None, js_runtimes=None):
            raise MediaIngestError(RESOLVE_FAILED, "boom")

        monkeypatch.setattr(resolver, "resolve_media_url", _boom)
        monkeypatch.setattr(js_runtime, "find_js_runtime", lambda **kwargs: None)
        resp = ipc_server._handle_media_transcribe_start({"source": "https://www.youtube.com/watch?v=x"}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.not_supported"


class TestMediaModelStartGate:
    """Selected-but-not-loaded is a start; nothing selected is not."""

    @staticmethod
    def _patch_job_manager(monkeypatch):
        import voice_typer.server.media_ingest.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_MANAGER", None)
        started = {}

        class _Mgr:
            def start(self, source, runner, *, client_id=None, export_path=None):
                started["source"] = source

                class _J:
                    job_id = "gate1"
                    status = "running"
                    client_id = None

                _J.client_id = client_id
                return _J()

        monkeypatch.setattr(jobs_mod, "get_job_manager", lambda: _Mgr())
        return started

    def test_selected_but_not_loaded_is_accepted(self, ipc_server, fake_service, monkeypatch, tmp_path):
        started = self._patch_job_manager(monkeypatch)
        ipc_server.app.models.active_transcriber.return_value = None
        ipc_server.app.models._model_downloaded_precheck.return_value = True
        ipc_server.app.config.model_size = "small.en"
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f)}, {})
        assert resp["type"] == "media_transcribe_result"
        assert started["source"] == str(f)

    def test_selected_during_a_startup_load_is_accepted(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """The engine is still loading, so active_transcriber() is None."""
        started = self._patch_job_manager(monkeypatch)
        ipc_server.app.models.active_transcriber.return_value = None
        ipc_server.app.models._model_downloaded_precheck.return_value = True
        ipc_server.app.config.model_size = "small.en"
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f)}, {})
        assert resp["type"] == "media_transcribe_result"
        assert resp["data"]["job_id"] == "gate1"
        assert started["source"] == str(f)

    def test_nothing_selected_is_rejected_with_open_models(self, ipc_server, fake_service, monkeypatch, tmp_path):
        self._patch_job_manager(monkeypatch)
        ipc_server.app.models.active_transcriber.return_value = None
        ipc_server.app.config.model_size = ""
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f)}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.no_model"

    def test_selected_but_missing_model_is_rejected_with_retry_copy(
        self, ipc_server, fake_service, monkeypatch, tmp_path
    ):
        """A bare config string is not proof: the model must be installed."""
        self._patch_job_manager(monkeypatch)
        ipc_server.app.models.active_transcriber.return_value = None
        ipc_server.app.models._model_downloaded_precheck.return_value = False
        ipc_server.app.config.model_size = "small.en"
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f)}, {})
        assert resp["type"] == "error"
        # NOT "server.no_model": the user already chose a model, so the copy
        # offers a retry rather than sending them back to the picker.
        assert resp["data"]["code"] == "no_engine_loaded"


class TestMediaValidationGate:
    """No text is persisted from an ingest that failed its own checks."""

    @staticmethod
    def _job():
        import threading
        from types import SimpleNamespace

        return SimpleNamespace(
            job_id="gate",
            cancel_event=threading.Event(),
            progress=0.0,
            client_id=None,
            ingest_tier="stream",
            expected_seconds=None,
            decoded_seconds=None,
            note=None,
            engine_label="whisper/small.en",
            quality=None,
            cancel_reason=None,
        )

    @staticmethod
    def _validated():
        return {"export_path": None, "export_format": None}

    def test_zero_chunks_is_an_error_and_never_persists(self, ipc_server, fake_service, monkeypatch):
        from voice_typer.server.media_ingest import storage as storage_mod
        from voice_typer.server.media_ingest.errors import MEDIA_TOO_SHORT, MediaIngestError

        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._finish_media_job(
                self._job(), "text", validated=self._validated(), decoded_seconds=0.0, expected_seconds=42.0
            )
        assert excinfo.value.code == MEDIA_TOO_SHORT
        assert persisted == []

    def test_truncated_ingest_is_refused(self, ipc_server, fake_service, monkeypatch):
        from voice_typer.server.media_ingest import storage as storage_mod
        from voice_typer.server.media_ingest.errors import MEDIA_TRUNCATED, MediaIngestError

        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._finish_media_job(
                self._job(), "text", validated=self._validated(), decoded_seconds=3.0, expected_seconds=30.0
            )
        assert excinfo.value.code == MEDIA_TRUNCATED
        assert persisted == []

    def test_sub_second_clip_is_too_short(self, ipc_server, fake_service, monkeypatch):
        from voice_typer.server.media_ingest import storage as storage_mod
        from voice_typer.server.media_ingest.errors import MEDIA_TOO_SHORT, MediaIngestError

        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._finish_media_job(
                self._job(), "text", validated=self._validated(), decoded_seconds=0.4, expected_seconds=None
            )
        assert excinfo.value.code == MEDIA_TOO_SHORT
        assert persisted == []

    def test_silent_media_completes_with_zero_chars(self, ipc_server, fake_service, monkeypatch):
        """Total silence is a "no speech" outcome, never a success card."""
        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest import storage as storage_mod

        persisted = []
        events = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event))
        job = self._job()
        out = ipc_server._finish_media_job(
            job,
            "thanks for watching",
            validated=self._validated(),
            decoded_seconds=30.0,
            expected_seconds=30.0,
            silent=True,
        )
        assert out == {"row_id": None, "chars": 0}
        assert persisted == []
        assert job.note == "no_speech"
        complete = [e for e in events if e["type"] == "media_transcribe_complete"]
        assert complete and complete[0]["data"]["chars"] == 0
        assert complete[0]["data"]["row_id"] is None

    def test_empty_engine_output_is_a_no_speech_outcome(self, ipc_server, fake_service, monkeypatch):
        """The hallucination gate returning "" must not read as a success."""
        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest import storage as storage_mod

        persisted = []
        events = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event))
        job = self._job()
        out = ipc_server._finish_media_job(
            job, "", validated=self._validated(), decoded_seconds=30.0, expected_seconds=30.0
        )
        assert out == {"row_id": None, "chars": 0}
        assert persisted == []
        assert job.note == "no_speech"
        complete = [e for e in events if e["type"] == "media_transcribe_complete"]
        assert complete and complete[0]["data"]["note"] == "no_speech"
        assert complete[0]["data"]["chars"] == 0

    def test_zero_decoded_local_ingest_never_persists(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """An ingest that produced no audio is an error, not a success card."""
        import threading
        from types import SimpleNamespace

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage_mod
        from voice_typer.server.media_ingest.errors import MEDIA_TOO_SHORT, MediaIngestError

        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: 30.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: iter(()))
        monkeypatch.setattr(
            loop, "transcribe_windows", lambda *a, **k: loop.WindowsState(texts=[], decoded_seconds=0.0)
        )
        job = SimpleNamespace(
            job_id="empty",
            cancel_event=threading.Event(),
            progress=0.0,
            client_id=None,
            ingest_tier=None,
            expected_seconds=None,
            decoded_seconds=None,
            note=None,
            engine_label=None,
            quality=None,
            cancel_reason=None,
        )
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._run_local_media_job(job, str(tmp_path / "clip.mp3"), {"export_path": None})
        assert excinfo.value.code == MEDIA_TOO_SHORT
        assert persisted == []

    def test_silent_local_file_is_a_no_speech_outcome(self, ipc_server, fake_service, monkeypatch, tmp_path):
        import threading
        from types import SimpleNamespace

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage_mod

        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: 12.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: iter(()))
        state = loop.WindowsState(texts=["thank you"], decoded_seconds=12.0)
        state.rms = 0.0
        state.silence_pct = 100.0
        monkeypatch.setattr(loop, "transcribe_windows", lambda *a, **k: state)
        job = SimpleNamespace(
            job_id="silent",
            cancel_event=threading.Event(),
            progress=0.0,
            client_id=None,
            ingest_tier=None,
            expected_seconds=None,
            decoded_seconds=None,
            note=None,
            engine_label=None,
            quality=None,
            cancel_reason=None,
        )
        out = ipc_server._run_local_media_job(job, str(tmp_path / "clip.mp3"), {"export_path": None})
        assert out == {"row_id": None, "chars": 0}
        assert persisted == []
        assert job.note == "no_speech"

    def test_cancelled_partial_skips_the_duration_gate(self, ipc_server, fake_service, monkeypatch):
        from voice_typer.server.media_ingest import storage as storage_mod

        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        out = ipc_server._finish_media_job(
            self._job(),
            "partial",
            validated=self._validated(),
            decoded_seconds=0.4,
            expected_seconds=30.0,
            partial=True,
        )
        assert persisted, "a cancelled partial must still be saved"
        assert out["chars"] == len("partial")


class TestMediaPhaseTaxonomy:
    """``loading_model`` is claimed only when a load actually happens."""

    @staticmethod
    def _capture(ipc_server, monkeypatch):
        phases: list[str] = []
        monkeypatch.setattr(
            ipc_server,
            "_publish_media_progress",
            lambda job, frac, phase, eta=None, duration=None: phases.append(phase),
        )
        return phases

    def test_loaded_engine_publishes_preparing(self, ipc_server, fake_service, monkeypatch):
        from types import SimpleNamespace

        phases = self._capture(ipc_server, monkeypatch)
        engine = SimpleNamespace(is_loaded=True)
        ipc_server.app.models.active_transcriber.return_value = engine
        ipc_server._publish_media_phase(SimpleNamespace(job_id="p"))
        assert phases == ["preparing"]

    def test_needs_load_publishes_loading_model_once(self, ipc_server, fake_service, monkeypatch):
        from types import SimpleNamespace

        phases = self._capture(ipc_server, monkeypatch)
        ipc_server.app.models.active_transcriber.return_value = None
        ipc_server._publish_media_phase(SimpleNamespace(job_id="p"))
        ipc_server._publish_media_progress(SimpleNamespace(job_id="p"), 0.1, "transcribing")
        assert phases == ["loading_model", "transcribing"]


class TestMediaUrlJobTiers:
    """Download-first tiering: the local audio copy is primary, the stream is
    the fallback (namespace doubles: the job body only reads those fields)."""

    @staticmethod
    def _job():
        import threading
        from types import SimpleNamespace

        # Every field the job body / outcome line touches (a real MediaJob
        # carries the same set with defaults).
        return SimpleNamespace(
            job_id="tier1",
            cancel_event=threading.Event(),
            progress=0.0,
            client_id=None,
            ingest_tier=None,
            expected_seconds=None,
            decoded_seconds=None,
            note=None,
            engine_label=None,
            quality=None,
            cancel_reason=None,
        )

    @staticmethod
    def _resolved():
        from types import SimpleNamespace

        return SimpleNamespace(
            audio_url="https://cdn.example/a.m4a",
            webpage_url="https://example.com/v",
            duration=42.0,
            subtitles_available=False,
            is_live=False,
        )

    def _patch_pipeline(
        self,
        monkeypatch,
        tmp_path,
        *,
        download_error=None,
        download_failures=99,
        probe=None,
        decoded_seconds=42.0,
        decode_error=None,
    ):
        import contextlib

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.downloader as dl
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage
        import voice_typer.server.media_ingest.url_resolver as resolver

        monkeypatch.setattr(resolver, "resolve_media_url", lambda url, **kw: self._resolved())

        calls: list[tuple] = []
        audio = tmp_path / "a.m4a"
        audio.write_bytes(b"x")
        attempts = {"n": 0}

        @contextlib.contextmanager
        def _download(url, **kwargs):
            attempts["n"] += 1
            calls.append(("download", url))
            if download_error is not None and attempts["n"] <= download_failures:
                raise download_error
            yield audio

        monkeypatch.setattr(dl, "temp_audio_download", _download)

        def _decode(src, **kw):
            calls.append(("decode", src))
            if decode_error is not None:
                raise decode_error
            return iter(())

        monkeypatch.setattr(dec, "decode_chunks", _decode)
        monkeypatch.setattr(dec, "probe_remote", lambda url, **kw: calls.append(("probe", url)) or probe)
        monkeypatch.setattr(
            loop,
            "transcribe_windows",
            lambda chunks, backend, **kw: (
                calls.append(("transcribe",)) or loop.WindowsState(texts=["ok"], decoded_seconds=decoded_seconds)
            ),
        )
        monkeypatch.setattr(storage, "persist_result", lambda *a, **k: 1)
        return calls

    def test_download_tier_runs_before_any_stream(self, ipc_server, fake_service, monkeypatch, tmp_path):
        calls = self._patch_pipeline(monkeypatch, tmp_path)
        out = ipc_server._run_url_media_job(self._job(), "https://example.com/v", None, {"use_subtitles": False})
        assert [c[0] for c in calls] == ["download", "decode", "transcribe"]
        assert out == {"row_id": 1, "chars": 2}

    def test_stream_fallback_when_download_fails(self, ipc_server, fake_service, monkeypatch, tmp_path):
        import types

        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest.errors import DOWNLOAD_FAILED, MediaIngestError

        calls = self._patch_pipeline(
            monkeypatch,
            tmp_path,
            download_error=MediaIngestError(DOWNLOAD_FAILED, "nope"),
            probe=types.SimpleNamespace(audio_streams=1, duration_seconds=42.0),
        )
        events: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event))
        job = self._job()
        job.client_id = "row-tier"
        out = ipc_server._run_url_media_job(job, "https://example.com/v", None, {"use_subtitles": False})
        # One retry, then a PROBE, and only then the stream.
        assert [c[0] for c in calls] == ["download", "download", "probe", "decode", "transcribe"]
        assert job.ingest_tier == "stream"
        assert job.note == "stream_fallback"
        assert out == {"row_id": 1, "chars": 2}
        complete = [e for e in events if e["type"] == "media_transcribe_complete"]
        assert complete, "the completion event was never published"
        assert complete[0]["data"]["tier"] == "stream"
        assert complete[0]["data"]["note"] == "stream_fallback"

    def test_stream_tier_is_refused_when_the_url_does_not_probe(
        self, ipc_server, fake_service, monkeypatch, tmp_path, caplog
    ):
        """Never stream an unverified URL, and never call the model for it."""
        import logging

        import voice_typer.server.media_ingest.engine_loop as loop
        from voice_typer.server.media_ingest.errors import DOWNLOAD_FAILED, MediaIngestError

        self._patch_pipeline(
            monkeypatch,
            tmp_path,
            download_error=MediaIngestError(DOWNLOAD_FAILED, "nope"),
            probe=None,
        )
        model_calls = []
        monkeypatch.setattr(
            loop,
            "transcribe_windows",
            lambda *a, **k: model_calls.append(1) or loop.WindowsState(texts=["x"]),
        )
        job = self._job()
        with (
            caplog.at_level(logging.WARNING, logger="voice_typer.server.ipc_server"),
            pytest.raises(MediaIngestError) as excinfo,
        ):
            ipc_server._run_url_media_job(job, "https://example.com/v", None, {"use_subtitles": False})
        assert excinfo.value.code == DOWNLOAD_FAILED
        assert model_calls == [], "the model was called for an unverifiable stream"
        assert "stream fallback refused" in caplog.text
        assert job.ingest_tier != "stream"

    def test_download_retry_recovers_without_degrading(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """One transient download failure must not demote the job to streaming."""
        from voice_typer.server.media_ingest.errors import DOWNLOAD_FAILED, MediaIngestError

        calls = self._patch_pipeline(
            monkeypatch,
            tmp_path,
            download_error=MediaIngestError(DOWNLOAD_FAILED, "nope"),
            download_failures=1,
        )
        job = self._job()
        out = ipc_server._run_url_media_job(job, "https://example.com/v", None, {"use_subtitles": False})
        assert [c[0] for c in calls] == ["download", "download", "decode", "transcribe"]
        assert job.ingest_tier == "download"
        assert job.note is None
        assert out == {"row_id": 1, "chars": 2}

    def test_subtitles_tier_records_the_source_in_history(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """No engine ran, so the row must not claim one (nor a blank model)."""
        import voice_typer.server.media_ingest.storage as storage_mod
        import voice_typer.server.media_ingest.subtitles as subs
        import voice_typer.server.media_ingest.url_resolver as resolver

        resolved = self._resolved()
        resolved.subtitles_available = True
        monkeypatch.setattr(resolver, "resolve_media_url", lambda url, **kw: resolved)
        monkeypatch.setattr(subs, "fetch_subtitles", lambda url, lang=None: "caption text")
        saved: list[str] = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, model="", **k: saved.append(model) or 1)
        job = self._job()
        out = ipc_server._run_url_media_job(job, "https://example.com/v", None, {"use_subtitles": True})
        assert out["chars"] == len("caption text")
        assert job.ingest_tier == "subtitles"
        assert saved == ["subtitles"]

    def test_truncated_download_costs_one_decode_and_never_probes(
        self, ipc_server, fake_service, monkeypatch, tmp_path
    ):
        """A truncation verdict is already known: retrying re-decodes it."""
        from voice_typer.server.media_ingest import storage as storage_mod
        from voice_typer.server.media_ingest.errors import MEDIA_TRUNCATED, MediaIngestError

        calls = self._patch_pipeline(monkeypatch, tmp_path, decoded_seconds=3.0)
        persisted = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._run_url_media_job(self._job(), "https://example.com/v", None, {"use_subtitles": False})
        assert excinfo.value.code == MEDIA_TRUNCATED
        assert [c[0] for c in calls] == ["download", "decode", "transcribe"]
        assert persisted == []

    def test_missing_audio_track_is_not_retried(self, ipc_server, fake_service, monkeypatch, tmp_path, caplog):
        """NO_AUDIO is a verdict: no second download, no stream probe."""
        import logging

        from voice_typer.server.media_ingest.errors import NO_AUDIO, MediaIngestError

        calls = self._patch_pipeline(monkeypatch, tmp_path, decode_error=MediaIngestError(NO_AUDIO, "no audio track"))
        with (
            caplog.at_level(logging.WARNING),
            pytest.raises(MediaIngestError) as excinfo,
        ):
            ipc_server._run_url_media_job(self._job(), "https://example.com/v", None, {"use_subtitles": False})
        assert excinfo.value.code == NO_AUDIO
        assert [c[0] for c in calls] == ["download", "decode"]
        assert "retrying once" not in caplog.text
        assert "stream fallback" not in caplog.text

    def test_decode_failed_from_a_downloaded_file_is_not_retried(self, ipc_server, fake_service, monkeypatch, tmp_path):
        from voice_typer.server.media_ingest.errors import DECODE_FAILED, MediaIngestError

        calls = self._patch_pipeline(
            monkeypatch, tmp_path, decode_error=MediaIngestError(DECODE_FAILED, "bad container")
        )
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._run_url_media_job(self._job(), "https://example.com/v", None, {"use_subtitles": False})
        assert excinfo.value.code == DECODE_FAILED
        assert [c[0] for c in calls] == ["download", "decode"]

    def test_truncated_stream_is_one_decode(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """The stream verdict must not be re-decoded either."""
        import types

        from voice_typer.server.media_ingest.errors import DOWNLOAD_FAILED, MEDIA_TRUNCATED, MediaIngestError

        calls = self._patch_pipeline(
            monkeypatch,
            tmp_path,
            download_error=MediaIngestError(DOWNLOAD_FAILED, "nope"),
            probe=types.SimpleNamespace(audio_streams=1, duration_seconds=42.0),
            decoded_seconds=3.0,
        )
        with pytest.raises(MediaIngestError) as excinfo:
            ipc_server._run_url_media_job(self._job(), "https://example.com/v", None, {"use_subtitles": False})
        assert excinfo.value.code == MEDIA_TRUNCATED
        assert [c[0] for c in calls] == ["download", "download", "probe", "decode", "transcribe"]

    def test_local_job_probes_total_so_progress_and_eta_work(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """A local file has no resolver-provided total: the container probe feeds
        ``total_seconds`` (fraction/ETA) plus the Duration readout."""
        import threading
        from types import SimpleNamespace

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage

        progress = []
        monkeypatch.setattr(
            ipc_server,
            "_publish_media_progress",
            lambda job, frac, phase, eta=None, duration=None: progress.append((frac, phase, eta, duration)),
        )
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: 480.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: iter(()))
        seen_kwargs = {}

        def _transcribe_windows(chunks, backend, **kw):
            seen_kwargs.update(kw)
            return loop.WindowsState(texts=["ok"], decoded_seconds=480.0)

        monkeypatch.setattr(loop, "transcribe_windows", _transcribe_windows)
        monkeypatch.setattr(storage, "persist_result", lambda *a, **k: 1)

        out = ipc_server._run_local_media_job(
            SimpleNamespace(
                job_id="local1",
                cancel_event=threading.Event(),
                progress=0.0,
                client_id=None,
                ingest_tier=None,
                expected_seconds=None,
                decoded_seconds=None,
                note=None,
                engine_label=None,
                quality=None,
                cancel_reason=None,
            ),
            r"C:\tmp\clip.mp3",
            {"export_path": None, "export_format": None},
        )

        # The fake app's engine is already loaded, so no load is claimed.
        assert progress[0][1] == "preparing"
        assert seen_kwargs["total_seconds"] == 480.0
        # Mid-job progress carries the probed total as the Duration readout.
        seen_kwargs["on_progress"](0.5, 12.0)
        assert progress[-1] == (0.5, "transcribing", 12.0, 480.0)
        assert out == {"row_id": 1, "chars": 2}


class TestMediaEngineAttribution:
    """History must name the engine that produced the text, not the config.

    A switch writes ``config.model_size`` / ``config.asr_backend`` BEFORE it
    waits for running jobs, so reading config at finish time labelled a
    transcript with a model that never saw the audio.
    """

    @staticmethod
    def _job(label):
        import threading
        from types import SimpleNamespace

        return SimpleNamespace(
            job_id="attr",
            cancel_event=threading.Event(),
            progress=0.0,
            client_id=None,
            ingest_tier="download",
            expected_seconds=None,
            decoded_seconds=None,
            note=None,
            engine_label=label,
            quality=None,
            cancel_reason=None,
        )

    @pytest.mark.parametrize(
        ("leased", "config_after_switch"),
        [
            ("whisper/small.en", "whisper/large-v3"),
            ("whisper/small.en", "cloud/openai/whisper-1"),
            ("cloud/openai/whisper-1", "whisper/small.en"),
            ("cloud/openai/whisper-1", "cloud/groq/whisper-large-v3"),
        ],
        ids=["local->local", "local->cloud", "cloud->local", "cloud->cloud"],
    )
    def test_history_label_is_the_leased_engine_after_a_switch(
        self, ipc_server, fake_service, monkeypatch, leased, config_after_switch
    ):
        from voice_typer.server.media_ingest import storage as storage_mod

        saved: list[str] = []
        monkeypatch.setattr(
            storage_mod,
            "persist_result",
            lambda *a, model="", **k: saved.append(model) or 1,
        )
        # The switch has already written the new identity into config while
        # the job was still decoding.
        ipc_server.app.config.model_size = config_after_switch
        ipc_server.app.config.asr_backend = "cloud" if config_after_switch.startswith("cloud/") else "whisper"

        job = self._job(leased)
        out = ipc_server._finish_media_job(
            job, "hello", validated={"export_path": None}, decoded_seconds=10.0, expected_seconds=10.0
        )
        assert out["chars"] == 5
        assert saved == [leased], f"History was labelled {saved!r}, not the leased engine"

    def test_four_jobs_under_a_switch_all_keep_the_old_label(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """N running jobs + a switch: every row lands on the engine it started
        with, and the switch does not proceed until they are done."""
        import threading
        import time
        import types

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.lease as lease_mod
        import voice_typer.server.media_ingest.storage as storage_mod
        from voice_typer.server.model_manager._change import ChangeMixin

        gate = lease_mod.ModelLeaseGate()
        monkeypatch.setattr(lease_mod, "get_lease_gate", lambda: gate)
        # One loaded engine, and its identity is read from the ENGINE (the
        # fake app's names are MagicMocks unless pinned).
        ipc_server.app.models.active_transcriber.return_value = types.SimpleNamespace(
            is_loaded=True, _model_size="small.en"
        )
        ipc_server.app.models.active_backend_name.return_value = "whisper"
        labels: list[str] = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, model="", **k: labels.append(model) or 1)
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: 10.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: iter(()))
        release = threading.Event()
        started = threading.Semaphore(0)

        def _transcribe(chunks, backend, **kw):
            started.release()
            release.wait(5)
            return loop.WindowsState(texts=["ok"], decoded_seconds=10.0)

        monkeypatch.setattr(loop, "transcribe_windows", _transcribe)

        def _run() -> None:
            ipc_server._run_local_media_job(
                self._job(None), tmp_path / "clip.wav", {"export_path": None, "export_format": None}
            )

        threads = [threading.Thread(target=_run, daemon=True) for _ in range(4)]
        for thread in threads:
            thread.start()
        for _ in range(4):
            assert started.acquire(timeout=5)
        assert gate.active() == 4

        # The switch reads leases and must block until every job released.
        switch_done = threading.Event()

        def _switch() -> None:
            harness = object.__new__(ChangeMixin)
            # Attribute map, not `harness._app = ...`: the mixin annotates
            # `_app` as the real app, and this test only needs `.tray`.
            harness.__dict__["_app"] = types.SimpleNamespace(tray=types.SimpleNamespace(notify=lambda *a: None))
            assert harness._defer_switch_to_running_media_jobs() is True
            switch_done.set()

        switcher = threading.Thread(target=_switch, daemon=True)
        switcher.start()
        time.sleep(0.2)
        assert not switch_done.is_set(), "the switch unloaded the engine under 4 live jobs"
        # Meanwhile config flips to the new model (the switch wrote it before
        # waiting, which is exactly why finish-time reads are wrong).
        ipc_server.app.config.model_size = "large-v3"

        release.set()
        for thread in threads:
            thread.join(5)
        assert switch_done.wait(5)

        assert len(labels) == 4
        assert set(labels) == {"whisper/small.en"}, f"rows mislabelled after the switch: {labels!r}"
        assert gate.active() == 0


class TestLeaseCoversTheModelLoad:
    """A switch during the LOAD is deferred like one during a decode."""

    @staticmethod
    def _job():
        import threading
        from types import SimpleNamespace

        return SimpleNamespace(
            job_id="load1",
            cancel_event=threading.Event(),
            progress=0.0,
            client_id=None,
            ingest_tier=None,
            expected_seconds=None,
            decoded_seconds=None,
            note=None,
            engine_label=None,
            quality=None,
            cancel_reason=None,
        )

    @staticmethod
    def _gate(monkeypatch):
        import voice_typer.server.media_ingest.lease as lease_mod

        gate = lease_mod.ModelLeaseGate()
        monkeypatch.setattr(lease_mod, "get_lease_gate", lambda: gate)
        return gate

    def test_switch_waits_for_the_load_and_the_job_keeps_its_engine(
        self, ipc_server, fake_service, monkeypatch, tmp_path
    ):
        import threading
        import time
        import types

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage_mod
        from voice_typer.server.model_manager._change import ChangeMixin

        gate = self._gate(monkeypatch)
        entered = threading.Event()
        release = threading.Event()
        label = "whisper/small.en"

        def _load():
            entered.set()
            assert release.wait(5)
            return types.SimpleNamespace(is_loaded=True), label

        monkeypatch.setattr(ipc_server, "_ensure_media_backend", _load)
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: 10.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: iter(()))
        decoded: list[int] = []

        def _transcribe(chunks, backend, **kw):
            decoded.append(1)
            return loop.WindowsState(texts=["ok"], decoded_seconds=10.0)

        monkeypatch.setattr(loop, "transcribe_windows", _transcribe)
        labels: list[str] = []
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, model="", **k: labels.append(model) or 1)

        result: dict = {}
        worker = threading.Thread(
            target=lambda: result.update(
                ipc_server._run_local_media_job(
                    self._job(), tmp_path / "clip.wav", {"export_path": None, "export_format": None}
                )
            ),
            daemon=True,
        )
        worker.start()
        assert entered.wait(5)
        # The load itself is leased, so the switch has something to wait on.
        assert gate.engines() == {"pending"}

        switch_done = threading.Event()

        def _switch() -> None:
            harness = object.__new__(ChangeMixin)
            # Attribute map, not `harness._app = ...`: the mixin annotates
            # `_app` as the real app, and this test only needs `.tray`.
            harness.__dict__["_app"] = types.SimpleNamespace(tray=types.SimpleNamespace(notify=lambda *a: None))
            assert harness._defer_switch_to_running_media_jobs() is True
            switch_done.set()

        switcher = threading.Thread(target=_switch, daemon=True)
        switcher.start()
        time.sleep(0.15)
        assert not switch_done.is_set(), "the switch ran while the job was still loading its engine"

        release.set()
        worker.join(5)
        assert switch_done.wait(5)
        assert result.get("chars") == 2
        assert decoded == [1]
        assert labels == [label]
        assert gate.active() == 0

    def test_cancel_during_the_load_never_starts_a_decode(self, ipc_server, fake_service, monkeypatch, tmp_path):
        """The timeout path cancels a PREPARING job: nothing is decoded."""
        import types

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage_mod
        from voice_typer.server.media_ingest.errors import MODEL_CHANGED

        gate = self._gate(monkeypatch)
        job = self._job()

        def _load():
            job.cancel_reason = MODEL_CHANGED
            job.cancel_event.set()
            return types.SimpleNamespace(is_loaded=True), "whisper/small.en"

        monkeypatch.setattr(ipc_server, "_ensure_media_backend", _load)
        decoded: list[int] = []
        persisted: list[int] = []
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: decoded.append(1) or 10.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: decoded.append(1) or iter(()))
        monkeypatch.setattr(
            loop, "transcribe_windows", lambda *a, **k: decoded.append(1) or loop.WindowsState(texts=["x"])
        )
        monkeypatch.setattr(storage_mod, "persist_result", lambda *a, **k: persisted.append(1) or 1)

        out = ipc_server._run_local_media_job(job, tmp_path / "clip.wav", {"export_path": None, "export_format": None})
        assert out == {"row_id": None, "chars": 0}
        assert decoded == [], "a job cancelled during the load started decoding anyway"
        assert persisted == []
        assert gate.active() == 0

    def test_cancel_during_the_url_load_never_downloads(self, ipc_server, fake_service, monkeypatch, tmp_path):
        import types

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.downloader as dl
        import voice_typer.server.media_ingest.url_resolver as resolver
        from voice_typer.server.media_ingest.errors import MODEL_CHANGED

        gate = self._gate(monkeypatch)
        job = self._job()
        monkeypatch.setattr(
            resolver,
            "resolve_media_url",
            lambda url, **kw: types.SimpleNamespace(
                audio_url="https://cdn.example/a.m4a",
                webpage_url="https://example.com/v",
                duration=42.0,
                subtitles_available=False,
                is_live=False,
            ),
        )

        def _load():
            job.cancel_reason = MODEL_CHANGED
            job.cancel_event.set()
            return types.SimpleNamespace(is_loaded=True), "whisper/small.en"

        monkeypatch.setattr(ipc_server, "_ensure_media_backend", _load)
        downloaded: list[int] = []
        monkeypatch.setattr(dl, "temp_audio_download", lambda *a, **k: downloaded.append(1))
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: downloaded.append(1) or iter(()))

        out = ipc_server._run_url_media_job(job, "https://example.com/v", None, {"use_subtitles": False})
        assert out == {"row_id": None, "chars": 0}
        assert downloaded == [], "a cancelled URL job still downloaded or decoded"
        assert gate.active() == 0
