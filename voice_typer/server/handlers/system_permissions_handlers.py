"""Platform permission IPC handlers: macOS accessibility + Linux polkit.

Split from ``voice_typer/server/handlers/system_handlers.py`` (create-first);
``SystemHandlersMixin`` composes this mixin so the historical handler names
keep resolving on the composed IPC server class.
"""

from __future__ import annotations

import subprocess

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log
from voice_typer.server.ipc.validation import ResponseEnvelope

# Platform probes + polkit helpers are patched on the facade by tests, so they
# MUST be re-resolved there on every call (never imported by value).
_facade = lazy_module("voice_typer.server.handlers.system_handlers")


class _SystemPermissionsHandlersMixin(HandlerBase):
    """macOS accessibility probe/reset + Linux polkit permission reset."""

    def _handle_check_accessibility(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``check_accessibility`` IPC command.

        Returns ``{"granted": bool, "platform": "macos"|"windows"|"linux"}``.
        """

        def body(d: dict) -> dict:
            import sys as _sys

            granted = True
            # Canonical platform string. ``_sys.platform`` is
            platform_name = "macos" if _facade.is_macos() else _sys.platform
            if _facade.is_macos():
                try:
                    import ctypes

                    # AXIsProcessTrusted() is the official API.
                    app_services = ctypes.cdll.LoadLibrary(
                        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
                    )
                    granted = bool(app_services.AXIsProcessTrusted())
                except Exception as exc:
                    log.warning(
                        "[IPC] check_accessibility: AXIsProcessTrusted ctypes load "
                        "failed (%s); treating as not-granted (check_failed)",
                        exc,
                    )
                    return {
                        "type": "accessibility_status",
                        "data": {
                            "granted": False,
                            "platform": "macos",
                            "reason": "check_failed",
                        },
                    }
            status_data: dict = {
                "granted": granted,
                "platform": platform_name,
            }
            if _facade.is_macos() and not granted:
                from voice_typer.server.server_platform.macos_bundle_id import (
                    resolve_host_bundle_id,
                )

                bundle_id = resolve_host_bundle_id()
                if bundle_id:
                    # (mirrors the reset handler's convention).
                    from voice_typer.server.server_platform.macos_bundle_id import (
                        tccutil_reset_command_str,
                    )

                    status_data["suggest_reset"] = True
                    status_data["reset_command"] = tccutil_reset_command_str("Accessibility", bundle_id)
                else:
                    status_data["suggest_reset"] = False
            return {"type": "accessibility_status", "data": status_data}

        return self._wrap(
            cmd_name="check_accessibility",
            resp_type="accessibility_status",
            data=data,
            resp=resp,
            body=body,
            schema={},
            pre_coerce=False,
        )

    def _handle_reset_macos_accessibility(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``reset_macos_accessibility`` IPC command."""

        def body(d: dict) -> dict:
            if not _facade.is_macos():
                return {
                    "type": "ack",
                    "data": {
                        "ok": False,
                        "command": None,
                        "error": "unsupported_platform",
                    },
                }

            from voice_typer.server.permissions import _open_macos_accessibility_settings
            from voice_typer.server.server_platform.macos_bundle_id import (
                resolve_host_bundle_id,
                tccutil_reset_command,
                tccutil_reset_command_str,
            )

            bundle_id = resolve_host_bundle_id()
            if not bundle_id:
                return {
                    "type": "ack",
                    "data": {
                        "ok": False,
                        "command": None,
                        "error": "bundle_id_unresolved",
                    },
                }

            # Both forms come from the single construction point
            command = tccutil_reset_command_str("Accessibility", bundle_id)
            try:
                result = subprocess.run(
                    tccutil_reset_command("Accessibility", bundle_id),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                ok = result.returncode == 0
                tcc_error = None if ok else (result.stderr.strip() or "tccutil failed")
            except (subprocess.TimeoutExpired, OSError) as exc:
                ok = False
                tcc_error = f"tccutil failed: {exc}"

            # Re-open System Settings â†’ Privacy & Security â†’
            _open_macos_accessibility_settings()

            return {
                "type": "ack",
                "data": {"ok": ok, "command": command, "error": tcc_error},
            }

        return self._wrap(
            cmd_name="reset_macos_accessibility",
            resp_type="ack",
            data=data,
            resp=resp,
            body=body,
            schema={},
            pre_coerce=False,
        )

    def _handle_reset_linux_permissions(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``reset_linux_permissions`` IPC command."""

        def body(d: dict) -> dict:
            if not _facade.is_linux():
                return {
                    "type": "ack",
                    "data": {
                        "ok": False,
                        "command": None,
                        "error": "unsupported_platform",
                        "actions": [],
                        "checks": {},
                    },
                }

            actions = _facade._enumerate_polkit_actions()
            command, ok, error_str = _facade._reset_polkit_authorization()
            checks: dict[str, str] = {}
            if ok:
                for action_id in actions:
                    checks[action_id] = _facade._polkit_check_authorization(action_id)

            return {
                "type": "ack",
                "data": {
                    "ok": ok,
                    "command": command,
                    "error": error_str,
                    "actions": actions,
                    "checks": checks,
                },
            }

        return self._wrap(
            cmd_name="reset_linux_permissions",
            resp_type="ack",
            data=data,
            resp=resp,
            body=body,
            schema={},
            pre_coerce=False,
        )
