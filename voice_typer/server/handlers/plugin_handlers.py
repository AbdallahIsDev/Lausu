"""``get_plugins`` handler: the plugin list the Plugins page renders.

Discovery is fail-safe: a build with no plugin workspace (the normal shipped
case) answers with an empty list rather than an error, and one broken
manifest never hides the rest.
"""

from voice_typer.server import internal_plugin_hook
from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.ipc.validation import ResponseEnvelope
from voice_typer.server.plugins import discover


class PluginHandlersMixin(HandlerBase):
    """Mixin: plugin discovery IPC handler."""

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
                "plugins": [p.to_dict(active=p.id == active and bool(active)) for p in discover()],
            }
        except Exception as exc:
            # generic WS-path envelope (no ``str(exc)`` leak).
            self._respond_with_error(resp, exc, "get_plugins")
        return resp
