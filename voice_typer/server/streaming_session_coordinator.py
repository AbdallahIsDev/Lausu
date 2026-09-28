"""Streaming session lifecycle coordination."""

from __future__ import annotations

import logging
import os

from voice_typer.server import event_bus
from voice_typer.server.streaming import StreamingConfig, StreamingTranscriptionSession

log = logging.getLogger(__name__)


def _publish_live_preview_unsupported(cycle_id: str) -> None:
    """Publish the ONE-TIME per-recording "live preview unavailable" signal."""
    try:
        event_bus.publish(
            {
                "type": "transcription_partial",
                "data": {
                    "text": "",
                    "cycle_id": cycle_id,
                    "supported": False,
                },
            },
        )
    except Exception:
        log.debug(
            "[STREAMING] Failed to publish live-preview-unavailable signal",
            exc_info=True,
        )
    # (SEC-026, no python bridge) can show a localized hint instead of
    try:
        event_bus.publish(
            {
                "type": "bubble_set_state",
                "data": {
                    "state": "recording",
                    "live_preview_supported": False,
                },
            },
        )
    except Exception:
        log.debug(
            "[STREAMING] Failed to mirror live-preview-unavailable to bubble",
            exc_info=True,
        )


class StreamingSessionCoordinator:
    """Streaming-session startup + config helpers."""

    def __init__(self) -> None:
        # Stateless helper, all state lives on the controller.
        pass

    def streaming_enabled(self, controller) -> bool:
        """Return whether hidden streaming should run for the next recording."""
        if os.environ.get("VOICE_TYPER_STREAMING") == "0":
            return False
        return controller._app.config.streaming_transcription

    def streaming_config(self, controller) -> StreamingConfig:
        cfg = controller._app.config
        return StreamingConfig(
            enabled=self.streaming_enabled(controller),
            chunk_seconds=cfg.streaming_chunk_seconds,
            step_seconds=cfg.streaming_step_seconds,
            left_overlap_seconds=cfg.streaming_left_overlap_seconds,
            right_guard_seconds=cfg.streaming_right_guard_seconds,
            min_first_chunk_seconds=cfg.streaming_min_first_chunk_seconds,
            silence_threshold=cfg.streaming_silence_threshold,
        )

    def start_streaming_session_if_enabled(self, controller) -> None:
        """Start hidden streaming work for the active recording if enabled."""
        app = controller._app
        controller.set_streaming_session(None)
        if not self.streaming_enabled(controller):
            return

        # Streaming requires word-level timestamps: in-process engines
        # expose ``transcribe_words``; the worker-backed shim instead
        # streams through the C6 worker session (checked below).
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr as _WorkerBackedAsr

        active = app.models.active_transcriber()
        if active is not None:
            log.info(
                "[STREAMING] Checking transcriber: %s has transcribe_words=%s worker_backed=%s",
                type(active).__name__,
                hasattr(active, "transcribe_words"),
                isinstance(active, _WorkerBackedAsr),
            )
        else:
            log.info("[STREAMING] No active transcriber, skipping streaming (cycle=%s)", app._cycle_id)
            return

        # ADR-0025 C6/C7: prefer the worker session when the hop can serve
        # it (pack present + connected + local backend). A worker-backed
        # backend has no in-process engine to fall back to.
        if self._try_start_worker_session(controller, active):
            return
        if active is not None and not hasattr(active, "transcribe_words"):
            log.info(
                "[STREAMING] Transcriber lacks transcribe_words, skipping streaming (cycle=%s)",
                app._cycle_id,
            )
            _publish_live_preview_unsupported(getattr(app, "_cycle_id", "") or "")
            return

        try:
            session = StreamingTranscriptionSession(
                recorder=app.recorder,
                transcriber=app.models.active_transcriber(),
                config=self.streaming_config(controller),
                sample_rate=app.config.sample_rate,
                # THREAD-REGISTRY: pass the app's registry so the
                thread_registry=getattr(app, "_thread_registry", None),
                # Correlation id echoed in every transcription_partial
                cycle_id=getattr(app, "_cycle_id", "") or "",
                # Residual fence: let the session check whether the
                busy_check=lambda: (
                    app.models.registry.is_busy(app.models.registry.active_name)
                    if getattr(getattr(app, "models", None), "registry", None) is not None
                    else False
                ),
            )
            session.start()
            controller.set_streaming_session(session)
            log.info("[STREAMING] Hidden streaming session started (cycle=%s)", app._cycle_id)
        except Exception as e:
            log.exception("[STREAMING] Failed to start streaming session: %s", e)
            controller.set_streaming_session(None)

    def _try_start_worker_session(self, controller, active) -> bool:
        """Start a worker-backed session; ``False`` means go in-process.

        Never raises: every failure mode (gate off, open unanswered,
        thread start) is a fallback signal, logged once each.
        """
        from voice_typer.server import worker_path
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr as _WorkerBackedAsr
        from voice_typer.server.worker_client import get_shared_client
        from voice_typer.server.worker_streaming import WorkerStreamingSession

        try:
            app = controller._app
            # Worker-backed backends stream via the hop despite exposing
            # no in-process word engine (C7). isinstance, not a flag
            # read: MagicMock doubles auto-create any attribute.
            if (
                active is not None
                and not hasattr(active, "transcribe_words")
                and not isinstance(active, _WorkerBackedAsr)
            ):
                return False
            ok, reason = worker_path.worker_path_available(app)
            if not ok:
                log.info("[STREAMING] worker path off (%s), in-process session", reason)
                return False
            session = WorkerStreamingSession(
                recorder=app.recorder,
                client=get_shared_client(),
                config=self.streaming_config(controller),
                sample_rate=app.config.sample_rate,
                cycle_id=getattr(app, "_cycle_id", "") or "",
                language=getattr(app.config, "language", None),
                thread_registry=getattr(app, "_thread_registry", None),
            )
            if not session.start():
                log.info("[STREAMING] worker session open failed, in-process session")
                return False
            controller.set_streaming_session(session)
            log.info("[STREAMING] Hidden worker streaming session started (cycle=%s)", app._cycle_id)
            return True
        except Exception:
            log.debug("[STREAMING] worker session start failed, falling back", exc_info=True)
            return False
