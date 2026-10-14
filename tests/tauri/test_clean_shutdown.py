"""Ctrl+C drives the tray-Quit teardown; key-listener orphans stay reaped.

Ctrl+C: killing dev from the terminal used to log `Failed to unregister
class Chrome_WidgetWin_0` (only tray-Quit destroyed webviews first) AND
hard-killed the sidecar mid-WAL-flush (the handler destroyed webviews
only, then returned false so the OS default `ExitProcess` cut off
`shutdown_sidecar_for_exit`). The handler now calls `on_quit_app`
itself (arm `shutting_down` + destroy webviews + `app.exit(0)` so
`RunEvent::Exit` → `on_host_exit` runs the budgeted flush) and returns
true so the teardown owns process exit. CLOSE/LOGOFF/SHUTDOWN keep the
best-effort shape (OS deadline, default termination proceeds).

Key-listener orphans (verdict, pinned below): host → sidecar →
`_spawn.py` Popen → native listener exe. The sidecar is assigned to the
host-wide Job Object (`KILL_ON_JOB_CLOSE`); grandchildren inherit that
membership unless a spawn breaks away. No production spawn passes
`CREATE_BREAKAWAY_FROM_JOB` / `DETACHED_PROCESS` /
`CREATE_NEW_PROCESS_GROUP`, `_spawn.py` keeps the listener's stdin as a
pipe whose EOF the C reader treats as parent-death (`exit(0)`), and the
Windows `kill_process_tree` reaps the whole tree (`taskkill /T`). So a
Task Manager host-kill closes the job (OS reaps sidecar + listener),
cooperative exit tree-kills, and an escaped listener still self-exits
on stdin EOF: no production change needed, verdict pinned by tests.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONSOLE_CTRL = PROJECT_ROOT / "src-tauri" / "src" / "console_ctrl.rs"
LIFECYCLE = PROJECT_ROOT / "src-tauri" / "src" / "sidecar" / "lifecycle.rs"
TAURI_DEV_MJS = PROJECT_ROOT / "voice_typer" / "client" / "scripts" / "tauri-dev.mjs"
JOB_WINDOWS = PROJECT_ROOT / "src-tauri" / "src" / "platform" / "process" / "windows.rs"
KILL_TREE_MOD = PROJECT_ROOT / "src-tauri" / "src" / "platform" / "process" / "mod.rs"
NATIVE_SPAWN = PROJECT_ROOT / "voice_typer" / "server" / "native_hotkeys" / "_spawn.py"
KEY_LISTENER_C = PROJECT_ROOT / "voice_typer" / "server" / "native" / "windows-key-listener.c"


def test_console_handler_destroys_webviews_first():
    source = CONSOLE_CTRL.read_text(encoding="utf-8")
    assert "SetConsoleCtrlHandler" in source
    assert "destroy_webview_windows" in source
    # Ctrl+C/Break must proceed via the cooperative teardown, NOT the
    # OS default termination (which hard-kills mid-WAL-flush).
    assert "on_quit_app(app)" in source
    assert "true.into()" in source
    # CLOSE/LOGOFF/SHUTDOWN keep the old best-effort shape: the OS
    # imposes a seconds-long deadline, so default termination proceeds.
    assert "false.into()" in source


def test_console_ctrl_c_does_not_hard_kill_mid_flush():
    """The Ctrl+C arm must reach `on_quit_app` BEFORE swallowing the signal."""
    source = CONSOLE_CTRL.read_text(encoding="utf-8")
    match_start = source.index("match ctrl_type")
    quit_call = source.index("on_quit_app(app)")
    # The swallow belongs to the Ctrl+C arm: search AFTER the quit call
    # (an earlier `true.into()` in `install` is the add-flag, not the
    # return value).
    swallow = source.index("true.into()", quit_call)
    assert match_start < quit_call < swallow, (
        "the Ctrl+C arm must call on_quit_app (arm shutting_down + destroy "
        "webviews + app.exit(0) so RunEvent::Exit runs the budgeted flush) "
        "before swallowing the OS default ExitProcess"
    )


def test_console_handler_does_not_reimplement_quit_teardown():
    """One ordered teardown: the handler calls `on_quit_app`, never a copy."""
    source = CONSOLE_CTRL.read_text(encoding="utf-8")
    assert source.count("on_quit_app(app)") == 1, (
        "console_ctrl must call the tray-Quit teardown exactly once; "
        "a second inline copy would drift from tray Quit"
    )


def test_quit_path_shares_the_destroy_helper():
    """One helper, two callers: tray-Quit and console kills can't drift."""
    source = LIFECYCLE.read_text(encoding="utf-8")
    assert source.count("fn destroy_webview_windows") == 1
    assert "destroy_webview_windows(app_handle)" in source
    assert "webview_windows()" in source


def test_dev_wrapper_spawns_cli_without_cmd_layer():
    text = TAURI_DEV_MJS.read_text(encoding="utf-8")
    assert "tauri.js" in text


def test_key_listener_cannot_break_away_from_host_job():
    """No spawn in the listener chain may escape the host Job Object."""
    for path in (JOB_WINDOWS, KILL_TREE_MOD, NATIVE_SPAWN, KEY_LISTENER_C):
        source = path.read_text(encoding="utf-8")
        for flag in (
            "CREATE_BREAKAWAY_FROM_JOB",
            "DETACHED_PROCESS",
            "CREATE_NEW_PROCESS_GROUP",
            "CREATE_BREAKAWAY",
        ):
            assert flag not in source, (
                f"{path.name} must not pass {flag}: a breakaway listener "
                "grandchild would survive a Task Manager host-kill"
            )


def test_key_listener_keeps_stdin_eof_self_exit():
    """The stdin-EOF backstop must survive: EOF == parent dead == exit."""
    spawn = NATIVE_SPAWN.read_text(encoding="utf-8")
    assert "stdin=subprocess.PIPE" in spawn
    assert "stdin=DEVNULL" not in spawn
    listener = KEY_LISTENER_C.read_text(encoding="utf-8")
    assert "stdin_reader_thread" in listener
    assert "exit(0)" in listener


def test_host_kill_reaps_listener_via_job_and_tree_kill():
    """Both reap layers must stay wired: job kill-on-close + tree kill."""
    job = JOB_WINDOWS.read_text(encoding="utf-8")
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in job
    assert "AssignProcessToJobObject" in job
    tree = KILL_TREE_MOD.read_text(encoding="utf-8")
    assert "taskkill" in tree
    assert "/T" in tree
