"""Plugin discovery + the ``get_plugins`` IPC surface.

The shipped app has no plugin workspace, so discovery must degrade to an
empty list rather than an error: that is the normal state for every user
who does not have a plugin installed. These tests pin that fail-safe
behaviour, the manifest parsing rules, and the ``active_plugin`` contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from voice_typer.server import internal_plugin_hook as hook
from voice_typer.server.config_validators import IPC_CONFIG_ALLOWLIST
from voice_typer.server.ipc.registry import _COMMAND_REGISTRY, _READONLY_COMMANDS
from voice_typer.server.plugins import discover, get_plugin, registry


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "internal_plugins"
    root.mkdir()
    monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(root))
    return root


def _write_manifest(directory: Path, **overrides: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "id": "acme_stt",
        "name": "Acme STT",
        "vendor": "Acme",
        "icon": "acme",
        "description": "A test plugin.",
        "settings": [{"key": "visible", "type": "bool", "label": "Show window", "default": True}],
    }
    manifest.update(overrides)
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


class TestDiscovery:
    def test_no_workspace_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A shipped build has no plugin directory and must not error."""
        monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(tmp_path / "absent"))
        assert discover() == []

    def test_empty_workspace_returns_empty(self, workspace: Path) -> None:
        assert discover() == []

    def test_manifest_is_discovered(self, workspace: Path) -> None:
        _write_manifest(workspace / "acme_stt")
        found = discover()
        assert [p.id for p in found] == ["acme_stt"]
        assert found[0].name == "Acme STT"
        assert found[0].vendor == "Acme"
        assert [s.key for s in found[0].settings] == ["visible"]

    def test_broken_manifest_does_not_hide_the_others(self, workspace: Path) -> None:
        _write_manifest(workspace / "acme_stt")
        (workspace / "broken").mkdir()
        (workspace / "broken" / "plugin.json").write_text("{not json", encoding="utf-8")
        assert [p.id for p in discover()] == ["acme_stt"]

    @pytest.mark.parametrize(
        "overrides",
        [
            {"id": "Bad Id"},
            {"id": ""},
            {"name": ""},
        ],
        ids=["bad-id", "empty-id", "empty-name"],
    )
    def test_invalid_manifests_are_skipped(self, workspace: Path, overrides: dict[str, object]) -> None:
        _write_manifest(workspace / "acme_stt", **overrides)
        assert discover() == []

    def test_settings_with_unknown_type_are_dropped(self, workspace: Path) -> None:
        _write_manifest(
            workspace / "acme_stt",
            settings=[
                {"key": "ok", "type": "bool", "label": "Fine"},
                {"key": "bad", "type": "file_path", "label": "Nope"},
                "not an object",
            ],
        )
        assert [s.key for s in discover()[0].settings] == ["ok"]

    def test_dot_directories_are_ignored(self, workspace: Path) -> None:
        _write_manifest(workspace / ".hidden")
        assert discover() == []

    def test_get_plugin_finds_by_id(self, workspace: Path) -> None:
        _write_manifest(workspace / "acme_stt")
        assert get_plugin("acme_stt") is not None
        assert get_plugin("absent") is None

    def test_sorted_by_display_name(self, workspace: Path) -> None:
        _write_manifest(workspace / "z_plugin", name="Alpha")
        _write_manifest(workspace / "a_plugin", name="Zulu")
        assert [p.name for p in discover()] == ["Alpha", "Zulu"]


class TestActivePluginFlag:
    def test_active_flag_follows_config(self, workspace: Path) -> None:
        _write_manifest(workspace / "acme_stt")
        payload = discover()[0].to_dict(active=True)
        assert payload["active"] is True

    def test_inactive_by_default(self, workspace: Path) -> None:
        _write_manifest(workspace / "acme_stt")
        assert discover()[0].to_dict()["active"] is False


class TestActivePluginConfig:
    def test_field_is_in_the_allowlist(self) -> None:
        assert "active_plugin" in IPC_CONFIG_ALLOWLIST

    def test_default_is_empty(self) -> None:
        from voice_typer.server.config import Config

        assert Config().active_plugin == ""

    @pytest.mark.parametrize("value", ["", "google_stt", "ok-1_2"])
    def test_accepts_slugs(self, value: str) -> None:
        _, validate = IPC_CONFIG_ALLOWLIST["active_plugin"]
        assert validate(value) is None

    @pytest.mark.parametrize("value", ["Bad ID", "a" * 65, "semi;colon", 5, None])
    def test_rejects_anything_else(self, value: object) -> None:
        _, validate = IPC_CONFIG_ALLOWLIST["active_plugin"]
        assert validate(value) is not None


