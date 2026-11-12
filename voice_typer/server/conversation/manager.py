"""Conversation turn manager: one push-to-talk exchange at a time.

Owns the message list, the single-flight guard and the per-turn abort.
Never touches the IPC layer; the caller injects ``publish`` (the event
sink) and a ``service`` (TTS). The app supplies ``models``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any

from voice_typer.server._secrets import redact_secret
from voice_typer.server.conversation.capture import ChatCapture
from voice_typer.server.conversation.transcribe import transcribe_with_engine
from voice_typer.server.duration import format_duration
from voice_typer.server.model_providers import resolve_llm
from voice_typer.server.model_providers.contracts import ChatMessage
from voice_typer.server.model_providers.errors import ProviderError

log = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a voice assistant. Reply in one to three short spoken sentences. "
    "Never use markdown, bullet lists, headings, code blocks or emoji — your reply "
    "is read aloud by a text-to-speech engine."
)

_MAX_TOKENS = 256
_HISTORY_TURNS_MIN = 1
_HISTORY_TURNS_MAX = 32
_HISTORY_TURNS_DEFAULT = 8

# Manager-side guard for a capture nobody released (the page unmounted while
# the button was held, so no pointerup ever arrives). Matches the audio-side
# buffer cap in ``level_monitor/worker.py``; whichever fires first wins.
_CAPTURE_AUTO_FINISH_SECONDS = 30.0


class ChatManager:
    """Owns one voice-conversation thread. Half-duplex, single-flight."""

    def __init__(
        self,
        app: Any,
        config: Any,
        publish: Callable[[dict[str, Any]], None],
        *,
        service: Any | None = None,
        capture: ChatCapture | None = None,
    ) -> None:
        self._app = app
        self._config = config
        self._publish_fn = publish
        self._service = service
        self._capture = capture if capture is not None else ChatCapture()
        self.messages: list[ChatMessage] = []
        self.busy = False
        self.phase = "idle"
        self._listening = False
        self._lock = threading.Lock()
        # Bumped on every arm/reset; a worker that lost the race goes silent.
        self._turn_id = 0
        self._abort: threading.Event | None = None
        self._capture_started_at: float | None = None
        self._capture_watchdog_stop: threading.Event | None = None

    # ------------------------------------------------------------------ IPC ops

    def listen_start(self) -> dict[str, object]:
        mic_id = getattr(self._config, "microphone", None)
        with self._lock:
            if self.busy:
                log.info("[CHAT] listen_start refused: a turn is already in flight")
                return {"started": False, "sample_rate": 0}
            self._tts_stop()
            try:
                sample_rate = self._capture.start(mic_id)
            except Exception as exc:
                log.warning("[CHAT] capture start failed: %s", redact_secret(str(exc)))
                return {"started": False, "sample_rate": 0}
            self.busy = True
            self._listening = True
            self.phase = "listening"
            self._capture_started_at = time.monotonic()
            self._arm_capture_watchdog_locked()
            watchdog = self._capture_watchdog_stop
        # Published outside the lock so the phase indicator is event-driven, but
        # only while this arm is still the current one: a reset() that landed in
        # between must not be overwritten by a late "listening".
        with self._lock:
            still_armed = self._listening and self._capture_watchdog_stop is watchdog
        if still_armed:
            self._publish({"phase": "listening"})
        return {"started": True, "sample_rate": sample_rate}

    def listen_stop(self) -> dict[str, object]:
        with self._lock:
            if not self._listening:
                return {"accepted": False}
            self._listening = False
            self._capture_started_at = None
            self._disarm_capture_watchdog_locked()
            self._turn_id += 1
            turn_id = self._turn_id
            abort = threading.Event()
            self._abort = abort
            self.phase = "transcribing"
        # daemon: the IPC thread must never wait on a model call (RACE-008).
        thread = threading.Thread(
            target=self._run_turn,
            args=(turn_id, abort),
            name="chat-turn",
            daemon=True,
        )
        thread.start()
        return {"accepted": True}

    def state(self) -> dict[str, object]:
        with self._lock:
            return {
                "messages": [{"role": m.role, "text": m.content} for m in self.messages],
                "busy": self.busy,
                "phase": self.phase,
            }

    def reset(self) -> dict[str, object]:
        with self._lock:
            self._turn_id += 1
            abort, self._abort = self._abort, None
            self.messages.clear()
            self.busy = False
            self.phase = "idle"
            self._listening = False
            self._capture_started_at = None
            self._disarm_capture_watchdog_locked()
        if abort is not None:
            abort.set()
        self._capture.cancel()
        self._tts_stop()
        self._publish({"phase": "idle"})
        return {"ok": True}

    # ------------------------------------------------------------------ turn body

    def _run_turn(self, turn_id: int, abort: threading.Event) -> None:
        started = time.perf_counter()
        try:
            self._publish({"phase": "transcribing"})
            try:
                audio = self._capture.stop()
            except Exception as exc:
                log.warning("[CHAT] capture stop failed: %s", redact_secret(str(exc)))
                return self._finish_error("transcription_failed", turn_id)
            engine = self._active_engine()
            if engine is None or audio.size == 0:
                reason = "no_engine_loaded" if engine is None else "no_speech"
                return self._finish_error(reason, turn_id)
            try:
                text = transcribe_with_engine(engine, audio).strip()
            except Exception as exc:
                log.warning("[CHAT] transcription failed: %s", redact_secret(str(exc)))
                return self._finish_error("transcription_failed", turn_id)
            if not text:
                log.info("[CHAT] empty transcript; skipping the LLM")
                return self._finish_error("no_speech", turn_id)
            with self._lock:
                if self._stale_locked(turn_id):
                    return
                self.messages.append(ChatMessage("user", text))
                history = list(self.messages)
            self._publish({"phase": "thinking", "role": "user", "text": text})
            try:
                resolved = resolve_llm(self._config)
                reply = resolved.client().complete(
                    self._llm_messages(history),
                    max_tokens=_MAX_TOKENS,
                    abort_event=abort,
                )
            except ProviderError as exc:
                code = getattr(exc, "code", "server.provider_error")
                log.warning(
                    "[CHAT] LLM provider failed (code=%s provider=%s): %s",
                    code,
                    getattr(exc, "provider", ""),
                    redact_secret(str(exc)),
                )
                return self._finish_error(code, turn_id)
            except Exception as exc:
                log.warning("[CHAT] LLM call failed: %s", redact_secret(str(exc)))
                return self._finish_error("server.provider_error", turn_id)
            reply = (reply or "").strip()
            if not reply:
                log.warning("[CHAT] LLM returned an empty reply")
                return self._finish_error("server.provider_error", turn_id)
            with self._lock:
                if self._stale_locked(turn_id):
                    return
                self.messages.append(ChatMessage("assistant", reply))
            self._publish({"phase": "speaking", "role": "assistant", "text": reply})
            self._tts_speak(reply)
            self._finish_idle(turn_id)
            log.info(
                "[CHAT] turn completed chars=%d%s",
                len(reply),
                format_duration(time.perf_counter() - started),
            )
        except Exception as exc:
            log.exception("[CHAT] turn crashed: %s", redact_secret(str(exc)))
            self._finish_error("server.internal_error", turn_id)

    def _active_engine(self) -> Any | None:
        models = getattr(self._app, "models", None)
        if models is None:
            return None
        try:
            engine = models.active_transcriber()
        except Exception as exc:
            log.warning("[CHAT] active_transcriber() failed: %s", redact_secret(str(exc)))
            return None
        if engine is None or not getattr(engine, "is_loaded", False):
            return None
        return engine

    def _llm_messages(self, history: Sequence[ChatMessage]) -> list[ChatMessage]:
        system_text = str(getattr(self._config, "chat_system_prompt", "") or "").strip()
        if not system_text:
            system_text = DEFAULT_SYSTEM_PROMPT
        try:
            turns = int(getattr(self._config, "chat_history_turns", _HISTORY_TURNS_DEFAULT))
        except (TypeError, ValueError):
            turns = _HISTORY_TURNS_DEFAULT
        turns = max(_HISTORY_TURNS_MIN, min(_HISTORY_TURNS_MAX, turns))
        return [ChatMessage("system", system_text), *history[-2 * turns :]]

    # ------------------------------------------------------------- state helpers

    def _stale_locked(self, turn_id: int) -> bool:
        return turn_id != self._turn_id

    def _arm_capture_watchdog_locked(self) -> None:
        """Start the bounded auto-finish guard for this capture."""
        stop = threading.Event()
        self._capture_watchdog_stop = stop
        # daemon: the guard only flips manager state, never owns cleanup
        # (RACE-008); it also exits on the stop Event, not a one-shot Timer
        # (RACE-013).
        thread = threading.Thread(
            target=self._capture_watchdog,
            args=(stop,),
            name="chat-capture-watchdog",
            daemon=True,
        )
        thread.start()

    def _disarm_capture_watchdog_locked(self) -> None:
        stop, self._capture_watchdog_stop = self._capture_watchdog_stop, None
        if stop is not None:
            stop.set()

    def _capture_watchdog(self, stop: threading.Event) -> None:
        """Finish a capture that outlived the cap without a release."""
        while True:
            with self._lock:
                if self._capture_watchdog_stop is not stop:
                    return
                if not self._listening or self._capture_started_at is None:
                    return
                remaining = _CAPTURE_AUTO_FINISH_SECONDS - (time.monotonic() - self._capture_started_at)
            if remaining > 0:
                if stop.wait(remaining):
                    return
                continue
            with self._lock:
                if self._capture_watchdog_stop is not stop or not self._listening:
                    return
            log.warning(
                "[CHAT] capture held past the %.0fs cap with no release; finishing the turn",
                _CAPTURE_AUTO_FINISH_SECONDS,
            )
            self.listen_stop()
            return

    def _tts_speak(self, reply: str) -> None:
        service = self._tts_service()
        if service is None:
            log.debug("[CHAT] no TTS service; the reply stays text-only")
            return
        try:
            service.tts_speak(reply)
        except Exception as exc:
            # The reply is already on screen; audio failing must not hide it.
            log.warning("[CHAT] TTS failed; the reply is text-only: %s", redact_secret(str(exc)))

    def _tts_stop(self) -> None:
        service = self._tts_service()
        if service is None:
            return
        try:
            service.tts_stop()
        except Exception as exc:
            log.warning("[CHAT] tts_stop failed: %s", redact_secret(str(exc)))

    def _tts_service(self) -> Any | None:
        if self._service is not None:
            return self._service
        return getattr(self._app, "service", None)

    def _finish_error(self, code: str, turn_id: int) -> None:
        with self._lock:
            if self._stale_locked(turn_id):
                return
            self.phase = "idle"
            self.busy = False
            self._listening = False
            self._capture_started_at = None
            self._disarm_capture_watchdog_locked()
        self._publish({"phase": "error", "error_code": code})
        self._publish({"phase": "idle"})

    def _finish_idle(self, turn_id: int) -> None:
        with self._lock:
            if self._stale_locked(turn_id):
                return
            self.phase = "idle"
            self.busy = False
            self._listening = False
            self._capture_started_at = None
            self._disarm_capture_watchdog_locked()
        self._publish({"phase": "idle"})

    def _publish(self, payload: dict[str, Any]) -> None:
        try:
            self._publish_fn(payload)
        except Exception:
            log.warning("[CHAT] chat_turn publish failed", exc_info=True)


__all__ = ["ChatManager", "DEFAULT_SYSTEM_PROMPT"]
