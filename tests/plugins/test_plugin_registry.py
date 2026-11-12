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

    def test_selection_is_enough_when_the_workspace_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A selected plugin owns dictation once the workspace is there.

        The gate used to ALSO require ``VOICE_TYPER_INTERNAL_PLUGINS=1``, and
        nothing in the repo ever set it: activating a plugin in the Plugins
        page silently kept the local model on every hotkey press, with no
        visible reason. The workspace (tracked source, never packaged) plus
        the plugin's own PLUGINS_ENABLED marker are the deliberate opt-ins,
        and a frozen build still never runs a plugin.
        """
        monkeypatch.delenv("VOICE_TYPER_INTERNAL_PLUGINS", raising=False)
        monkeypatch.setattr(hook, "internal_surface_enabled", lambda: True)
        monkeypatch.setattr(
            hook,
            "_plugin",
            lambda app=None: type(
                "_P", (), {"plugins_enabled": staticmethod(lambda: True)}
            )(),
        )
        assert hook.plugins_enabled(self._app("google_stt")) is True

    def test_no_workspace_still_means_local_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without the workspace the local model always keeps dictation."""
        monkeypatch.setattr(hook, "internal_surface_enabled", lambda: False)
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


class TestSetPluginSettingCommand:
    """The one plugin-setting write, end to end through the dispatcher."""

    def test_registered_as_a_mutator_not_a_read(self) -> None:
        assert _COMMAND_REGISTRY["set_plugin_setting"] == "_handle_set_plugin_setting"
        assert "set_plugin_setting" not in _READONLY_COMMANDS

    def test_persists_a_declared_setting_and_reads_it_back(self, workspace: Path) -> None:
        from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

        _write_manifest(workspace / "acme_stt")
        ipc, _app, _service = make_ipc_server_with_fakes()
        resp = ipc._dispatch(
            {
                "type": "set_plugin_setting",
                "data": {"plugin_id": "acme_stt", "key": "visible", "value": False},
            }
        )
        assert resp is not None
        assert resp["type"] == "plugin_setting"
        assert resp["data"] == {"plugin_id": "acme_stt", "key": "visible", "value": False}

        stored = json.loads((workspace / "acme_stt" / "settings.json").read_text(encoding="utf-8"))
        assert stored == {"visible": False}

        listing = ipc._dispatch({"type": "get_plugins"})
        assert listing is not None
        assert listing["data"]["plugins"][0]["values"] == {"visible": False}

    def test_rejects_an_undeclared_key_without_writing(self, workspace: Path) -> None:
        from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

        _write_manifest(workspace / "acme_stt")
        ipc, _app, _service = make_ipc_server_with_fakes()
        resp = ipc._dispatch(
            {
                "type": "set_plugin_setting",
                "data": {"plugin_id": "acme_stt", "key": "nope", "value": True},
            }
        )
        assert resp is not None
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.invalid_field"
        assert not (workspace / "acme_stt" / "settings.json").exists()


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

        The workspace is created here rather than assumed present: a shipped
        build never packages it — that is exactly what
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

    def test_workspace_source_is_tracked_but_runtime_is_ignored(self) -> None:
        """The source is visible; only local runtime state is gitignored."""
        root = Path(__file__).resolve().parents[2]
        ignored = {
            line.strip()
            for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        assert "tools/internal_plugins/" not in ignored
        nested = (root / "tools" / "internal_plugins" / ".gitignore").read_text(
            encoding="utf-8"
        )
        assert "PLUGINS_ENABLED" in nested
        assert "config.json" in nested


class TestPluginModuleRouting:
    """The seam must pick the module the selected id names, never one fixed
    plugin: otherwise selecting a second plugin would silently drive the
    first plugin's page."""

    def _app(self, active: str) -> object:
        class _Config:
            active_plugin = active

        class _App:
            config = _Config()

        return _App()

    def test_module_table_covers_both_installed_plugins(self) -> None:
        assert hook.PLUGIN_MODULES["google_stt"] == "tools.internal_plugins.google_stt.plugin"
        assert hook.PLUGIN_MODULES["anthropic_stt"] == "tools.internal_plugins.anthropic_stt.plugin"

    def test_unknown_id_resolves_to_no_module(self) -> None:
        """A stale/uninstalled id must not import anything (fails closed)."""
        assert hook._plugin(self._app("not_installed")) is None
        assert hook.plugins_enabled(self._app("not_installed")) is False

    def test_install_resolves_the_selection_on_every_press(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Selection changes apply to the NEXT press, with no restart.

        The wrapper is installed once (when the developer-only surface
        exists) and must read ``active_plugin`` at press time; freezing the
        module at install time would make the Plugins toggle a no-op until
        the app relaunches.
        """
        import types

        monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
        calls: list[str] = []

        class _Session:
            def __init__(self, name: str) -> None:
                self.name = name
                self.active = False

            def toggle(self) -> None:
                calls.append(self.name)
                self.active = True

            def stop(self) -> None:
                calls.append(self.name + ":stop")
                self.active = False

            def cancel(self) -> bool:
                calls.append(self.name + ":cancel")
                was_active = self.active
                self.active = False
                return was_active

        def _stub(name: str) -> types.ModuleType:
            module = types.ModuleType(f"tools.internal_plugins.{name}.plugin")
            module.plugins_enabled = lambda: True
            module.attach = lambda app: _Session(name)
            monkeypatch.setitem(sys.modules, module.__name__, module)
            monkeypatch.setitem(hook.PLUGIN_MODULES, name, module.__name__)
            return module

        _stub("alpha_stt")
        _stub("beta_stt")

        class _Config:
            active_plugin = "beta_stt"

        class _App:
            config = _Config
            _internal_plugin_wrapped = False

            def toggle_dictation(self) -> None:
                calls.append("local:toggle")

            def _stop_dictation(self) -> None:
                calls.append("local:stop")

            def _cancel_dictation(self) -> None:
                calls.append("local:cancel")

        app = _App()
        assert hook.install(app) is True
        # Already wrapped: a second install must not nest the wrappers.
        assert hook.install(app) is False

        app.toggle_dictation()
        assert calls == ["beta_stt"]

        # Switching mid-recording cancels the old owner before starting the
        # newly selected plugin on the very next press.
        app.config.active_plugin = "alpha_stt"
        app.toggle_dictation()
        assert calls == ["beta_stt", "beta_stt:cancel", "alpha_stt"]

        # Stop routes to the session that owns the in-flight cycle.
        app._stop_dictation()
        assert calls[-1] == "alpha_stt:stop"

        # Clearing the selection restores the local model immediately.
        app.config.active_plugin = ""
        app.toggle_dictation()
        assert calls[-2:] == ["alpha_stt:stop", "local:toggle"]
