"""TTS IPC handler mixin: tts_status, tts_prepare, tts_speak, tts_stop.

This module exists so the renderer's Models page can drive the local TTS engines
through the same command path as the ASR model catalog. Failures come back as a
stable CODE the renderer maps to plain-language copy; the raw engine message,
HTTP status and body tail stay in the log.
"""

from __future__ import annotations

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log
from voice_typer.server.ipc.validation import ErrorCodes, ResponseEnvelope
from voice_typer.server.tts.playback import PlaybackError
from voice_typer.server.tts.types import TtsError

#: Stable failure codes the renderer maps to localized copy (never shown raw).
TTS_ERR_NOT_INSTALLED = "not_installed"
TTS_ERR_NO_OUTPUT = "no_output"
TTS_ERR_GENERIC = "generic"

_NO_OUTPUT_HINTS = (
    "no default output",
    "no output device",
    "invalid device",
    "device unavailable",
    "error opening",
    "portaudio",
)
_NOT_INSTALLED_HINTS = (
    "not installed",
    "runtime missing",
    "artifact missing",
    "runtime binary not found",
    "not configured",
    "turned off",
)


def tts_error_code(exc: BaseException) -> str:
    """Map a backend TTS failure onto one of the renderer's plain-language codes."""
    text = str(exc).lower()
    if any(hint in text for hint in _NO_OUTPUT_HINTS):
        return TTS_ERR_NO_OUTPUT
    if any(hint in text for hint in _NOT_INSTALLED_HINTS):
        return TTS_ERR_NOT_INSTALLED
    if isinstance(exc, PlaybackError):
        return TTS_ERR_GENERIC
    return TTS_ERR_GENERIC


class TtsHandlersMixin(HandlerBase):
    """Mixin: local text-to-speech IPC handlers."""

    def _handle_tts_status(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``tts_status`` (read-only)."""
        try:
            resp["type"] = "tts_status"
            resp["data"] = self.service.get_tts_status()
        except Exception as exc:
            self._respond_with_error(resp, exc, "tts_status")
        return resp

    def _handle_tts_prepare(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``tts_prepare``: download one engine pack."""

        def body(d: dict) -> dict:
            engine = d.get("engine", "") or ""
            if not engine:
                return self._error_response(
                    resp,
                    "Missing 'engine' parameter",
                    code=ErrorCodes.MISSING_FIELD,
                    field="engine",
                )
            log.info("[IPC] tts_prepare for '%s'", engine)
            return {"type": "tts_prepare_result", "data": self.service.tts_prepare(engine)}

        return self._wrap(
            cmd_name="tts_prepare",
            resp_type="tts_prepare_result",
            data=data,
            resp=resp,
            body=body,
            schema={"engine": {"type": str, "required": False, "default": ""}},
            pre_coerce=False,
        )

    def _handle_tts_speak(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``tts_speak``: render and start playing one engine's sample."""

        def body(d: dict) -> dict:
            text = d.get("text", "") or ""
            sample = bool(d.get("sample", False))
            if not sample and not text.strip():
                return self._error_response(
                    resp,
                    "Missing 'text' parameter",
                    code=ErrorCodes.MISSING_FIELD,
                    field="text",
                )
            engine = (d.get("engine") or "").strip() or None
            voice = (d.get("voice") or "").strip() or None
            try:
                result = self.service.tts_speak(text, engine, voice=voice, sample=sample)
            except TtsError as exc:
                log.warning("[TTS] tts_speak failed engine=%s: %s", engine or "configured", exc)
                return {"type": "tts_speak_result", "data": {"ok": False, "error": tts_error_code(exc)}}
            except Exception:
                log.exception("[TTS] tts_speak crashed engine=%s", engine or "configured")
                return {"type": "tts_speak_result", "data": {"ok": False, "error": TTS_ERR_GENERIC}}
            return {"type": "tts_speak_result", "data": {"ok": True, **result}}

        return self._wrap(
            cmd_name="tts_speak",
            resp_type="tts_speak_result",
            data=data,
            resp=resp,
            body=body,
            schema={
                "text": {"type": str, "required": False, "default": ""},
                "engine": {"type": str, "required": False, "default": ""},
                "voice": {"type": str, "required": False, "default": ""},
                "sample": {"type": bool, "required": False, "default": False},
            },
            pre_coerce=False,
        )

    def _handle_tts_stop(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``tts_stop``: interrupt the clip that is playing."""
        try:
            resp["type"] = "tts_stop"
            resp["data"] = self.service.tts_stop()
        except Exception as exc:
            self._respond_with_error(resp, exc, "tts_stop")
        return resp
