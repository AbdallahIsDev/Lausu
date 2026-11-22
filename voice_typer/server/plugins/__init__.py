"""Plugin discovery: see :mod:`voice_typer.server.plugins.registry`.

Shared settings are NOT here: they are canonical fields in the main app
config, projected into plugin daemons by
:mod:`voice_typer.server.plugins.shared_settings`.
"""

from voice_typer.server.plugins.registry import (
    PluginInfo,
    discover,
    get_plugin,
    plugins_dir,
)

__all__ = ["PluginInfo", "discover", "get_plugin", "plugins_dir"]
