"""Media-transcribe IPC handlers: start / cancel / status (ADR-0023)."""

import threading

from voice_typer.server.handlers._log import log
from voice_typer.server.handlers.media_job_runners import MediaJobRunnersMixin
from voice_typer.server.ipc.validation import (
    ErrorCodes,
    ResponseEnvelope,
    _error_response,
    _validate_dict_payload,
)

# Concurrent media jobs all want the same lazily-loaded model. Two jobs
# starting together would otherwise both miss `active_transcriber()` and
# each trigger a full weight load; one lock makes the second wait for the
# first instead. Inference itself is serialized separately, by the ASR lane
# in `media_ingest.jobs`.
_MODEL_LOAD_LOCK = threading.Lock()


class MediaHandlersMixin(MediaJobRunnersMixin):
    """Mixin: local-file and URL media transcription jobs (ADR-0023)."""

    def _handle_media_transcribe_start(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        def body(d: dict) -> dict:
            validated, error = _validate_dict_payload(
                d,
                {
                    "source": {"type": str, "required": True, "max_value_len": 4096},
                    "export_path": {"type": (str, type(None)), "required": False, "default": None},
                    "export_format": {"type": (str, type(None)), "required": False, "default": None},
                    # ADR-0023 E13: the renderer's toggle is the opt-in (it always sends it).
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
                return self._start_url_media_job(classified.raw, validated, resp, client_id, export_path)
            refusal = self._media_start_refusal()
            if refusal is not None:
                return _error_response(resp, str(refusal["message"]), code=str(refusal["code"]))
            manager = get_job_manager()

            def _runner(job: MediaJob) -> dict:
                return self._run_local_media_job(job, classified.raw, validated)

            try:
                job = manager.start(classified.raw, _runner, client_id=client_id, export_path=export_path)
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
        refusal = self._media_start_refusal()
        if refusal is not None:
            return _error_response(resp, str(refusal["message"]), code=str(refusal["code"]))
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

    def _media_model_state(self) -> tuple[str, str]:
        """Classify which of the four start states the model layer is in.

        ``ready``    - an engine is loaded and usable;
        ``loadable`` - a model is selected and installed, a load will happen;
        ``none``     - nothing is selected (Open Models);
        ``failed``   - selected but not usable/installed (retry / Open Models).

        A bare ``config.model_size`` string is NOT proof on its own: the
        previous gate accepted it, so a stale config started jobs that could
        only fail.
        """
        from voice_typer.server.model_registry import NO_MODEL_SIZE

        models = getattr(self.app, "models", None)
        if models is None:
            return "none", "no speech model is selected"
        try:
            engine = models.active_transcriber()
        except Exception:  # noqa: BLE001, probe falls through to config
            log.debug("[MEDIA] active_transcriber probe failed", exc_info=True)
            engine = None
        if engine is not None and bool(getattr(engine, "is_loaded", False)):
            return "ready", ""
        size = str(getattr(self.app.config, "model_size", "") or "").strip()
        if not size or size == NO_MODEL_SIZE:
            return "none", "no speech model is selected"
        installed = getattr(models, "_model_downloaded_precheck", None)
        if callable(installed):
            try:
                if not installed():
                    return "failed", f"the {size} model is not installed"
            except Exception:  # noqa: BLE001, "unknown" accepts the start
                log.debug("[MEDIA] installed-model probe failed", exc_info=True)
        return "loadable", ""

    def _media_start_refusal(self) -> dict | None:
        """Error envelope for a start the model layer cannot honour."""
        from voice_typer.server.media_ingest.errors import NO_ENGINE

        state, reason = self._media_model_state()
        if state == "none":
            return {
                "code": ErrorCodes.NO_MODEL,
                "message": "no speech model installed (open Models to choose one)",
            }
        if state == "failed":
            return {"code": NO_ENGINE, "message": reason}
        return None

    def _ensure_media_backend(self):
        """E15/lease: resolve + load the engine for this job, never a dictation."""
        from voice_typer.server.asr_errors import ModelIntegrityError, ModelNotDownloadedError
        from voice_typer.server.media_ingest.errors import MODEL_LOADING, NO_ENGINE, MediaIngestError
        from voice_typer.server.model_manager._loading import engine_label

        models = getattr(self.app, "models", None)
        if models is None:
            raise MediaIngestError(NO_ENGINE, "no speech model is loaded (open Models to choose one)")
        loader = getattr(models, "ensure_engine_loaded_for_media", None)
        with _MODEL_LOAD_LOCK:
            result = loader() if callable(loader) else None
            # A double/older manager may answer with something mock-shaped;
            # only a real `state: str` result is trusted, everything else uses
            # the historical load path below.
            state = getattr(result, "state", None) if result is not None else None
            if isinstance(state, str):
                reason = str(getattr(result, "reason", "") or "")
                engine = getattr(result, "engine", None)
                label = str(getattr(result, "label", "") or "")
            else:
                # Doubles/older managers: the historical load path, still
                # without queueing a pending dictation.
                ensure = getattr(models, "ensure_active_engine_loaded", None)
                if callable(ensure):
                    try:
                        ensure(queue_pending_dictation=False)
                    except TypeError:
                        ensure()
                    except (ModelNotDownloadedError, ModelIntegrityError) as exc:
                        raise MediaIngestError(NO_ENGINE, str(exc)) from exc
                    except Exception:  # noqa: BLE001, verified by the is_loaded re-check
                        log.debug("[MEDIA] lazy model load raised", exc_info=True)
                engine = models.active_transcriber()
                state = "ready" if engine is not None and getattr(engine, "is_loaded", False) else "failed"
                reason = "no speech model is loaded"
                label = ""
        if state == "ready" and engine is not None and getattr(engine, "is_loaded", False):
            if not label:
                backend = ""
                namer = getattr(models, "active_backend_name", None)
                if callable(namer):
                    try:
                        backend = str(namer() or "")
                    except Exception:  # noqa: BLE001, label falls back to empty backend
                        backend = ""
                label = engine_label(backend, engine)
            return engine, label
        if state == "no_model":
            raise MediaIngestError(ErrorCodes.NO_MODEL, reason or "no speech model is selected")
        if state == "loading":
            raise MediaIngestError(MODEL_LOADING, reason or "the speech model is still loading")
        raise MediaIngestError(NO_ENGINE, reason or "no speech model is loaded")
