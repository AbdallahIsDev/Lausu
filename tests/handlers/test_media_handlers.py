"""Unit tests for ``MediaHandlersMixin`` (ADR-0023 Phase 1)."""

from __future__ import annotations


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
            def start(self, source, runner):
                started["source"] = source

                class _J:
                    job_id = "abc123"
                    status = "running"

                return _J()

        monkeypatch.setattr(jobs_mod, "get_job_manager", lambda: _Mgr())
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        resp = ipc_server._handle_media_transcribe_start({"source": str(f)}, {})
        assert resp["type"] == "media_transcribe_result"
        assert resp["data"]["job_id"] == "abc123"
        assert started["source"] == str(f)


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
    def test_url_is_handed_to_the_job_without_resolving_inline(
        self, ipc_server, fake_service, monkeypatch
    ):
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
            def start(self, source, runner):
                started["source"] = source

                class _J:
                    job_id = "url123"
                    status = "running"

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


class TestMediaUrlJobTiers:
    """Download-first tiering: the local audio copy is primary, the stream is
    the fallback (namespace doubles: the job body only reads those fields)."""

    @staticmethod
    def _job():
        import threading
        from types import SimpleNamespace

        return SimpleNamespace(job_id="tier1", cancel_event=threading.Event(), progress=0.0)

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

    def _patch_pipeline(self, monkeypatch, tmp_path, *, download_error=None):
        import contextlib

        import voice_typer.server.media_ingest.decoder as dec
        import voice_typer.server.media_ingest.downloader as dl
        import voice_typer.server.media_ingest.engine_loop as loop
        import voice_typer.server.media_ingest.storage as storage
        import voice_typer.server.media_ingest.url_resolver as resolver

        monkeypatch.setattr(
            resolver, "resolve_media_url", lambda url, **kw: self._resolved()
        )

        calls = []
        audio = tmp_path / "a.m4a"
        audio.write_bytes(b"x")

        @contextlib.contextmanager
        def _download(url, **kwargs):
            calls.append(("download", url))
            if download_error is not None:
                raise download_error
            yield audio

        monkeypatch.setattr(dl, "temp_audio_download", _download)
        monkeypatch.setattr(dec, "decode_chunks", lambda src, **kw: calls.append(("decode", src)) or iter(()))
        monkeypatch.setattr(
            loop,
            "transcribe_windows",
            lambda chunks, backend, **kw: calls.append(("transcribe",)) or loop.WindowsState(texts=["ok"]),
        )
        monkeypatch.setattr(storage, "persist_result", lambda *a, **k: 1)
        return calls

    def test_download_tier_runs_before_any_stream(self, ipc_server, fake_service, monkeypatch, tmp_path):
        calls = self._patch_pipeline(monkeypatch, tmp_path)
        out = ipc_server._run_url_media_job(
            self._job(), "https://example.com/v", None, {"use_subtitles": False}
        )
        assert [c[0] for c in calls] == ["download", "decode", "transcribe"]
        assert out == {"row_id": 1, "chars": 2}

    def test_stream_fallback_when_download_fails(self, ipc_server, fake_service, monkeypatch, tmp_path):
        import voice_typer.server.media_ingest.decoder as dec
        from voice_typer.server.media_ingest.errors import DOWNLOAD_FAILED, MediaIngestError

        calls = self._patch_pipeline(
            monkeypatch,
            tmp_path,
            download_error=MediaIngestError(DOWNLOAD_FAILED, "nope"),
        )
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: calls.append(("stream-decode",)) or iter(()))
        out = ipc_server._run_url_media_job(
            self._job(), "https://example.com/v", None, {"use_subtitles": False}
        )
        assert [c[0] for c in calls] == ["download", "stream-decode", "transcribe"]
        assert out == {"row_id": 1, "chars": 2}

    def test_local_job_probes_total_so_progress_and_eta_work(
        self, ipc_server, fake_service, monkeypatch, tmp_path
    ):
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
            lambda job, frac, phase, eta=None, duration=None: progress.append(
                (frac, phase, eta, duration)
            ),
        )
        monkeypatch.setattr(dec, "probe_duration_seconds", lambda *a, **k: 480.0)
        monkeypatch.setattr(dec, "decode_chunks", lambda *a, **k: iter(()))
        seen_kwargs = {}

        def _transcribe_windows(chunks, backend, **kw):
            seen_kwargs.update(kw)
            return loop.WindowsState(texts=["ok"])

        monkeypatch.setattr(loop, "transcribe_windows", _transcribe_windows)
        monkeypatch.setattr(storage, "persist_result", lambda *a, **k: 1)

        out = ipc_server._run_local_media_job(
            SimpleNamespace(job_id="local1", cancel_event=threading.Event(), progress=0.0),
            r"C:\tmp\clip.mp3",
            {"export_path": None, "export_format": None},
        )

        assert progress[0][1] == "loading_model"
        assert seen_kwargs["total_seconds"] == 480.0
        # Mid-job progress carries the probed total as the Duration readout.
        seen_kwargs["on_progress"](0.5, 12.0)
        assert progress[-1] == (0.5, "transcribing", 12.0, 480.0)
        assert out == {"row_id": 1, "chars": 2}
