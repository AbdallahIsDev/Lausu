"""Media job runners: ingest -> validate -> persist (ADR-0023).

The IPC surface (start / cancel / status) lives in ``media_handlers.py``;
everything a job does between ``start`` and its completion event lives here:
the ingest tiers, progress publishing, the ingest validation gate and the
History write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log

# ADR-0023 E9 tier-0 budget: first stream open plus retry room for one
# re-resolve (URL_EXPIRED) / seek-resume (STREAM_STALLED) before the
# temp-download fallback tier.
MAX_STREAM_ATTEMPTS = 3

#: History's model column for the official-subtitles tier: no engine ran, and
#: an empty string reads as a missing transcript instead of a caption source.
SUBTITLES_ENGINE_LABEL = "subtitles"


def _format_optional(value: object) -> str:
    """Format a numeric quality reading for the outcome log, else ``n/a``."""
    import math
    import numbers

    if isinstance(value, numbers.Real) and math.isfinite(float(value)):
        return f"{float(value):.2f}"
    return "n/a"


class MediaJobRunnersMixin(HandlerBase):
    """Mixin: one media job's ingest -> validate -> persist life (ADR-0023)."""

    if TYPE_CHECKING:
        # Provided by MediaHandlersMixin (the composed IPC class) at runtime.
        def _ensure_media_backend(self) -> Any: ...

    def _resolve_media(self, url: str, runtime):
        """Re-resolve a URL to a fresh signed audio URL after expiry."""
        from voice_typer.server.media_ingest import runtime as _runtime, url_resolver as _resolver

        return _resolver.resolve_media_url(
            url,
            js_runtimes=_runtime.js_runtime_options(runtime),
        )

    def _finish_media_job(
        self,
        job,
        text: str,
        *,
        duration: float | None = None,
        decoded_seconds: float | None = None,
        expected_seconds: float | None = None,
        partial: bool = False,
        quality: dict[str, float] | None = None,
        silent: bool = False,
        validated: dict,
    ) -> dict:
        """Validate, persist + export the final transcript, publish completion.

        This is the SINGLE gate every media job passes before anything is
        written: a job whose ingest decoded nothing, decoded a truncated
        fraction, or decoded only silence can never produce a success row.
        Empty output (silent audio, or a cancel before the first window
        flushed) skips History so no junk row is created; the completion
        event then carries ``row_id: null`` so the renderer still leaves the
        running state.
        """
        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest import storage as _storage, validation as _validation
        from voice_typer.server.media_ingest.errors import MEDIA_TRUNCATED, MediaIngestError

        job.expected_seconds = expected_seconds if expected_seconds is not None else job.expected_seconds
        job.decoded_seconds = decoded_seconds if decoded_seconds is not None else job.decoded_seconds
        if decoded_seconds is not None and not partial:
            verdict = _validation.validate_decoded(decoded_seconds=decoded_seconds, expected_seconds=expected_seconds)
            if not verdict.ok:
                job.note = verdict.code
                raise MediaIngestError(verdict.code or MEDIA_TRUNCATED, verdict.message)

        stripped = "" if silent else text.strip()
        if silent:
            job.note = "no_speech"
        elif not stripped and not partial:
            # The engine's hallucination gate returned nothing (the whole
            # media was rejected as invented speech): the same "no speech"
            # outcome as silence, never a "characters were added" card.
            job.note = job.note or "no_speech"
        row_id: int | None = None
        if stripped:
            row_id = _storage.persist_result(
                self.app,
                stripped,
                duration=duration if duration is not None else 0.0,
                # The engine this job actually ran on (leased at start), never
                # ``config.model_size`` read now: a switch may have written the
                # new model into config while this job was still decoding.
                model=job.engine_label or "",
                device=str(getattr(self.app.config, "device", "") or ""),
                partial=partial,
            )
            export_path = validated.get("export_path")
            if isinstance(export_path, str) and export_path:
                _storage.export_text(stripped, export_path, fmt=str(validated.get("export_format") or "txt"))
        if quality is not None:
            job.quality = quality
        status = "partial" if partial else ("no_speech" if not stripped else "completed")
        self._log_media_outcome(job, status=status, chars=len(stripped))
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
                        "tier": job.ingest_tier,
                        "quality": quality,
                        "note": job.note,
                    },
                }
            )
        except Exception:  # noqa: BLE001, best-effort
            log.debug("[MEDIA] complete publish failed", exc_info=True)
        return {"row_id": row_id, "chars": len(stripped)}

    @staticmethod
    def _log_media_outcome(job, *, status: str, chars: int) -> None:
        """One outcome line per job, with every support-relevant field."""
        quality = job.quality or {}
        decoded = job.decoded_seconds
        expected = job.expected_seconds
        log.info(
            "[MEDIA] outcome: job=%s status=%s tier=%s engine=%s chars=%d "
            "audio=%s/%s avg_logprob=%s no_speech_prob=%s note=%s",
            job.job_id,
            status,
            job.ingest_tier or "-",
            job.engine_label or "-",
            chars,
            f"{decoded:.1f}s" if decoded is not None else "n/a",
            f"{expected:.1f}s" if expected is not None else "n/a",
            _format_optional(quality.get("avg_logprob")),
            _format_optional(quality.get("no_speech_prob")),
            job.note or "-",
        )

    @staticmethod
    def _job_quality(state, chars: int) -> dict[str, float] | None:
        """Quality readings for the job (worst window), when available."""
        quality: dict[str, float] = {}
        if state.avg_logprob is not None:
            quality["avg_logprob"] = round(float(state.avg_logprob), 4)
        if state.no_speech_prob is not None:
            quality["no_speech_prob"] = round(float(state.no_speech_prob), 4)
        if state.decoded_seconds > 0:
            quality["chars_per_second"] = round(chars / state.decoded_seconds, 3)
        return quality or None

    @staticmethod
    def _asr_manager():
        """The process-wide job manager, owner of the single ASR lane."""
        from voice_typer.server.media_ingest.jobs import get_job_manager

        return get_job_manager()

    def _media_engine_ready(self) -> bool:
        """Ask the model layer whether a load must actually happen.

        The phase taxonomy must not claim ``loading_model`` for a job that
        starts on an already-loaded engine (it made every job look slow and
        sent the user hunting for a load that never happened).
        """
        models = getattr(self.app, "models", None)
        if models is None:
            return False
        try:
            engine = models.active_transcriber()
        except Exception:  # noqa: BLE001, treated as "needs a load"
            log.debug("[MEDIA] engine readiness probe failed", exc_info=True)
            return False
        return engine is not None and bool(getattr(engine, "is_loaded", False))

    def _publish_media_phase(self, job) -> None:
        """First phase: ``loading_model`` only when a load must happen."""
        phase = "preparing" if self._media_engine_ready() else "loading_model"
        self._publish_media_progress(job, 0.0, phase)

    def _transcribe_file(self, path, backend, manager, job, expected: float | None):
        """Decode + window-transcribe one local file (shared by both tiers)."""
        from voice_typer.server.media_ingest import decoder as _decoder, engine_loop as _loop

        chunks = _decoder.decode_chunks(str(path))
        return _loop.transcribe_windows(
            chunks,
            backend,
            cancel_event=job.cancel_event,
            on_progress=lambda frac, eta: self._publish_media_progress(job, frac, "transcribing", eta, expected),
            total_seconds=expected,
            lane=manager.asr_lane,
        )

    def _run_local_media_job(self, job, path: str, validated: dict) -> dict:
        """Background body: lease the engine, load it, decode, persist."""
        from voice_typer.server.media_ingest import decoder as _decoder, validation as _validation
        from voice_typer.server.media_ingest.lease import PENDING_ENGINE_LABEL, get_lease_gate

        lease = get_lease_gate()
        # Lease BEFORE the load: a switch that arrives while this job is still
        # loading would otherwise see an empty gate and unload the very model
        # the job is about to decode with.
        token = lease.begin(PENDING_ENGINE_LABEL)
        try:
            self._publish_media_phase(job)
            backend, label = self._ensure_media_backend()
            lease.relabel(token, label)
            job.engine_label = label
            if job.cancel_event.is_set():
                # Cancelled while the model loaded (a switch gave up waiting):
                # release the engine untouched instead of decoding on a model
                # that is about to be swapped out.
                return self._finish_media_job(job, "", partial=True, validated=validated)
            # A local job has no resolver-provided total: read it off the
            # container header so the bar reports a fraction/ETA instead of
            # jumping 0 -> 1.
            total = _decoder.probe_duration_seconds(path)
            job.expected_seconds = total
            manager = self._asr_manager()
            state = self._transcribe_file(path, backend, manager, job, total)
            cancelled = job.cancel_event.is_set()
            silent = _validation.is_total_silence(state.rms, state.silence_pct)
            return self._finish_media_job(
                job,
                state.text,
                duration=state.decoded_seconds,
                decoded_seconds=state.decoded_seconds,
                expected_seconds=total,
                partial=cancelled,
                quality=self._job_quality(state, len(state.text)),
                silent=silent and not cancelled,
                validated=validated,
            )
        finally:
            lease.end(token)

    def _run_url_media_job(self, job, url: str, runtime, validated: dict) -> dict:
        """URL job body: resolve, subtitles, download, guarded stream fallback."""
        from voice_typer.server.media_ingest import (
            engine_loop as _loop,
            runtime as _runtime,
            subtitles as _subtitles,
            url_resolver as _resolver,
        )
        from voice_typer.server.media_ingest.errors import UNSUPPORTED_LIVE, MediaIngestError
        from voice_typer.server.media_ingest.lease import PENDING_ENGINE_LABEL, get_lease_gate

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
                job.ingest_tier = "subtitles"
                # No engine ran: History names the source instead of an empty
                # model column (a blank model reads as a broken row).
                job.engine_label = SUBTITLES_ENGINE_LABEL
                job.expected_seconds = resolved.duration
                return self._finish_media_job(job, text, duration=resolved.duration, validated=validated)

        # E15: the model lazy-loads only once audio work is unavoidable. The
        # lease is taken BEFORE that load: a switch arriving mid-load would
        # otherwise see an empty gate and unload the model being loaded.
        self._publish_media_phase(job)
        lease = get_lease_gate()
        token = lease.begin(PENDING_ENGINE_LABEL)
        try:
            backend, label = self._ensure_media_backend()
            lease.relabel(token, label)
            job.engine_label = label
            manager = self._asr_manager()
            expected = resolved.duration
            if job.cancel_event.is_set():
                # Cancelled while the model loaded: report the (empty) partial
                # and never start a decode on an engine about to be freed.
                return self._finish_url_state(job, _loop.WindowsState(), expected, validated, manager, partial=True)
            state, expected = self._ingest_via_downloads(job, resolved, url, runtime, backend, manager, expected)
            return self._finish_url_state(job, state, expected, validated, manager, partial=job.cancel_event.is_set())
        finally:
            lease.end(token)

    def _download_and_transcribe(self, job, resolved, runtime, backend, manager, expected):
        """One download-tier attempt: ingest the audio, then transcribe it."""
        from voice_typer.server.media_ingest import (
            decoder as _decoder,
            downloader as _downloader,
            runtime as _runtime,
        )

        self._publish_media_progress(job, 0.0, "downloading", None, expected)
        with _downloader.temp_audio_download(
            resolved.webpage_url or resolved.audio_url,
            js_runtimes=_runtime.js_runtime_options(runtime),
            on_progress=lambda frac: self._publish_media_progress(job, frac, "downloading", None, expected),
        ) as tmp_path:
            # An Instagram-style resolver reports duration=None: probe the
            # file that was actually ingested so percent/ETA (and the
            # truncation gate) have a real total.
            total = expected
            if total is None:
                total = _decoder.probe_duration_seconds(str(tmp_path))
            job.ingest_tier = "download"
            job.expected_seconds = total
            return self._transcribe_file(tmp_path, backend, manager, job, total), total

    def _ingest_via_downloads(self, job, resolved, url: str, runtime, backend, manager, expected):
        """Download tier with ONE retry; returns ``(state, expected)``.

        Only ``RETRYABLE_INGEST_CODES`` earn a second attempt. Every other
        code is a verdict about the media itself (no audio track, DRM, a
        truncated decode): it is raised on first occurrence, so a verdict
        costs exactly one download + decode + transcribe.
        """
        from voice_typer.server.media_ingest import engine_loop as _loop
        from voice_typer.server.media_ingest.errors import MediaIngestError, is_retryable_ingest_code

        try:
            return self._download_and_transcribe(job, resolved, runtime, backend, manager, expected)
        except MediaIngestError as exc:
            if job.cancel_event.is_set():
                return _loop.WindowsState(), expected
            if not is_retryable_ingest_code(exc.code):
                raise
            log.warning("[MEDIA] audio download failed (%s); retrying once", exc.code)

        # ONE re-resolve plus ONE download retry before the stream tier is
        # even considered: the observed download failure was transient, so
        # a single hiccup must not degrade the job to streaming.
        refreshed = resolved
        try:
            refreshed = self._resolve_media(resolved.webpage_url or url, runtime)
            if expected is None:
                expected = refreshed.duration
            return self._download_and_transcribe(job, refreshed, runtime, backend, manager, expected)
        except MediaIngestError as exc:
            if job.cancel_event.is_set():
                return _loop.WindowsState(), expected
            if not is_retryable_ingest_code(exc.code):
                raise
            download_error = exc
            log.warning("[MEDIA] audio download retry failed (%s)", exc.code)
        return self._ingest_via_streams(
            job, refreshed, runtime, backend, manager, expected, download_error=download_error
        )

    def _ingest_via_streams(self, job, resolved, runtime, backend, manager, expected, *, download_error):
        """Guarded stream tier: probe first, retry only transient failures.

        The probe keeps the tier honest (never stream a URL that does not
        prove itself a direct media resource with real audio), and the loop
        retries only ``RETRYABLE_INGEST_CODES``; the finish step runs OUTSIDE
        it, so a truncated stream is one decode and one verdict.
        """
        from voice_typer.server.media_ingest import (
            decoder as _decoder,
            engine_loop as _loop,
            validation as _validation,
        )
        from voice_typer.server.media_ingest.errors import (
            DOWNLOAD_FAILED,
            URL_EXPIRED,
            MediaIngestError,
            is_retryable_ingest_code,
        )

        probe = _decoder.probe_remote(resolved.audio_url)
        probe_duration = probe.duration_seconds if probe is not None else None
        if (
            probe is None
            or probe.audio_streams < 1
            or probe_duration is None
            or probe_duration < _validation.MIN_MEDIA_SECONDS
        ):
            log.warning(
                "[MEDIA] stream fallback refused: %s",
                "not a direct media resource"
                if probe is None
                else f"audio_streams={probe.audio_streams} duration={probe_duration}",
            )
            raise MediaIngestError(
                DOWNLOAD_FAILED,
                "the audio could not be downloaded and the stream could not be verified",
            ) from download_error

        if expected is None:
            expected = probe_duration
        job.ingest_tier = "stream"
        job.note = "stream_fallback"
        job.expected_seconds = expected
        log.info(
            "[MEDIA] stream fallback: download failed twice (%s); probe says audio_streams=%d duration=%.1fs",
            download_error.code,
            probe.audio_streams,
            probe_duration,
        )

        state = _loop.WindowsState()
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
                stream_duration = resolved.duration or expected

                def _on_stream_progress(frac: float, eta: float | None, _d: float | None = stream_duration) -> None:
                    self._publish_media_progress(job, frac, "transcribing", eta, _d)

                state = _loop.transcribe_windows(
                    chunks,
                    backend,
                    cancel_event=job.cancel_event,
                    on_progress=_on_stream_progress,
                    total_seconds=stream_duration,
                    state=state,
                    lane=manager.asr_lane,
                )
            except MediaIngestError as exc:
                if job.cancel_event.is_set():
                    break
                last_error = exc
                log.warning(
                    "[MEDIA] stream attempt %d/%d failed (%s)",
                    attempt + 1,
                    MAX_STREAM_ATTEMPTS,
                    exc.code,
                )
                if not is_retryable_ingest_code(exc.code):
                    raise
                if exc.code == URL_EXPIRED and attempt + 1 < MAX_STREAM_ATTEMPTS:
                    try:
                        resolved = self._resolve_media(resolved.webpage_url, runtime)
                    except MediaIngestError as resolve_exc:
                        last_error = resolve_exc
                        break
                continue
            return state, expected
        if job.cancel_event.is_set():
            return state, expected
        assert last_error is not None
        raise last_error

    def _finish_url_state(self, job, state, expected, validated, manager, *, partial: bool = False) -> dict:
        """Common finish for every URL tier (download / retry / stream)."""
        from voice_typer.server.media_ingest import validation as _validation

        silent = _validation.is_total_silence(state.rms, state.silence_pct)
        return self._finish_media_job(
            job,
            state.text,
            duration=state.decoded_seconds if state.decoded_seconds else expected,
            decoded_seconds=state.decoded_seconds,
            expected_seconds=expected,
            partial=partial,
            quality=self._job_quality(state, len(state.text)),
            silent=silent and not partial,
            validated=validated,
        )

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
                        "tier": job.ingest_tier,
                        "note": job.note,
                    },
                }
            )
        except Exception:  # noqa: BLE001, best-effort
            log.debug("[MEDIA] progress publish failed", exc_info=True)
