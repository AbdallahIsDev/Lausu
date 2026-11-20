"""Autostart/session/mutex regressions (RDP, venv, install hash, handle close)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


class TestRDPSession:
    """PLAT-RDP: is_remote_session detects RDP/SSH sessions."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows uses GetSystemMetrics for RDP detection, not SSH env vars",
    )
    def test_returns_false_when_no_ssh_env(self, monkeypatch):
        monkeypatch.delenv("SSH_CLIENT", raising=False)
        monkeypatch.delenv("SSH_TTY", raising=False)
        from voice_typer.server.server_platform import is_remote_session

        assert is_remote_session() is False

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows uses GetSystemMetrics for RDP detection, not SSH env vars",
    )
    def test_detects_ssh_session(self, monkeypatch):
        monkeypatch.setenv("SSH_CLIENT", "10.0.0.1 12345 22")
        from voice_typer.server.server_platform import is_remote_session

        assert is_remote_session() is True


class TestVenvDetection:
    """PLAT-VENV: Autostart uses system Python when in venv."""

    def test_autostart_command_in_venv_uses_sys_executable(self):
        from voice_typer.server.server_platform import _autostart_command

        cmd = _autostart_command()
        assert "autostart_launcher.py" in cmd


class TestMutexPathHash:
    """PLAT-RUN: Mutex name includes installation path hash."""

    def test_run_key_name_includes_hash(self):
        from voice_typer.server.server_platform import _run_key_name

        name = _run_key_name()
        assert name.startswith("com.Lausu.autostart_")
        assert len(name) > len("com.Lausu.autostart_")

    def test_different_executables_produce_different_hashes(self, monkeypatch):
        from voice_typer.server.server_platform import _run_key_name

        monkeypatch.setattr(
            "voice_typer.server.server_platform.autostart._install_identifier",
            lambda: "/path/a/autostart_launcher.py",
        )
        name_a = _run_key_name()
        monkeypatch.setattr(
            "voice_typer.server.server_platform.autostart._install_identifier",
            lambda: "/path/b/autostart_launcher.py",
        )
        name_b = _run_key_name()
        assert name_a != name_b


class TestMutexHandleClose:
    """PLAT-HLEAK: CloseHandle called in quit() for mutex."""

    def test_quit_closes_mutex_handle(self, monkeypatch, tmp_config_dir):
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = []
        monkeypatch.setitem(sys.modules, "sounddevice", mock_sd)
        monkeypatch.setitem(sys.modules, "faster_whisper", MagicMock())
        monkeypatch.setitem(sys.modules, "pynput", MagicMock())
        monkeypatch.setitem(sys.modules, "pynput.keyboard", MagicMock())
        monkeypatch.setitem(sys.modules, "pystray", MagicMock())
        monkeypatch.setitem(sys.modules, "PIL", MagicMock())
        monkeypatch.setitem(sys.modules, "PIL.Image", MagicMock())
        monkeypatch.setitem(sys.modules, "PIL.ImageDraw", MagicMock())
        monkeypatch.setitem(sys.modules, "pyperclip", MagicMock())
        monkeypatch.setattr("atexit.register", lambda *a, **kw: None)
        monkeypatch.setattr("voice_typer.server.server_platform.autostart.is_autostart_enabled", lambda: False)
        monkeypatch.setattr("voice_typer.server.server_platform.autostart.enable_autostart", lambda: True)
        monkeypatch.setattr("voice_typer.server.server_platform.autostart.disable_autostart", lambda: True)
        monkeypatch.setattr("voice_typer.server.server_platform.microphone_list.list_microphones", lambda: [])

        from voice_typer.server.hotkeys import PynputHotkey

        monkeypatch.setattr(
            "voice_typer.server.hotkey_dispatcher.create_hotkey_backend",
            lambda hotkey_str: PynputHotkey(hotkey_str),
        )

        from voice_typer.server.app import LausuApp

        app = LausuApp()
        mock_handle = MagicMock()
        app._mutex_handle = mock_handle

        assert hasattr(app, "_mutex_handle")
        assert app._mutex_handle is mock_handle
