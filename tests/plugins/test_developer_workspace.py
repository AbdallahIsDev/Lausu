"""Workspace resolution and seeding for the bundled developer plugin tree.

A checkout runs straight out of ``tools/internal_plugins``. A packaged build
ships that tree read-only inside the binary, so the first developer-mode
unlock seeds a writable per-user copy and every runtime write goes there.
These tests pin both shapes and the rule that local state never travels with
the shipped source.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from voice_typer.server.plugins import workspace


def _write_source(root: Path) -> Path:
    """A miniature plugin tree with source AND local runtime state."""
    source = root / "tools" / "internal_plugins"
    plugin = source / "acme_stt"
    plugin.mkdir(parents=True)
    (plugin / "plugin.py").write_text("PLUGIN = True\n", encoding="utf-8")
    (plugin / "plugin.json").write_text('{"id": "acme_stt"}', encoding="utf-8")
    (plugin / "run.js").write_text("// daemon\n", encoding="utf-8")
    # Runtime state that must never be copied into the workspace.
    (source / workspace.MARKER_NAME).write_text("", encoding="utf-8")
    (plugin / "config.json").write_text('{"token": "local"}', encoding="utf-8")
    (plugin / "settings.json").write_text('{"visible": false}', encoding="utf-8")
    (plugin / "last_error.json").write_text('{"error": "local"}', encoding="utf-8")
    (plugin / "STOP").write_text("", encoding="utf-8")
    (plugin / "debug").mkdir()
    (plugin / "debug" / "daemon.err.log").write_text("local log", encoding="utf-8")
    (plugin / "generated").mkdir()
    (plugin / "generated" / "config.js").write_text("token", encoding="utf-8")
    (plugin / "__pycache__").mkdir()
    (plugin / "__pycache__" / "plugin.cpython-312.pyc").write_bytes(b"\0")
    return source


class TestResolvePluginsDir:
    def test_env_override_wins_when_it_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "explicit"
        target.mkdir()
        monkeypatch.setenv(workspace.ENV_FLAG, str(target))
        assert workspace.resolve_plugins_dir() == target

    def test_missing_override_is_no_workspace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(workspace.ENV_FLAG, str(tmp_path / "absent"))
        assert workspace.resolve_plugins_dir() is None

    def test_frozen_install_never_falls_back_to_the_read_only_bundle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Discovery must not list plugins whose settings cannot be written."""
        monkeypatch.delenv(workspace.ENV_FLAG, raising=False)
        monkeypatch.setattr(workspace, "_is_frozen", lambda: True)
        monkeypatch.setattr(workspace, "_bundle_root", lambda: tmp_path)
        monkeypatch.setattr(workspace, "user_plugins_dir", lambda: tmp_path / "absent")
        (tmp_path / "tools" / "internal_plugins").mkdir(parents=True)
        assert workspace.resolve_plugins_dir() is None

    def test_frozen_install_uses_the_seeded_copy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(workspace.ENV_FLAG, raising=False)
        monkeypatch.setattr(workspace, "_is_frozen", lambda: True)
        seeded = tmp_path / "seeded"
        seeded.mkdir()
        monkeypatch.setattr(workspace, "user_plugins_dir", lambda: seeded)
        assert workspace.resolve_plugins_dir() == seeded


class TestSeedWorkspace:
    def test_copies_source_and_writes_the_marker(self, tmp_path: Path) -> None:
        source = _write_source(tmp_path / "build")
        destination = tmp_path / "user" / "tools" / "internal_plugins"
        result = workspace.seed_workspace(source, destination)
        assert result == destination
        assert (destination / "acme_stt" / "plugin.py").is_file()
        assert (destination / "acme_stt" / "run.js").is_file()
        assert (destination / workspace.MARKER_NAME).is_file()

    def test_never_copies_local_runtime_state(self, tmp_path: Path) -> None:
        source = _write_source(tmp_path / "build")
        destination = tmp_path / "user"
        workspace.seed_workspace(source, destination)
        assert not (destination / "acme_stt" / "config.json").exists()
        assert not (destination / "acme_stt" / "settings.json").exists()
        assert not (destination / "acme_stt" / "last_error.json").exists()
        assert not (destination / "acme_stt" / "STOP").exists()
        assert not (destination / "acme_stt" / "debug").exists()
        assert not (destination / "acme_stt" / "generated").exists()
        assert not list(destination.rglob("*.pyc"))

    def test_keeps_local_state_already_in_the_workspace(self, tmp_path: Path) -> None:
        source = _write_source(tmp_path / "build")
        destination = tmp_path / "user"
        (destination / "acme_stt").mkdir(parents=True)
        (destination / "acme_stt" / "settings.json").write_text('{"visible": true}', encoding="utf-8")
        workspace.seed_workspace(source, destination)
        assert (destination / "acme_stt" / "settings.json").read_text(encoding="utf-8") == ('{"visible": true}')


class TestEnsureDeveloperWorkspace:
    def test_checkout_returns_the_tracked_workspace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        tracked = tmp_path / "tools" / "internal_plugins"
        tracked.mkdir(parents=True)
        monkeypatch.setattr(workspace, "_is_frozen", lambda: False)
        monkeypatch.setattr(workspace, "bundled_plugins_dir", lambda: tracked)
        assert workspace.ensure_developer_workspace() == tracked

    def test_frozen_build_seeds_the_per_user_copy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = _write_source(tmp_path / "build")
        seeded = tmp_path / "config" / "developer_plugins" / "tools" / "internal_plugins"
        monkeypatch.setattr(workspace, "_is_frozen", lambda: True)
        monkeypatch.setattr(workspace, "bundled_plugins_dir", lambda: source)
        monkeypatch.setattr(workspace, "user_plugins_dir", lambda: seeded)
        result = workspace.ensure_developer_workspace()
        assert result == seeded
        assert (seeded / workspace.MARKER_NAME).is_file()
        assert (seeded / "acme_stt" / "plugin.py").is_file()

    def test_missing_bundled_source_is_reported_not_crashed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(workspace, "_is_frozen", lambda: True)
        monkeypatch.setattr(workspace, "bundled_plugins_dir", lambda: None)
        assert workspace.ensure_developer_workspace() is None

    def test_repeated_seeds_are_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source = _write_source(tmp_path / "build")
        seeded = tmp_path / "user"
        monkeypatch.setattr(workspace, "_is_frozen", lambda: True)
        monkeypatch.setattr(workspace, "bundled_plugins_dir", lambda: source)
        monkeypatch.setattr(workspace, "user_plugins_dir", lambda: seeded)
        workspace.ensure_developer_workspace()
        (seeded / "acme_stt" / "settings.json").write_text('{"visible": false}', encoding="utf-8")
        workspace.ensure_developer_workspace()
        assert (seeded / "acme_stt" / "settings.json").read_text(encoding="utf-8") == ('{"visible": false}')


class TestPluginImportRoot:
    def test_root_is_the_parent_of_the_tools_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        plugins = tmp_path / "root" / "tools" / "internal_plugins"
        plugins.mkdir(parents=True)
        monkeypatch.setenv(workspace.ENV_FLAG, str(plugins))
        assert workspace.plugin_import_root() == tmp_path / "root"

    def test_no_workspace_means_no_import_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(workspace.ENV_FLAG, str(tmp_path / "absent"))
        assert workspace.plugin_import_root() is None
