"""TTS IPC handler mixin: tts_status, tts_prepare, tts_speak.

This module exists so the renderer's Models page can toggle and exercise the
local TTS engines through the same command path as the ASR model catalog.
"""

from __future__ import annotations

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log
from voice_typer.server.ipc.validation import ErrorCodes, ResponseEnvelope


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
        """Handle ``tts_speak``: render and play one engine (default: configured)."""

        def body(d: dict) -> dict:
            text = d.get("text", "") or ""
            if not text.strip():
                return self._error_response(
                    resp,
                    "Missing 'text' parameter",
                    code=ErrorCodes.MISSING_FIELD,
                    field="text",
                )
            engine = (d.get("engine") or "").strip() or None
            return {
                "type": "tts_speak_result",
                "data": self.service.tts_speak(text, engine),
            }

        return self._wrap(
            cmd_name="tts_speak",
            resp_type="tts_speak_result",
            data=data,
            resp=resp,
            body=body,
            schema={
                "text": {"type": str, "required": False, "default": ""},
                "engine": {"type": str, "required": False, "default": ""},
            },
            pre_coerce=False,
        )