class TestPluginGate:
    """The gate decides who owns dictation; it must fail closed everywhere."""

    def _app(self, active: str) -> object:
        class _Config:
            active_plugin = active

        class _App:
            config = _Config()

        return _App()

    def test_local_model_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No selection means the local model, even with the env flag on."""
        monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
        assert hook.requested_plugin_id(self._app("")) == ""
        assert hook.plugins_enabled(self._app("")) is False

    def test_no_app_means_local_model(self) -> None:
        assert hook.requested_plugin_id(None) == ""
        assert hook.plugins_enabled(None) is False

    def test_app_without_config_means_local_model(self) -> None:
        assert hook.requested_plugin_id(object()) == ""
        assert hook.plugins_enabled(object()) is False

    def test_env_flag_still_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A selected plugin is not enough on its own - the gate still rules."""
        monkeypatch.delenv("VOICE_TYPER_INTERNAL_PLUGINS", raising=False)
        assert hook.plugins_enabled(self._app("google_stt")) is False

    def test_frozen_builds_never_run_a_plugin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert hook.plugins_enabled(self._app("google_stt")) is False


class TestGetPluginsCommand:
    def test_registered_and_classified_readonly(self) -> None:
        assert _COMMAND_REGISTRY["get_plugins"] == "_handle_get_plugins"
        assert "get_plugins" in _READONLY_COMMANDS

    def test_handler_shape(self) -> None:
        from voice_typer.server.handlers.plugin_handlers import PluginHandlersMixin

        assert hasattr(PluginHandlersMixin, "_handle_get_plugins")

    def test_discovery_never_imports_the_plugin_package(self) -> None:
        """Discovery reads manifests only; the plugin code stays untouched."""
        source = Path(registry.__file__).read_text(encoding="utf-8")
        assert "importlib" not in source


class TestGetPluginsEndToEnd:
    """The command as the renderer actually receives it."""

    def test_response_shape(self, workspace: Path) -> None:
        from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

        _write_manifest(workspace / "acme_stt")
        ipc, _app, _service = make_ipc_server_with_fakes()
        resp = ipc._dispatch({"type": "get_plugins"})
        assert resp is not None
        assert resp["type"] == "plugins"
        payload = resp["data"]
        # Object envelope, not a bare list: the nav needs `available` even
        # when the plugin array is empty.
        assert isinstance(payload, dict)
        assert payload["available"] is True
        assert payload["plugins"][0]["id"] == "acme_stt"
        # Nothing selected -> nothing is active.
        assert payload["plugins"][0]["active"] is False

    def test_no_plugins_is_an_empty_array_not_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A build with the surface available but nothing installed."""
        from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

        workspace = tmp_path / "internal_plugins"
        workspace.mkdir()
        monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(workspace))
        ipc, _app, _service = make_ipc_server_with_fakes()
        resp = ipc._dispatch({"type": "get_plugins"})
        assert resp is not None
        assert resp["data"]["plugins"] == []
        assert resp["data"]["available"] is True

    def test_hidden_install_answers_available_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A shipped install reports available=False with an empty list."""
        from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

        monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(tmp_path / "absent"))
        monkeypatch.delenv("VOICE_TYPER_INTERNAL_PLUGINS", raising=False)
        ipc, _app, _service = make_ipc_server_with_fakes()
        resp = ipc._dispatch({"type": "get_plugins"})
        assert resp is not None
        assert resp["data"] == {"available": False, "plugins": []}


class TestPluginsUiVisibility:
    """The Plugins nav is developer-only: hidden from every shipped build."""

    def test_owner_workspace_exposes_the_surface(self, workspace: Path) -> None:
        """A developer checkout (which HAS the workspace) exposes the surface.

        The workspace is created here rather than assumed present: it is
        gitignored, so a CI checkout never has it — that is exactly what
        ``test_workspace_is_never_packaged`` pins. Asserting against the
        ambient repo made this pass locally and fail on every CI leg.
        """
        assert workspace.is_dir()
        assert hook.internal_surface_enabled() is True

    def test_missing_workspace_hides_it(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(tmp_path / "absent"))
        monkeypatch.delenv("VOICE_TYPER_INTERNAL_PLUGINS", raising=False)
        assert hook.internal_surface_enabled() is False

    def test_frozen_build_never_exposes_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
        assert hook.internal_surface_enabled() is False

    def test_env_flag_alone_exposes_it(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(tmp_path / "absent"))
        monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
        assert hook.internal_surface_enabled() is True

    def test_visibility_ignores_the_active_plugin(self, workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The UI must be reachable BEFORE a plugin is ever selected."""
        assert workspace.is_dir()
        monkeypatch.setattr(hook, "requested_plugin_id", lambda app=None: "")
        assert hook.internal_surface_enabled() is True

    def test_workspace_is_never_packaged(self) -> None:
        """The discriminator is a gitignored path, so it cannot ship."""
        ignore = Path(__file__).resolve().parents[2] / ".gitignore"
        assert "tools/internal_plugins/" in ignore.read_text(encoding="utf-8")
