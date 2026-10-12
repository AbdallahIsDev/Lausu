"""Bubble window must stay caption-harmless: no system menu, no dblclick zoom.

The pill drags via an OS caption region, which on Windows summons the
system menu on right-click and toggles minimize/maximize on
double-click. The community fix (same as the accepted answer for this
exact Tauri question) is ``maximizable/minimizable/closable: false``
on the bubble block, in EVERY conf that defines one. This pins all of
them so a per-arch copy cannot drift back.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFS = sorted((PROJECT_ROOT / "src-tauri").glob("tauri*.conf.json"))

_BUBBLE_FLAGS = ("maximizable", "minimizable", "closable")


def _bubble_blocks():
    for conf in CONFS:
        data = json.loads(conf.read_text(encoding="utf-8"))
        for window in data.get("app", {}).get("windows", []):
            if window.get("label") == "bubble":
                yield conf.name, window


def test_every_bubble_block_disables_chrome():
    found = list(_bubble_blocks())
    assert found, "no bubble window block found in any tauri conf"
    for name, block in found:
        for flag in _BUBBLE_FLAGS:
            assert block.get(flag) is False, f"{name} bubble block must set {flag}=false (system menu / dblclick guard)"


def test_main_window_keeps_normal_chrome():
    """The flags are bubble-only; the main window stays a normal window."""
    data = json.loads((PROJECT_ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    main = next(w for w in data["app"]["windows"] if w.get("label") == "main")
    for flag in _BUBBLE_FLAGS:
        assert flag not in main, f"main window must not carry bubble flag {flag}"


def test_system_menu_strip_wired_in_show_path():
    """Every show must harden the chrome; the strip must target WS_SYSMENU."""
    source = (PROJECT_ROOT / "src-tauri" / "src" / "commands" / "bubble" / "window.rs").read_text(encoding="utf-8")
    assert "harden_bubble_chrome(&window)" in source
    assert "WS_SYSMENU" in source
    assert "strip_bubble_system_menu" in source
    assert "DeleteMenu" in source
    assert "GWLP_WNDPROC" in source
    assert "Chrome_RenderWidgetHostHWND" in source
    assert "WM_RBUTTONDOWN" in source
    bootstrap = (PROJECT_ROOT / "src-tauri" / "src" / "window_bootstrap.rs").read_text(encoding="utf-8")
    assert "harden_bubble_on_setup" in bootstrap


def test_system_menu_strip_covers_mutation_paths():
    """tao rewrites the style on flag flips, so the strip must run on
    hide, resize, and geometry events too, never on show alone."""
    window_rs = (PROJECT_ROOT / "src-tauri" / "src" / "commands" / "bubble" / "window.rs").read_text(encoding="utf-8")
    assert window_rs.count("harden_bubble_chrome(&") >= 2
    commands_rs = (PROJECT_ROOT / "src-tauri" / "src" / "commands" / "bubble" / "commands.rs").read_text(
        encoding="utf-8"
    )
    assert "harden_bubble_chrome" in commands_rs
    events_rs = (PROJECT_ROOT / "src-tauri" / "src" / "window_events.rs").read_text(encoding="utf-8")
    assert "harden_bubble_chrome" in events_rs
    # The geometry handler runs ON the main thread while hardening
    # blocks on main-thread roundtrips: it must hop off-thread or the
    # UI deadlocks on itself (frozen splash, "Not Responding").
    assert "thread::spawn" in events_rs
    # The swallow pre-checks liveness on the caller thread and only
    # dispatches when an install is actually needed, so steady-state
    # event calls never touch the main thread at all.
    assert "CallWindowProcW(*prev" not in window_rs
    # The chained proc must be copied out and the registry guard
    # dropped BEFORE the call: tao/Chromium send synchronously to
    # our other subclassed window, re-entering the proc on the same
    # thread, and calling out under a non-reentrant Mutex deadlocks
    # the UI (frozen splash, "Not Responding", ~0 CPU).
    assert "CallWindowProcW(Some(p)" in window_rs
    assert "IsWindow" in window_rs
