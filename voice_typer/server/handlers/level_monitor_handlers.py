"""Level-monitor IPC handler mixin: level_monitor_* + live_preview commands."""

from voice_typer.server.asr_errors import ConsentRequiredError
from voice_typer.server.handlers._base import HandlerBase, log
from voice_typer.server.ipc.validation import ResponseEnvelope, _validate_dict_payload


class LevelMonitorHandlersMixin(HandlerBase):
    """Mixin: level-monitor IPC handlers (start / stop)."""

    def _handle_level_monitor_start(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``level_monitor_start`` IPC command."""

        def body(d: dict) -> dict:
            # opening the InputStream. The monitor captures audio
            try:
                if not getattr(self.app.config, "voice_biometric_consent", False):
                    raise ConsentRequiredError(
                        "voice biometric consent required to start level monitor",
                        engine_name="level_monitor",
                        consent_field="voice_biometric_consent",
                    )
            except ConsentRequiredError:
                raise
            except Exception:
                log.exception("[IPC] level_monitor_start: failed to read voice_biometric_consent, failing open")

            # validate ``mic_id`` type via the shared
            validated, error = _validate_dict_payload(
                d,
                {
                    "mic_id": {
                        "type": (str, type(None)),
                        "required": False,
                        "default": None,
                    },
                },
            )
            if error:
                return error
            # ``_validate_dict_payload`` returns None values only with an error.
            assert validated is not None
            mic_id = validated.get("mic_id")
            result = self.service.level_monitor_start(mic_id=mic_id)
            return {"type": "level_monitor_status", "data": result}

        return self._wrap(
            cmd_name="level_monitor_start",
            resp_type="level_monitor_status",
            data=data,
            resp=resp,
            body=body,
        )

    def _handle_level_monitor_stop(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``level_monitor_stop`` IPC command."""
        try:
            result = self.service.level_monitor_stop()
            resp["type"] = "level_monitor_status"
            resp["data"] = result
        except Exception as exc:
            # generic WS-path envelope (no ``str(exc)`` leak).
            self._respond_with_error(resp, exc, "level_monitor_stop")
        return resp

    def _handle_live_preview(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``live_preview`` IPC command (filtered Listen Live).

        Frames arrive as ``live_preview_audio`` push events; this command only
        flips the stream and answers with its real state (including
        ``monitoring``), so the renderer can say "unavailable" instead of
        showing a dead button.
        """

        def body(d: dict) -> dict:
            validated, error = _validate_dict_payload(
                d,
                {"enabled": {"type": bool, "required": True}},
            )
            if error:
                return error
            assert validated is not None
            result = self.service.live_preview(enabled=bool(validated["enabled"]))
            return {"type": "live_preview_status", "data": result}

        return self._wrap(
            cmd_name="live_preview",
            resp_type="live_preview_status",
            data=data,
            resp=resp,
            body=body,
        )
