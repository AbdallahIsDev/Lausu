"""Mic-guard / output-level IPC handler mixin: 3 commands.

* ``get_microphone_volume`` — read the real capture knob (guard surface).
* ``set_microphone_volume`` — the ``[Back to 100%]`` write. Always writes;
  the guard's anti-flap budget only bounds its OWN automatic restores.
* ``set_output_volume`` — the S1 ``[Lower to 75%]`` offer. The only place
  the app moves the speaker knob outside dictation ducking, and it only
  ever runs from an explicit user press.
"""

from typing import cast

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.ipc.validation import (
    ResponseEnvelope,
    Schema,
    _validate_dict_payload,
)

# Schema for the two level-writing commands. ``clamp_range`` coerces rather
# than rejects, so a slider that lands on 1.0000000002 still writes.
_LEVEL_SCHEMA: Schema = {
    "level": {
        "type": (int, float),
        "required": True,
        "clamp_range": (0.0, 1.0),
    },
}


class MicVolumeHandlersMixin(HandlerBase):
    """Mixin: capture-gain guard + output-level write surface."""

    def _handle_get_microphone_volume(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``get_microphone_volume`` IPC command."""
        try:
            resp["type"] = "microphone_volume"
            resp["data"] = self.service.get_microphone_volume()
        except Exception as exc:
            # generic WS-path envelope (no ``str(exc)`` leak).
            self._respond_with_error(resp, exc, "get_microphone_volume")
        return resp

    def _handle_set_microphone_volume(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``set_microphone_volume`` IPC command."""

        def body(d: dict) -> dict:
            validated, error = _validate_dict_payload(d, _LEVEL_SCHEMA)
            if error:
                return error
            assert validated is not None
            level = float(cast(float | int | str, validated["level"]))
            return {"type": "microphone_volume", "data": self.service.set_microphone_volume(level)}

        return self._wrap(
            cmd_name="set_microphone_volume",
            resp_type="microphone_volume",
            data=data,
            resp=resp,
            body=body,
        )

    def _handle_set_output_volume(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``set_output_volume`` IPC command."""

        def body(d: dict) -> dict:
            validated, error = _validate_dict_payload(d, _LEVEL_SCHEMA)
            if error:
                return error
            assert validated is not None
            level = float(cast(float | int | str, validated["level"]))
            result = self.service.set_output_volume(level)
            return {"type": "output_volume", "data": result}

        return self._wrap(
            cmd_name="set_output_volume",
            resp_type="output_volume",
            data=data,
            resp=resp,
            body=body,
        )


__all__ = ["MicVolumeHandlersMixin"]
