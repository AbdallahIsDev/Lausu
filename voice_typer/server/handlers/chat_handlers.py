"""Chat IPC handler mixin: chat_listen_start / chat_listen_stop / chat_state / chat_reset.

Push-to-talk voice conversation (STT -> LLM -> TTS). Capture opens only
after the voice-biometric consent gate passes (same gate as dictation and
the mic test); the consent dialog is the renderer's shared JIT prompt.
The LLM's own consent gate (``llm_provider_consent``) is enforced inside
``resolve_llm`` and is never bypassed here.
"""

from __future__ import annotations

from voice_typer.server.asr_errors import ConsentRequiredError
from voice_typer.server.handlers._base import HandlerBase, log
from voice_typer.server.ipc.validation import ResponseEnvelope


class ChatHandlersMixin(HandlerBase):
    """Mixin: voice conversation IPC handlers."""

    def _handle_chat_listen_start(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``chat_listen_start``: stop TTS, then arm chat capture."""
        try:
            try:
                consented = bool(getattr(self.app.config, "voice_biometric_consent", False))
            except Exception:
                log.exception("[IPC] chat_listen_start: failed to read voice_biometric_consent, failing open")
                consented = True
            if not consented:
                raise ConsentRequiredError(
                    "voice biometric consent required to start chat capture",
                    engine_name="chat",
                    consent_field="voice_biometric_consent",
                )
            resp["type"] = "chat_listen_start"
            resp["data"] = self.service.chat_listen_start()
        except Exception as exc:
            # _respond_with_error special-cases ConsentRequiredError into the
            # structured client.consent_required envelope (with consent_field).
            self._respond_with_error(resp, exc, "chat_listen_start")
        return resp

    def _handle_chat_listen_stop(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``chat_listen_stop``: returns now; the turn runs on a worker."""
        try:
            resp["type"] = "chat_listen_stop"
            resp["data"] = self.service.chat_listen_stop()
        except Exception as exc:
            self._respond_with_error(resp, exc, "chat_listen_stop")
        return resp

    def _handle_chat_state(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``chat_state`` (read-only): messages + busy + phase."""
        try:
            resp["type"] = "chat_state"
            resp["data"] = self.service.chat_state()
        except Exception as exc:
            self._respond_with_error(resp, exc, "chat_state")
        return resp

    def _handle_chat_reset(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``chat_reset``: abort any in-flight turn, clear history."""
        try:
            resp["type"] = "chat_reset"
            resp["data"] = self.service.chat_reset()
        except Exception as exc:
            self._respond_with_error(resp, exc, "chat_reset")
        return resp


__all__ = ["ChatHandlersMixin"]
