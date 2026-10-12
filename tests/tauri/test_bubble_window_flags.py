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
    """Every show must harden the chrome: hook (mouse path) + one-shot
    gutting (Alt+Space keyboard corner). No subclassing may remain."""
    source = (PROJECT_ROOT / "src-tauri" / "src" / "commands" / "bubble" / "window.rs").read_text(encoding="utf-8")
    assert "harden_bubble_chrome(&window)" in source
    assert "gut_bubble_system_menu" in source
    assert "ensure_bubble_msg_hook" in source
    assert "DeleteMenu" in source
    assert "SetWindowsHookExW" in source
    assert "WH_GETMESSAGE" in source
    assert "WM_NULL" in source
    assert "WM_RBUTTONDOWN" in source
    # Dead layers: the style strip lost a race to tao's flag flips,
    # and the wndproc subclass both leaked clicks in the gap and once
    # deadlocked the UI. Neither may come back.
    assert "strip_bubble_system_menu" not in source
    assert "swallow_bubble_caption_clicks" not in source
    assert "GWLP_WNDPROC" not in source
    assert "CallWindowProcW" not in source
    assert "SetWindowLongPtrW" not in source
    bootstrap = (PROJECT_ROOT / "src-tauri" / "src" / "window_bootstrap.rs").read_text(encoding="utf-8")
    assert "harden_bubble_on_setup" in bootstrap


def test_system_menu_strip_covers_mutation_paths():
    """The hook registration must run on show, hide, resize, and
    geometry events too, never on show alone."""
    window_rs = (PROJECT_ROOT / "src-tauri" / "src" / "commands" / "bubble" / "window.rs").read_text(encoding="utf-8")
    assert window_rs.count("harden_bubble_chrome(&") >= 2
    commands_rs = (PROJECT_ROOT / "src-tauri" / "src" / "commands" / "bubble" / "commands.rs").read_text(
        encoding="utf-8"
    )
    assert "harden_bubble_chrome" in commands_rs
    events_rs = (PROJECT_ROOT / "src-tauri" / "src" / "window_events.rs").read_text(encoding="utf-8")
    assert "harden_bubble_chrome" in events_rs
    assert "ensure_bubble_msg_hook" in events_rs
    # The geometry handler runs ON the main thread; the hook attach
    # is synchronous there while the rest hops off-thread.
    assert "thread::spawn" in events_rs
