"""`lausu` terminal entry starts production, never the dev env (E6)."""

from __future__ import annotations

from pathlib import Path

import voice_typer.server.cli as cli


class TestFindProductionBinary:
    def test_prefers_installed_over_local_build(self, monkeypatch, tmp_path):
        installed = tmp_path / "lausu-tauri.exe"
        installed.write_bytes(b"x")
        monkeypatch.setattr(
            "voice_typer.server.autostart.tauri_spawn._tauri_binary",
            lambda: str(installed),
        )
        assert cli.find_production_binary() == str(installed)

    def test_falls_back_to_local_target_build(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "voice_typer.server.autostart.tauri_spawn._tauri_binary",
            lambda: None,
        )
        fake = tmp_path / "lausu-tauri.exe"
        fake.write_bytes(b"x")
        monkeypatch.setattr(cli, "_LOCAL_TARGET_BINARIES", (fake,))
        assert cli.find_production_binary() == str(fake)

    def test_none_when_nothing_installed(self, monkeypatch):
        monkeypatch.setattr(
            "voice_typer.server.autostart.tauri_spawn._tauri_binary",
            lambda: None,
        )
        monkeypatch.setattr(cli, "_LOCAL_TARGET_BINARIES", ())
        assert cli.find_production_binary() is None


class TestIsLocalBuild:
    def test_target_debug_path_is_local(self):
        local = Path(cli._REPO_ROOT) / "src-tauri" / "target" / "debug" / cli._host_binary_name()
        assert cli._is_local_build(str(local)) is True

    def test_program_files_is_not_local(self):
        assert cli._is_local_build(r"C:\Program Files\App\lausu-tauri.exe") is False


class TestMainRouting:
    def test_default_routes_to_production_not_dev(self, monkeypatch):
        called = {}

        def _prod(hidden=False):
            called["prod"] = hidden
            return 0

        def _dev():
            called["dev"] = True
            return 0

        monkeypatch.setattr(cli, "launch_production", _prod)
        monkeypatch.setattr(cli, "launch_dev", _dev)
        assert cli.main([]) == 0
        assert "prod" in called
        assert "dev" not in called

    def test_dev_flag_is_explicit(self, monkeypatch):
        called = {}

        def _prod(hidden=False):
            called["prod"] = hidden
            return 0

        def _dev():
            called["dev"] = True
            return 0

        monkeypatch.setattr(cli, "launch_production", _prod)
        monkeypatch.setattr(cli, "launch_dev", _dev)
        assert cli.main(["--dev"]) == 0
        assert "dev" in called
        assert "prod" not in called

    def test_missing_binary_exits_one(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "find_production_binary", lambda: None)
        monkeypatch.setattr(
            "voice_typer.server.autostart.tauri_spawn._spawn_tauri_host",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not spawn")),
        )
        assert cli.launch_production() == 1
        err = capsys.readouterr().err
        assert "Production app binary not found" in err
        assert "lausu --dev" in err


class TestPackageEntryPoint:
    def test_pyproject_lausu_points_at_cli_not_ipc_server(self):
        text = (Path(cli._REPO_ROOT) / "pyproject.toml").read_text(encoding="utf-8")
        assert 'lausu = "voice_typer.server.cli:main"' in text
        assert 'lausu = "voice_typer.server.ipc_server:main"' not in text
