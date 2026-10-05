"""Plugin discovery: see :mod:`voice_typer.server.plugins.registry`."""

from voice_typer.server.plugins.registry import (
    PluginInfo,
    PluginSetting,
    discover,
    get_plugin,
    plugins_dir,
)

__all__ = ["PluginInfo", "PluginSetting", "discover", "get_plugin", "plugins_dir"]
