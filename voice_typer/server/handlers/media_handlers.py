"""Media-transcribe IPC handlers: start / cancel / status (ADR-0023)."""

import threading

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log
from voice_typer.server.ipc.validation import (
    ErrorCodes,
    ResponseEnvelope,
    _error_response,
    _validate_dict_payload,
)

# ADR-0023 E9 tier-0 budget: first stream open plus retry room for one
# re-resolve (URL_EXPIRED) / seek-resume (STREAM_STALLED) before the
# temp-download fallback tier.
MAX_STREAM_ATTEMPTS = 3

# Concurrent media jobs all want the same lazily-loaded model. Two jobs
# starting together would otherwise both miss `active_transcriber()` and
# each trigger a full weight load; one lock makes the second wait for the
# first instead. Inference itself is serialized separately, by the ASR lane
# in `media_ingest.jobs`.
_MODEL_LOAD_LOCK = threading.Lock()


class MediaHandlersMixin(HandlerBase):
    """Mixin: local-file and URL media transcription jobs (ADR-0023)."""

    def _handle_media_transcribe_start(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        def body(d: dict) -> dict:
            validated, error = _validate_dict_payload(
                d,
                {
                    "source": {"type": str, "required": True, "max_value_len": 4096},
                    "export_path": {"type": (str, type(None)), "required": False, "default": None},
                    "export_format": {"type": (str, type(None)), "required": False, "default": None},
                    # ADR-0023 E13: subtitle fast-path is OPT-IN (default off).
                    "use_subtitles": {"type": bool, "required": False, "default": True},
                    # Renderer correlation token, echoed on every event for
                    # this job so a push that beats the start ack still lands
                    # on the exact row that requested it (no guessing).
                    "client_id": {"type": (str, type(None)), "required": False, "default": None, "max_value_len": 64},
                },
            )
            if error:
                return error
            assert validated is not None
            from voice_typer.server.media_ingest.errors import JOB_BUSY, MediaIngestError
            from voice_typer.server.media_ingest.jobs import MediaJob, get_job_manager
            from voice_typer.server.media_ingest.sources import classify_source

            raw = str(validated["source"]).strip()
            client_id = validated.get("client_id")
            if not isinstance(client_id, str) or not client_id.strip():
                client_id = None
            export_path = validated.get("export_path")
            export_path = export_path.strip() if isinstance(export_path, str) and export_path.strip() else None
            # Two concurrent jobs writing the same file would clobber each
            # other, and which text survives would be arbitrary. Refuse the
            # second start with the standard field-validation envelope.
            if export_path is not None and get_job_manager().export_path_in_use(export_path):
                return {
                    "type": "error",
                    "data": {
                        "code": ErrorCodes.INVALID_FIELD,
                        "field": "export_path",
                        "message": f"'export_path' is already the target of a running job: {export_path}",
                    },
                }
            try:
                classified = classify_source(raw)
            except ValueError:
                return _error_response(resp, "missing source", code=ErrorCodes.MISSING_FIELD)
            if classified.kind == "url":
                return self._start_url_media_job(
                    classified.raw, validated, resp, client_id, export_path
                )
            if not self._media_model_selected():
                return _error_response(
                    resp, "no speech model installed (open Models to choose one)", code=ErrorCodes.NO_MODEL
                )
            manager = get_job_manager()

            def _runner(job: MediaJob) -> dict:
                return self._run_local_media_job(job, classified.raw, validated)

            try:
                job = manager.start(
                    classified.raw, _runner, client_id=client_id, export_path=export_path
                )
            except MediaIngestError as exc:
                if exc.code == JOB_BUSY:
                    return _error_response(resp, str(exc), code=ErrorCodes.JOB_BUSY)
                raise
            return {
                "type": "media_transcribe_result",
                "data": {"job_id": job.job_id, "client_id": job.client_id, "status": "running"},
            }

        return self._wrap(
            cmd_name="media_transcribe_start", resp_type="media_transcribe_result", data=data, resp=resp, body=body
        )

    def _start_url_media_job(
        self,
        url: str,
        validated: dict,
        resp: ResponseEnvelope,
        client_id: str | None = None,
        export_path: str | None = None,
    ) -> dict:
        """Consent-gate, then hand the resolve+download to a job thread.

        Resolution used to run inline, which made a batch of pasted links
        start one-at-a-time (each ``resolve_media_url`` is a network round
        trip). It now happens inside the job, so N links enqueue in N fast
        acks and the slow part overlaps.
        """
        from voice_typer.server.asr_errors import ConsentRequiredError
        from voice_typer.server.media_ingest import runtime as _runtime
        from voice_typer.server.media_ingest.errors import JOB_BUSY, MediaIngestError
        from voice_typer.server.media_ingest.jobs import MediaJob, get_job_manager

        if not getattr(self.app.config, "media_url_consent", False):
            raise ConsentRequiredError(
                "media URL consent required to transcribe a link",
                engine_name="media_ingest",
                consent_field="media_url_consent",
            )
        if not self._media_model_selected():
            return _error_response(
                resp, "no speech model installed (open Models to choose one)", code=ErrorCodes.NO_MODEL
            )
        manager = get_job_manager()
        # Cheap filesystem probe, no network: fail fast on the one site that
        # cannot be resolved without a JavaScript runtime instead of creating
        # a job that is guaranteed to die.
        runtime = _runtime.find_js_runtime()
        if runtime is None and "youtube" in url.lower():
            return _error_response(
                resp,
                "YouTube needs a JavaScript runtime; install Deno",
                code=ErrorCodes.NOT_SUPPORTED,
            )

        def _runner(job: MediaJob) -> dict:
            return self._run_url_media_job(job, url, runtime, validated)

        try:
            job = manager.start(url, _runner, client_id=client_id, export_path=export_path)
        except MediaIngestError as exc:
            if exc.code == JOB_BUSY:
                return _error_response(resp, str(exc), code=ErrorCodes.JOB_BUSY)
            raise
        return {
            "type": "media_transcribe_result",
            "data": {"job_id": job.job_id, "client_id": job.client_id, "status": "running"},
        }

    def _resolve_media(self, url: str, runtime):
        """Re-resolve a URL to a fresh signed audio URL after expiry."""
        from voice_typer.server.media_ingest import runtime as _runtime, url_resolver as _resolver

        return _resolver.resolve_media_url(
            url,
            js_runtimes=_runtime.js_runtime_options(runtime),
        )

    def _finish_media_job(
        self, job, text: str, *, duration: float | None = None, partial: bool = False, validated: dict
    ) -> dict:
        """Persist + export the final transcript and publish completion.

        Empty output (silent audio, or a cancel before the first window
        flushed) skips History so no junk row is created; the completion
        event then carries ``row_id: null`` so the renderer still leaves
        the running state.
        """
        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest import storage as _storage

        stripped = text.strip()
        row_id: int | None = None
        if stripped:
            row_id = _storage.persist_result(
                self.app,
                stripped,
                duration=duration if duration is not None else 0.0,
                model=str(getattr(self.app.config, "model_size", "") or ""),
                device=str(getattr(self.app.config, "device", "") or ""),
                partial=partial,
            )
            export_path = validated.get("export_path")
            if isinstance(export_path, str) and export_path:
                _storage.export_text(stripped, export_path, fmt=str(validated.get("export_format") or "txt"))
        try:
            event_bus.publish(
                {
                    "type": "media_transcribe_complete",
                    "data": {
                        "job_id": job.job_id,
                        "client_id": job.client_id,
                        "row_id": row_id,
                        "chars": len(stripped),
                        "partial": partial,
                    },
                }
            )
        except Exception:  # noqa: BLE001, best-effort
            log.debug("[MEDIA] complete publish failed", exc_info=True)
        return {"row_id": row_id, "chars": len(stripped)}

    @staticmethod
    def _asr_manager():
        """The process-wide job manager, owner of the single ASR lane."""
        from voice_typer.server.media_ingest.jobs import get_job_manager

        return get_job_manager()

    def _run_local_media_job(self, job, path: str, validated: dict) -> dict:
        """Background body: lazy-load model, decode, window-transcribe, persist."""
        from voice_typer.server.media_ingest import decoder as _decoder, engine_loop as _loop

        self._publish_media_progress(job, 0.0, "loading_model")
        backend = self._ensure_media_backend()
        # A local job has no resolver-provided total: read it off the container
        # header so the bar reports a fraction/ETA instead of jumping 0 -> 1.
        total = _decoder.probe_duration_seconds(path)
        chunks = _decoder.decode_chunks(path)
        manager = self._asr_manager()
        state = _loop.transcribe_windows(
            chunks,
            backend,
            cancel_event=job.cancel_event,
            on_progress=lambda frac, eta: self._publish_media_progress(job, frac, "transcribing", eta, total),
            total_seconds=total,
            lane=manager.asr_lane,
        )
        return self._finish_media_job(
            job,
            state.text,
            duration=state.decoded_seconds,
            partial=job.cancel_event.is_set(),
            validated=validated,
        )

    def _run_url_media_job(self, job, url: str, runtime, validated: dict) -> dict:
        """URL job body: resolve, subtitles fast path, download, stream fallback (ADR-0023 E9/E10/E12/E15)."""
        from voice_typer.server.media_ingest import (
            decoder as _decoder,
            downloader as _downloader,
            engine_loop as _loop,
            runtime as _runtime,
            subtitles as _subtitles,
            url_resolver as _resolver,
        )
        from voice_typer.server.media_ingest.errors import (
            DRM_REFUSED,
            UNSUPPORTED_LIVE,
            URL_EXPIRED,
            MediaIngestError,
        )

        resolved = _resolver.resolve_media_url(url, js_runtimes=_runtime.js_runtime_options(runtime))
        if resolved.is_live:
            raise MediaIngestError(UNSUPPORTED_LIVE, "live streams are not supported")

        # E12/E13: official-subtitles fast path is OPT-IN (author-provided
        # captions; the UI states the accuracy tradeoff).
        if resolved.subtitles_available and bool(validated.get("use_subtitles")):
            lang = str(getattr(self.app.config, "language", "") or "").strip() or "en"
            try:
                text = _subtitles.fetch_subtitles(resolved.webpage_url, lang=lang)
            except Exception:  # noqa: BLE001, fast path degrades to audio
                log.debug("[MEDIA] subtitle fetch failed, falling back to audio", exc_info=True)
                text = None
            if text:
                return self._finish_media_job(job, text, validated=validated)

        # E15: the model lazy-loads only once audio work is unavoidable.
        self._publish_media_progress(job, 0.0, "loading_model")
        backend = self._ensure_media_backend()

        manager = self._asr_manager()
        state = _loop.WindowsState()
        # Primary tier: download the audio-only stream once, then decode from
        # disk. Streaming the signed CDN URL spent ~15 s of ingest per 30 s of
        # audio at ~0.5x realtime while ASR cost <1 s, so the local copy is the
        # fast path and the stream is the fallback (2026-10-27 measurement).
        self._publish_media_progress(job, 0.0, "downloading", None, resolved.duration)
        try:
            with _downloader.temp_audio_download(
                resolved.webpage_url,
                js_runtimes=_runtime.js_runtime_options(runtime),
                on_progress=lambda frac: self._publish_media_progress(
                    job, frac, "downloading", None, resolved.duration
                ),
            ) as tmp_path:
                chunks = _decoder.decode_chunks(str(tmp_path))
                state = _loop.transcribe_windows(
                    chunks,
                    backend,
                    cancel_event=job.cancel_event,
                    on_progress=lambda frac, eta: self._publish_media_progress(
                        job, frac, "transcribing", eta, resolved.duration
                    ),
                    total_seconds=resolved.duration,
                    state=state,
                    lane=manager.asr_lane,
                )
            return self._finish_media_job(
                job,
                state.text,
                duration=resolved.duration,
                partial=job.cancel_event.is_set(),
                validated=validated,
            )
        except MediaIngestError as exc:
            if job.cancel_event.is_set():
                return self._finish_media_job(
                    job, state.text, duration=resolved.duration, partial=True, validated=validated
                )
            if exc.code == DRM_REFUSED:
                raise
            log.warning("[MEDIA] audio download failed (%s), falling back to the direct stream", exc.code)

        # Fallback tier: stream the resolved signed URL (resume-aware retries).
        last_error: MediaIngestError | None = None
        for attempt in range(MAX_STREAM_ATTEMPTS):
            if job.cancel_event.is_set():
                break
            try:
                chunks = _decoder.decode_chunks(
                    resolved.audio_url,
                    remote=True,
                    start_seconds=state.decoded_seconds,
                )
                # Bound per attempt: a re-resolve refreshes `resolved`.
                stream_duration = resolved.duration

                def _on_stream_progress(
                    frac: float, eta: float | None, _d: float | None = stream_duration
                ) -> None:
                    self._publish_media_progress(job, frac, "transcribing", eta, _d)

                state = _loop.transcribe_windows(
                    chunks,
                    backend,
                    cancel_event=job.cancel_event,
                    on_progress=_on_stream_progress,
                    total_seconds=resolved.duration,
                    state=state,
                    lane=manager.asr_lane,
                )
                return self._finish_media_job(
                    job,
                    state.text,
                    duration=resolved.duration,
                    partial=job.cancel_event.is_set(),
                    validated=validated,
                )
            except MediaIngestError as exc:
                if job.cancel_event.is_set():
                    break
                if exc.code == DRM_REFUSED:
                    raise
                last_error = exc
                log.warning("[MEDIA] stream attempt %d/%d failed (%s)", attempt + 1, MAX_STREAM_ATTEMPTS, exc.code)
                if exc.code == URL_EXPIRED and attempt + 1 < MAX_STREAM_ATTEMPTS:
                    try:
                        resolved = self._resolve_media(resolved.webpage_url, runtime)
                    except MediaIngestError as resolve_exc:
                        last_error = resolve_exc
                        break
                continue
        if job.cancel_event.is_set():
            return self._finish_media_job(
                job, state.text, duration=resolved.duration, partial=True, validated=validated
            )
        # The download tier already ran (and failed) before streaming, so this
        # is terminal: no second download attempt.
        assert last_error is not None
        raise last_error

    def _publish_media_progress(
        self,
        job,
        fraction: float,
        phase: str,
        eta_seconds: float | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        """Best-effort progress event carrying the phase + ETA (ADR-0023 E16)."""
        from voice_typer.server import event_bus

        job.progress = fraction
        job.phase = phase
        try:
            event_bus.publish(
                {
                    "type": "media_transcribe_progress",
                    "data": {
                        "job_id": job.job_id,
                        "client_id": job.client_id,
                        "progress": fraction,
                        "phase": phase,
                        "eta_seconds": eta_seconds,
                        "duration_seconds": duration_seconds,
                    },
                }
            )
        except Exception:  # noqa: BLE001, best-effort
            log.debug("[MEDIA] progress publish failed", exc_info=True)

    def _handle_media_transcribe_cancel(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Cancel one job by id, or every running job when no id is given."""
        try:
            from voice_typer.server.media_ingest.jobs import get_job_manager

            job_id: str | None = None
            if isinstance(data, dict):
                raw = data.get("job_id")
                if isinstance(raw, str) and raw.strip():
                    job_id = raw.strip()
            cancelled = get_job_manager().cancel(job_id)
            resp["type"] = "media_transcribe_result"
            resp["data"] = {"cancelled": len(cancelled), "job_ids": cancelled}
        except Exception as exc:
            self._respond_with_error(resp, exc, "media_transcribe_cancel")
        return resp

    def _handle_media_transcribe_status(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Running jobs + the concurrency cap, so the UI never hardcodes it."""
        try:
            from voice_typer.server.media_ingest.jobs import get_job_manager

            manager = get_job_manager()
            resp["type"] = "media_transcribe_result"
            resp["data"] = {"jobs": manager.snapshots(), "max_jobs": manager.max_jobs}
        except Exception as exc:
            self._respond_with_error(resp, exc, "media_transcribe_status")
        return resp

    def _media_model_selected(self) -> bool:
        """True when a speech model is selected (it may still need a lazy load)."""
        models = getattr(self.app, "models", None)
        if models is None:
            return False
        try:
            if models.active_transcriber() is not None:
                return True
        except Exception:  # noqa: BLE001, probe falls through to config
            log.debug("[MEDIA] active_transcriber probe failed", exc_info=True)
        return bool(str(getattr(self.app.config, "model_size", "") or "").strip())

    def _ensure_media_backend(self):
        """E15: lazy-load the active ASR engine inside the job thread."""
        from voice_typer.server.asr_errors import (
            ModelIntegrityError,
            ModelNotDownloadedError,
        )
        from voice_typer.server.media_ingest.errors import NO_ENGINE, MediaIngestError

        models = getattr(self.app, "models", None)
        if models is None:
            raise MediaIngestError(NO_ENGINE, "no speech model is loaded (open Models to choose one)")
        with _MODEL_LOAD_LOCK:
            # The lock only serializes the call: `ensure_active_engine_loaded`
            # stays the single authority on whether a load is needed (it also
            # handles a model switch), so behaviour is unchanged for one job.
            ensure = getattr(models, "ensure_active_engine_loaded", None)
            if callable(ensure):
                try:
                    ensure()
                except (ModelNotDownloadedError, ModelIntegrityError) as exc:
                    # Pack/model missing is a user-actionable state, not a crash.
                    raise MediaIngestError(NO_ENGINE, str(exc)) from exc
                except Exception:  # noqa: BLE001, verified by the is_loaded re-check
                    log.debug("[MEDIA] lazy model load raised", exc_info=True)
            engine = models.active_transcriber()
        if engine is None or not getattr(engine, "is_loaded", False):
            raise MediaIngestError(NO_ENGINE, "no speech model is loaded (open Models to choose one)")
        return engine
