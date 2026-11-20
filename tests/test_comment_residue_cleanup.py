"""Guard the comment-residue cleanup in the touched source files.

Comment-only cleanup has no runtime behavior to assert, so these are focused
source checks: they pin that the dead markers, task ID and truncated comment
fragments stay gone. The AB-52 docstring contract is pinned separately in
``tests/test_hotkeys.py``.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_STATUS = _ROOT / "voice_typer/client/src/renderer/src/lib/dictationStatus.ts"
_FACTORY = _ROOT / "voice_typer/server/hotkeys/factory.py"


def test_dictation_status_has_no_hmr_markers():
    src = _STATUS.read_text(encoding="utf-8")
    assert "hmr" not in src.lower()


def test_factory_docstring_states_the_selection_order():
    from voice_typer.server.hotkeys.factory import create_hotkey_backend

    flat = " ".join((create_hotkey_backend.__doc__ or "").lower().split())
    for backend in ("native", "mouse", "windows", "wayland", "pynput"):
        assert backend in flat, f"factory docstring omits {backend}"
    assert flat.index("native") < flat.index("windows") < flat.index("wayland") < flat.index("pynput")


def test_factory_has_no_task_id_or_hmr_residue():
    src = _FACTORY.read_text(encoding="utf-8")
    assert "PLAT-WAYLAND" not in src
    assert "hmr" not in src.lower()


def test_factory_has_no_truncated_comment_fragments():
    src = _FACTORY.read_text(encoding="utf-8")
    for fragment in (
        "# try the native subprocess backend first. It supports",
        "# Wrap the native backend so it satisfies the HotkeyBackend\n",
        "# pass ``role`` through so the adapter can propagate\n",
        "# this is the polling fallback. It's",
        "# Wayland compositors do NOT expose a standard global-hotkey\n",
        "# Caps Lock on Wayland CANNOT be suppressed, ``WaylandHotkey``\n",
    ):
        assert fragment not in src, f"truncated comment left behind: {fragment!r}"
