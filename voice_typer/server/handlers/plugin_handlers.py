"""Plugin IPC handlers: discovery plus one validated setting write.

Discovery is fail-safe: an install whose developer surface is locked (every
end-user install) answers with the flag off and an EMPTY list - it must not
leak the bundled plugin inventory - and one broken manifest never hides the
rest. Settings are validated against the manifest declaration and persisted
beside it, never in app config.
"""

from voice_typer.server import internal_plugin_hook
from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.ipc.error_codes import ErrorCodes
from voice_typer.server.ipc.validation import ResponseEnvelope
from voice_typer.server.plugins import discover, get_plugin
from voice_typer.server.plugins.settings_store import (
    PluginSettingError,
    load_values,
    set_value,
)


class PluginHandlersMixin(HandlerBase):
    """Mixin: plugin discovery + setting-write IPC handlers."""

    def _plugin_surface_enabled(self) -> bool:
        return internal_plugin_hook.internal_surface_enabled(getattr(self.app, "config", None))

    def _handle_get_plugins(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``get_plugins`` IPC command."""
        try:
            available = self._plugin_surface_enabled()
            plugins: list[dict[str, object]] = []
            if available:
                active = internal_plugin_hook.requested_plugin_id(self.app)
                plugins = [p.to_dict(active=p.id == active, values=load_values(p)) for p in discover()]
            resp["type"] = "plugins"
            # `available` drives the Plugins nav item. A locked install
            # answers the flag with no inventory at all: the catalog is an
            # owner-only surface, not something a shipped app advertises.
            resp["data"] = {"available": available, "plugins": plugins}
        except Exception as exc:
            # generic WS-path envelope (no ``str(exc)`` leak).
            self._respond_with_error(resp, exc, "get_plugins")
        return resp

    def _handle_set_plugin_setting(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Persist one manifest-declared setting for one installed plugin."""
        try:
            if not self._plugin_surface_enabled():
                # Same answer as an unknown plugin: a locked install does not
                # confirm which plugins it ships.
                self._error_response(resp, "unknown plugin", code=ErrorCodes.NOT_FOUND)
                return resp
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
            self._error_response(resp, str(exc), code=ErrorCodes.INVALID_FIELD)
        except Exception as exc:
            self._respond_with_error(resp, exc, "set_plugin_setting")
        return resp
