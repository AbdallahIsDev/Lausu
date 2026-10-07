"""Screenshot beta IPC handlers (Windows-only, flag-gated)."""

from __future__ import annotations

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.ipc.validation import ErrorCodes, ResponseEnvelope


class ScreenshotHandlersMixin(HandlerBase):
    _WINDOWS_ONLY_MSG = "Screenshots are Windows-only in this beta"

    def _screenshot_gate(self, resp: dict) -> dict | None:
        from voice_typer.server.platform_utils import is_windows

        if not is_windows():
            return self._error_response(resp, self._WINDOWS_ONLY_MSG, code="screenshot_unsupported")
        if not bool(getattr(self.app.config, "screenshot_beta_enabled", False)):
            return self._error_response(resp, "Screenshot beta is disabled", code="screenshot_disabled")
        if not bool(getattr(self.app.config, "screenshot_consent", False)):
            return self._error_response(resp, "Screenshot consent not granted", code="screenshot_no_consent")
        return None

    def _handle_screenshot_capture(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        def body(d: dict) -> dict:
            gated = self._screenshot_gate(resp)
            if gated is not None:
                return gated
            from voice_typer.server.screenshots import capture as _cap, paths as _paths, store as _store

            cycle_id = str(d["cycle_id"])
            try:
                result = _cap.capture_rect(d["rect"], _paths.shot_path(cycle_id))
            except ValueError:
                return self._error_response(resp, "Invalid rect", code=ErrorCodes.INVALID_FIELD, field="rect")
            except RuntimeError:
                return self._error_response(resp, self._WINDOWS_ONLY_MSG, code="screenshot_unsupported")
            try:
                _store.register_shot(cycle_id, result["path"])
            except _store.AlreadyCapturedError:
                return self._error_response(resp, "One screenshot per recording", code="screenshot_already_captured")
            _store.write_meta(cycle_id, {**_store.read_meta(cycle_id), "shots": [result["path"]]})
            return {"type": "screenshot_captured", "data": result}

        return self._wrap(
            cmd_name="screenshot_capture",
            resp_type="screenshot_captured",
            data=data,
            resp=resp,
            body=body,
            schema={"cycle_id": {"type": str, "required": True}, "rect": {"type": dict, "required": True}},
            pre_coerce=False,
        )

    def _handle_screenshot_clear_cycle(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        def body(d: dict) -> dict:
            from voice_typer.server.screenshots import store as _store

            _store.clear_cycle(str(d["cycle_id"]))
            return {"type": "ack"}

        return self._wrap(
            cmd_name="screenshot_clear_cycle",
            resp_type="ack",
            data=data,
            resp=resp,
            body=body,
            schema={"cycle_id": {"type": str, "required": True}},
            pre_coerce=False,
        )

    def _handle_screenshot_get_status(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        def body(d: dict) -> dict:
            from voice_typer.server.platform_utils import is_windows
            from voice_typer.server.screenshots import store as _store

            payload: dict = {
                "supported": is_windows(),
                "enabled": bool(getattr(self.app.config, "screenshot_beta_enabled", False)),
                "consent": bool(getattr(self.app.config, "screenshot_consent", False)),
            }
            if d.get("cycle_id"):
                payload.update(_store.get_status(str(d["cycle_id"])))
            return {"type": "screenshot_status", "data": payload}

        return self._wrap(
            cmd_name="screenshot_get_status",
            resp_type="screenshot_status",
            data=data,
            resp=resp,
            body=body,
            schema={"cycle_id": {"type": str, "required": False, "default": None}},
        )

    def _handle_screenshot_set_consent(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        def body(d: dict) -> dict:
            value = bool(d["consented"])
            self.service.apply_config({"screenshot_consent": value})
            return {"type": "ack", "data": {"consent": value}}

        return self._wrap(
            cmd_name="screenshot_set_consent",
            resp_type="ack",
            data=data,
            resp=resp,
            body=body,
            schema={"consented": {"type": bool, "required": True}},
            pre_coerce=False,
        )


__all__ = ["ScreenshotHandlersMixin"]
