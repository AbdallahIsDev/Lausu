"""Dev-console launcher (Dev shortcut + no-binary fallback)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from voice_typer.server.autostart import dev_console


def test_client_dir_has_package_json():
    assert (dev_console.client_dir() / "package.json").is_file()


def test_launch_dev_console_windows_spawns_cmd(monkeypatch):
    monkeypatch.setattr(dev_console.sys, "platform", "win32")
    popen = MagicMock()
    with patch.object(dev_console.subprocess, "Popen", popen):
        rc = dev_console.launch_dev_console("dev")
    assert rc == 0
    args = popen.call_args[0][0]
    assert args[0].endswith("cmd.exe")
    assert args[1] == "/k"
    assert args[2:5] == ["npm", "run", "dev"]
    assert popen.call_args.kwargs.get("creationflags") == dev_console.subprocess.CREATE_NEW_CONSOLE


def test_launch_dev_console_missing_client(monkeypatch, tmp_path):
    monkeypatch.setattr(dev_console, "client_dir", lambda: tmp_path)
    assert dev_console.launch_dev_console() == 1


def test_launch_handles_dev_flag():
    import inspect

    from voice_typer.server import autostart_launcher as al

    src = inspect.getsource(al.launch)
    assert '"--dev"' in src
    assert "launch_dev_console" in src
