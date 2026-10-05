"""Dev-console launcher (Dev shortcut + no-binary fallback)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from voice_typer.server.autostart import dev_console


def test_client_dir_has_package_json():
    assert (dev_console.client_dir() / "package.json").is_file()


def test_launch_dev_console_windows_spawns_cmd(monkeypatch):
    monkeypatch.setattr(dev_console.sys, "platform", "win32")
    # ``launch_dev_console`` reads ``sys.platform`` through
    # ``platform_utils.is_windows()``, so faking win32 here takes the
    # Windows branch on POSIX too -- where CPython never defines the
    # Windows-only creation-flag constants (they live under
    # ``if _mswindows:`` in ``Lib/subprocess.py``). Inject the flag so the
    # branch is exercisable on every OS.
    sentinel = 0x00000010  # CREATE_NEW_CONSOLE
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", sentinel, raising=False)

    popen = MagicMock()
    with patch.object(dev_console.subprocess, "Popen", popen):
        rc = dev_console.launch_dev_console("dev")
    assert rc == 0
    args = popen.call_args[0][0]
    assert args[0].endswith("cmd.exe")
    assert args[1] == "/k"
    assert args[2:5] == ["npm", "run", "dev"]
    # A new console is the whole point: pythonw has no console of its own,
    # so the user needs one to see vite/tauri output and Ctrl+C the server.
    assert popen.call_args.kwargs.get("creationflags") == sentinel


def test_launch_dev_console_missing_client(monkeypatch, tmp_path):
    monkeypatch.setattr(dev_console, "client_dir", lambda: tmp_path)
    assert dev_console.launch_dev_console() == 1


def test_launch_handles_dev_flag():
    import inspect

    from voice_typer.server import autostart_launcher as al

    src = inspect.getsource(al.launch)
    assert '"--dev"' in src
    assert "launch_dev_console" in src
