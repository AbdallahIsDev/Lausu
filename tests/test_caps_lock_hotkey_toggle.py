"""Caps Lock hotkey must reach the toggle callback (native listeners).

Regression: windows-key-listener.c / macos-key-listener.swift swallowed
KEY_UP after suppressing KEY_DOWN (OS Caps toggle) WITHOUT emitting the
wire event, so toggle-on-keyup never fired and PTT never stopped.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_C = REPO_ROOT / "voice_typer" / "server" / "native" / "windows-key-listener.c"
MACOS_SWIFT = (
    REPO_ROOT / "voice_typer" / "server" / "native" / "macos-key-listener.swift"
)


def test_windows_listener_emits_keyup_before_swallow() -> None:
    """KEY_UP wire event must be emitted BEFORE the suppressed-keyup early return."""
    src = WINDOWS_C.read_text(encoding="utf-8")
    keyup_block_start = src.find("WM_KEYUP || wParam == WM_SYSKEYUP")
    assert keyup_block_start != -1, "windows-key-listener.c must handle KEY_UP"
    keyup_block = src[keyup_block_start : keyup_block_start + 1200]
    first_emit = keyup_block.find("emit(")
    first_swallow_return = keyup_block.find("return 1;")
    assert first_emit != -1, "KEY_UP block must emit a wire event"
    assert first_swallow_return != -1, "KEY_UP block may still swallow for the OS"
    assert first_emit < first_swallow_return, (
        "KEY_UP must be emitted BEFORE the suppressed-keyup swallow "
        "(otherwise toggle-on-keyup / PTT-release never fires)"
    )
    assert 'KEY_UP:%s' in keyup_block or "KEY_UP:" in keyup_block


def test_windows_listener_keydown_emits_before_swallow() -> None:
    """KEY_DOWN wire event must also be emitted BEFORE the suppression swallow."""
    src = WINDOWS_C.read_text(encoding="utf-8")
    keydown_block_start = src.find("WM_KEYDOWN || wParam == WM_SYSKEYDOWN")
    assert keydown_block_start != -1, "windows-key-listener.c must handle KEY_DOWN"
    keydown_block = src[keydown_block_start : keydown_block_start + 1200]
    first_emit = keydown_block.find("emit(")
    first_swallow_return = keydown_block.find("return 1;")
    assert first_emit != -1, "KEY_DOWN block must emit a wire event"
    assert first_swallow_return != -1
    assert first_emit < first_swallow_return, (
        "KEY_DOWN must be emitted BEFORE the suppression swallow "
        "(otherwise Caps toggle / PTT start never fires)"
    )


def test_windows_listener_keyup_swallow_gated_on_suppressed_vk() -> None:
    """Only the matching suppressed keyDown's keyUp is swallowed (orphan guard)."""
    src = WINDOWS_C.read_text(encoding="utf-8")
    keyup_block_start = src.find("WM_KEYUP || wParam == WM_SYSKEYUP")
    assert keyup_block_start != -1
    keyup_block = src[keyup_block_start : keyup_block_start + 1200]
    assert "g_suppressed_vk == vk" in keyup_block, (
        "KEY_UP swallow must be gated on the remembered suppressed keyDown VK"
    )


def test_macos_listener_emits_keyup_before_swallow() -> None:
    """macOS CGEventTap must emit KEY_UP before returning nil on suppressed keyup."""
    src = MACOS_SWIFT.read_text(encoding="utf-8")
    keyup_case = src.find("case .keyUp:")
    assert keyup_case != -1, "macos-key-listener.swift must handle keyUp"
    block = src[keyup_case : keyup_case + 900]
    first_emit = block.find("emit(")
    first_swallow = block.find("return nil")
    assert first_emit != -1, "keyUp case must emit KEY_UP"
    assert first_swallow != -1
    assert first_emit < first_swallow, (
        "KEY_UP must be emitted BEFORE the suppressed-keyup swallow on macOS"
    )
    assert "suppressedKeyCode" in block, (
        "keyUp swallow must be gated on the remembered suppressed keyDown"
    )


def _make_matching_backend(
    *,
    hotkey: str = "CapsLock",
    toggle_on_keyup: bool = True,
    on_release: object | None = None,
    is_caps_lock: bool = True,
):
    """Minimal _MatchingMixin stand-in for isolated fire-point checks."""
    import threading

    from voice_typer.server.native_hotkeys._matching import _MatchingMixin

    class _Fake(_MatchingMixin):
        platform_name = "test"

        def __init__(self) -> None:
            self._match_lock = threading.Lock()
            self._held_modifiers: set[str] = set()
            self._fn_down = False
            self._main_key_down = False
            self._parsed = {
                "modifiers": set(),
                "main_key": hotkey,
                "is_fn_only": False,
                "is_modifier_only": False,
                "is_caps_lock": is_caps_lock,
            }
            self._extra_matchers: list = []
            self._on_release_callback = on_release
            self._toggle_on_keyup = toggle_on_keyup
            self.fired: list[str] = []
            self.released: list[str] = []
            self._callback = lambda: self.fired.append("toggle")
            if on_release is not None:
                self._on_release_callback = lambda: self.released.append("stop")

    return _Fake()


def test_matching_fires_caps_lock_toggle_on_keydown() -> None:
    """Caps Lock + toggle_on_keyup fires on KEY_DOWN (KEY_UP may never arrive)."""
    b = _make_matching_backend(toggle_on_keyup=True, on_release=None)
    b._on_key_event("CapsLock", down=True)
    assert b.fired == ["toggle"], f"expected toggle on KEY_DOWN, got {b.fired}"
    b._on_key_event("CapsLock", down=False)
    assert b.fired == ["toggle"], f"KEY_UP must not double-fire, got {b.fired}"


def test_matching_caps_lock_ptt_start_on_down_stop_on_up() -> None:
    """Caps Lock + PTT uses ordinary edges: KEY_DOWN starts, KEY_UP stops."""
    b = _make_matching_backend(toggle_on_keyup=False, on_release=object())
    b._on_key_event("CapsLock", down=True)
    assert b.fired == ["toggle"]
    assert b.released == []
    b._on_key_event("CapsLock", down=False)
    assert b.fired == ["toggle"]
    assert b.released == ["stop"], f"KEY_UP must stop PTT, got {b.released}"


def test_matching_caps_lock_legacy_toggle_fires_on_keydown() -> None:
    """Caps Lock + legacy toggle (toggle_on_keyup False) fires on KEY_DOWN."""
    b = _make_matching_backend(toggle_on_keyup=False, on_release=None)
    b._on_key_event("CapsLock", down=True)
    assert b.fired == ["toggle"]
    b._on_key_event("CapsLock", down=False)
    assert b.fired == ["toggle"], f"legacy toggle ignores KEY_UP, got {b.fired}"


def test_matching_caps_special_case_requires_empty_modifiers() -> None:
    """Caps + a modifier keeps ordinary toggle_on_keyup (fire on KEY_UP)."""
    b = _make_matching_backend(toggle_on_keyup=True, on_release=None)
    b._parsed["modifiers"] = {"ctrl"}
    b._on_modifier_event("Ctrl", down=True)
    b._on_key_event("CapsLock", down=True)
    assert b.fired == [], "combo must not take the Caps-only KEY_DOWN special case"
    b._on_key_event("CapsLock", down=False)
    assert b.fired == ["toggle"]
