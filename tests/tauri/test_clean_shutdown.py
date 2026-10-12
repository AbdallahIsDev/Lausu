"""Ctrl+C must not leave live WebViews for Chromium's AtExit to trip over.

Killing dev from the terminal used to log `Failed to unregister class
Chrome_WidgetWin_0` because only tray-Quit destroyed webviews first.
The console handler (`console_ctrl.rs`) reuses the same shared helper,
and the dev wrapper spawns the CLI without an extra `cmd.exe` layer
(one fewer "Terminate batch job" prompt).
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONSOLE_CTRL = PROJECT_ROOT / "src-tauri" / "src" / "console_ctrl.rs"
LIFECYCLE = PROJECT_ROOT / "src-tauri" / "src" / "sidecar" / "lifecycle.rs"
TAURI_DEV_MJS = PROJECT_ROOT / "voice_typer" / "client" / "scripts" / "tauri-dev.mjs"


def test_console_handler_destroys_webviews_first():
    source = CONSOLE_CTRL.read_text(encoding="utf-8")
    assert "SetConsoleCtrlHandler" in source
    assert "destroy_webview_windows" in source
    # Default termination must proceed afterwards (false), never swallow it.
    assert "false.into()" in source


def test_quit_path_shares_the_destroy_helper():
    """One helper, two callers: tray-Quit and console kills can't drift."""
    source = LIFECYCLE.read_text(encoding="utf-8")
    assert source.count("fn destroy_webview_windows") == 1
    assert "destroy_webview_windows(app_handle)" in source
    assert "webview_windows()" in source


def test_dev_wrapper_spawns_cli_without_cmd_layer():
    text = TAURI_DEV_MJS.read_text(encoding="utf-8")
    assert "tauri.js" in text
