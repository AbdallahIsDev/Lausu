"""Shared plugin settings are canonical config and propagate immediately."""

from __future__ import annotations

import json
from pathlib import Path

from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes


def _workspace(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "internal_plugins"
    root.mkdir()
    monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(root))
    for name, plugin_id in (("anthropic_stt", "anthropic_stt"), ("google_stt", "google_stt")):
        d = root / name
        d.mkdir()
        (d / "plugin.json").write_text(
            json.dumps({"id": plugin_id, "name": name}), encoding="utf-8"
        )
        (d / "config.json").write_text(
            json.dumps({"profileDir": "/tmp/profile", "visible": True, "notify": True}),
            encoding="utf-8",
        )
    return root


def _stored(workspace: Path, name: str) -> dict:
    return json.loads((workspace / name / "config.json").read_text(encoding="utf-8"))


def _server_with_config(**config_values):
    """Real Config + a service fake that actually applies set_config values."""
    from voice_typer.server.config import Config

    ipc, app, service = make_ipc_server_with_fakes()
    app.config = Config(developer_mode=True, **config_values)

    def apply(values):
        for key, value in values.items():
            setattr(app.config, key, value)

    service.apply_config.side_effect = apply
    return ipc, app, service


class TestImmediatePropagation:
    def test_visibility_change_projects_to_every_plugin(self, tmp_path, monkeypatch):
        workspace = _workspace(tmp_path, monkeypatch)
        ipc, app, _service = _server_with_config()

        resp = ipc._dispatch({"type": "set_config", "data": {"plugin_visible": False}})
        assert resp is not None and resp["type"] == "ack"
        assert app.config.plugin_visible is False
        for name in ("anthropic_stt", "google_stt"):
            assert _stored(workspace, name)["visible"] is False
            # Daemon-owned keys survive the projection.
            assert _stored(workspace, name)["profileDir"] == "/tmp/profile"

    def test_notify_change_projects_to_every_plugin(self, tmp_path, monkeypatch):
        workspace = _workspace(tmp_path, monkeypatch)
        ipc, app, _service = _server_with_config()

        ipc._dispatch({"type": "set_config", "data": {"plugin_notify": False}})
        for name in ("anthropic_stt", "google_stt"):
            assert _stored(workspace, name)["notify"] is False

    def test_visibility_change_applies_to_the_running_browser(
        self, tmp_path, monkeypatch
    ):
        _workspace(tmp_path, monkeypatch)
        ipc, app, _service = _server_with_config(active_plugin="google_stt")

        calls: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            "tools.internal_plugins._common.bridge.chrome_profile.set_window_visible",
            lambda directory, visible, **kwargs: calls.append((directory, visible)),
        )

        ipc._dispatch({"type": "set_config", "data": {"plugin_visible": False}})

        # The apply runs on a daemon thread; wait for it without a fixed sleep.
        import time

        deadline = time.monotonic() + 2.0
        while not calls and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls and calls[0][1] is False
        assert "google_stt" in calls[0][0]

    def test_startup_projection_uses_canonical_config(self, tmp_path, monkeypatch):
        workspace = _workspace(tmp_path, monkeypatch)
        from voice_typer.server.plugins import shared_settings

        config = type("Cfg", (), {"plugin_visible": False, "plugin_notify": False})()
        shared_settings.sync_all(config)
        for name in ("anthropic_stt", "google_stt"):
            assert _stored(workspace, name)["visible"] is False
            assert _stored(workspace, name)["notify"] is False
