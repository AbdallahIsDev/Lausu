"""Paste-delivery-target contract: Option A "typewriter model".

User decision 2026-10-17 (docs/voice_typer_recording_edge_cases.md §3,
AGENTS.md C-PASTE-1): text is pasted into whatever window is foreground
at keystroke-dispatch time. The app must never capture the dictation
window at stop or refocus a remembered window at paste time.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from voice_typer.server import clipboard as clip_mod

from tests.fixtures.clipboard_helpers import make_clipboard_manager

_SERVER_DIR = Path(__file__).resolve().parents[1] / "voice_typer" / "server"

# APIs that would yank focus back to a remembered window (Option B).
_FOCUS_STEAL_TOKENS = (
    "SetForegroundWindow",
    "SetActiveWindow",
    "SetFocus(",
    "BringWindowToTop",
)


def _clipboard_sources() -> list[str]:
    return [p.read_text(encoding="utf-8") for p in (_SERVER_DIR / "clipboard").rglob("*.py")]


def _recording_lifecycle_sources() -> list[str]:
    files = sorted(_SERVER_DIR.glob("recording_lifecycle*.py"))
    files.append(_SERVER_DIR / "recording_controller.py")
    files.extend(sorted((_SERVER_DIR / "recording").rglob("*.py")))
    return [p.read_text(encoding="utf-8") for p in files if p.exists()]


class TestNoFocusStealing:
    def test_clipboard_package_never_restores_focus(self):
        for src in _clipboard_sources():
            for token in _FOCUS_STEAL_TOKENS:
                assert token not in src, f"focus-steal token {token!r} in clipboard package (Option B forbidden)"

    def test_recording_lifecycle_never_captures_or_steals_focus(self):
        for src in _recording_lifecycle_sources():
            for token in (*_FOCUS_STEAL_TOKENS, "GetForegroundWindow"):
                assert token not in src, f"{token!r} in recording lifecycle (no target-window memory at stop)"


class TestDispatchTimeCapture:
    def test_dispatch_captures_target_handle_at_dispatch_time(self):
        """The foreground handle is read inside the paste dispatch, not cached earlier."""
        src = (_SERVER_DIR / "clipboard" / "manager" / "_paste.py").read_text(encoding="utf-8")
        dispatch_body = src.split("def _attempt_paste_dispatch", 1)[1]
        assert "self._capture_target_handle()" in dispatch_body

    def test_capture_target_handle_reads_fresh_each_call(self):
        cm = make_clipboard_manager()
        clip_mod_is_windows = clip_mod.is_windows
        clip_mod_is_macos = clip_mod.is_macos
        try:
            clip_mod.is_windows = lambda: False
            clip_mod.is_macos = lambda: True
            cm._get_frontmost_pid_macos = MagicMock(side_effect=[111, 222])
            assert cm._capture_target_handle() == (0, 111)
            assert cm._capture_target_handle() == (0, 222)
        finally:
            clip_mod.is_windows = clip_mod_is_windows
            clip_mod.is_macos = clip_mod_is_macos
