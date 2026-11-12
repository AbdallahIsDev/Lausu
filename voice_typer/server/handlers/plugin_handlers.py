"""Plugin IPC handlers: discovery plus one validated setting write.

Discovery is fail-safe: a build with no plugin workspace (the normal shipped
case) answers with an empty list rather than an error, and one broken
manifest never hides the rest. Settings are validated against the manifest
declaration and persisted beside it, never in app config.
"""

from voice_typer.server import internal_plugin_hook
from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.ipc.validation import ResponseEnvelope
from voice_typer.server.plugins import discover, get_plugin
from voice_typer.server.plugins.settings_store import (
    PluginSettingError,
    load_values,
    set_value,
)


class PluginHandlersMixin(HandlerBase):
    """Mixin: plugin discovery + setting-write IPC handlers."""

    def _handle_get_plugins(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``get_plugins`` IPC command."""
        try:
            active = internal_plugin_hook.requested_plugin_id(self.app)
            resp["type"] = "plugins"
            # `available` drives the Plugins nav item. It is answered even
            # when the surface is hidden, so the renderer can tell "not
            # allowed to see this" apart from "nothing installed".
            resp["data"] = {
                "available": internal_plugin_hook.internal_surface_enabled(),
                "plugins": [
                    p.to_dict(active=p.id == active and bool(active), values=load_values(p))
                    for p in discover()
                ],
            }
        except Exception as exc:
            # generic WS-path envelope (no ``str(exc)`` leak).
            self._respond_with_error(resp, exc, "get_plugins")
        return resp

    def _handle_set_plugin_setting(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Persist one manifest-declared setting for one installed plugin."""
        try:
            payload = data if isinstance(data, dict) else {}
            plugin_id = payload.get("plugin_id")
            key = payload.get("key")
            if not isinstance(plugin_id, str) or not isinstance(key, str):
                raise PluginSettingError("plugin_id and key are required")
            info = get_plugin(plugin_id)
            if info is None:
                raise PluginSettingError(f"unknown plugin {plugin_id!r}")
            value = set_value(info, key, payload.get("value"))
            resp["type"] = "plugin_setting"
            resp["data"] = {"plugin_id": plugin_id, "key": key, "value": value}
        except PluginSettingError as exc:
            # Expected rejection (unknown plugin/key, wrong type/range): a
            # plain client error, not an internal fault. The message names the
            # setting and the rule, never internals.
            self._error_response(resp, str(exc), code="client.invalid_field")
        except Exception as exc:
            self._respond_with_error(resp, exc, "set_plugin_setting")
        return resp
