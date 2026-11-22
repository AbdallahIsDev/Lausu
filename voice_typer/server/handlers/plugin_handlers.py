"""Plugin discovery IPC handler.

Discovery is fail-safe: an install whose developer surface is locked (every
end-user install) answers with the flag off and an EMPTY list - it must not
leak the bundled plugin inventory - and one broken manifest never hides the
rest. There is no plugin-specific settings write path: the shared settings
live in the main application config and are written with ``set_config``.
"""

from voice_typer.server import internal_plugin_hook
from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.ipc.validation import ResponseEnvelope
from voice_typer.server.plugins import discover


class PluginHandlersMixin(HandlerBase):
    """Mixin: plugin discovery (the only plugin-specific IPC surface)."""

    def _plugin_surface_enabled(self) -> bool:
        return internal_plugin_hook.internal_surface_enabled(getattr(self.app, "config", None))

    def _handle_get_plugins(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``get_plugins`` IPC command."""
        try:
            available = self._plugin_surface_enabled()
            plugins: list[dict[str, object]] = []
            if available:
                active = internal_plugin_hook.requested_plugin_id(self.app)
                plugins = [p.to_dict(active=p.id == active) for p in discover()]
            resp["type"] = "plugins"
            # `available` drives the Plugins nav item. A locked install
            # answers the flag with no inventory at all: the catalog is an
            # owner-only surface, not something a shipped app advertises.
            resp["data"] = {"available": available, "plugins": plugins}
        except Exception as exc:
            # generic WS-path envelope (no ``str(exc)`` leak).
            self._respond_with_error(resp, exc, "get_plugins")
        return resp
