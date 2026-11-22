"""A plugin switch must push the derived sidebar label with config_changed."""

from __future__ import annotations

import voice_typer.server.handlers.config_handlers as ch_mod
from voice_typer.server import internal_plugin_hook


def test_plugin_switch_pushes_active_plugin_name(ipc_server, monkeypatch):
    published: list[dict] = []
    monkeypatch.setattr(ch_mod.event_bus, "publish", published.append)
    monkeypatch.setattr(
        internal_plugin_hook,
        "plugin_display_name_for",
        lambda config: "Anthropic STT",
    )

    ipc_server._handle_set_config({"active_plugin": "anthropic_stt"}, {})

    events = [e for e in published if e.get("type") == "config_changed"]
    assert events, "config_changed must be published for a plugin switch"
    data = events[0]["data"]
    assert data["active_plugin"] == "anthropic_stt"
    assert data["active_plugin_name"] == "Anthropic STT", (
        "the sidebar reads active_plugin_name, which is computed only in "
        "get_config; a partial push without it leaves a stale caption"
    )


def test_clearing_plugin_switch_pushes_empty_name(ipc_server, monkeypatch):
    published: list[dict] = []
    monkeypatch.setattr(ch_mod.event_bus, "publish", published.append)
    monkeypatch.setattr(
        internal_plugin_hook,
        "plugin_display_name_for",
        lambda config: "",
    )

    ipc_server._handle_set_config({"active_plugin": ""}, {})

    data = [e for e in published if e.get("type") == "config_changed"][0]["data"]
    assert data["active_plugin"] == ""
    assert data["active_plugin_name"] == ""
