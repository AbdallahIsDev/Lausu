"""All heavy dependencies are mocked via the project-wide ``mock_heavy_imports``"""

import sys
from unittest.mock import MagicMock


class TestHotkeyMapping:
    """Verify the hotkey registration uses the new backend abstraction."""

    def test_register_hotkey_creates_backend(self, app, monkeypatch):
        """_register_hotkey should create a hotkey backend and call start().

        Toggle mode fires on release (``set_toggle_on_keyup(True)``), so the
        pynput backend uses the manual ``Listener`` path, not the press-only
        ``GlobalHotKeys``.
        """
        mock_listener = MagicMock()
        mock_listener.is_alive.return_value = True
        mock_listener_cls = MagicMock(return_value=mock_listener)

        mock_kb = sys.modules["pynput.keyboard"]
        mock_kb.Listener = mock_listener_cls

        app.hotkeys.register()

        assert app.hotkeys._hotkey_backend is not None
        # Toggle-on-release forces the manual Listener (press-only GHK can't fire on release).
        assert mock_listener_cls.call_count >= 1
        assert mock_listener.start.call_count >= 1

    def test_register_hotkey_failure_does_not_crash(self, app):
        """If both GlobalHotKeys AND fallback Listener raise, app should not crash."""
        mock_kb = sys.modules["pynput.keyboard"]
        mock_kb.GlobalHotKeys = MagicMock(side_effect=Exception("no display"))
        mock_kb.Listener = MagicMock(side_effect=Exception("no input"))

        # Should not raise
        app.hotkeys.register()
        # Backend was created but start() failed -> not alive or None
        if app.hotkeys._hotkey_backend is not None:
            assert app.hotkeys._hotkey_backend.is_alive() is False

    def test_register_esc_hotkey_creates_and_starts_backend(self, app, monkeypatch):
        """_register_esc_hotkey should create a backend and call start().

        ESC fires on release (``set_toggle_on_keyup(True)``), so it takes the
        manual ``Listener`` path.
        """

        mock_listener = MagicMock()
        mock_listener.is_alive.return_value = True
        mock_listener_cls = MagicMock(return_value=mock_listener)

        mock_kb = sys.modules["pynput.keyboard"]
        mock_kb.Listener = mock_listener_cls

        assert app.hotkeys._esc_backend is None
        app.hotkeys.register_esc()

        assert app.hotkeys._esc_backend is not None
        mock_listener_cls.assert_called_once()
        assert app.hotkeys._esc_backend.is_alive() is True
        mock_listener.start.assert_called_once()

    def test_unregister_esc_hotkey_stops_and_clears_backend(self, app, monkeypatch):
        """_unregister_esc_hotkey should stop the backend and set it to None."""
        mock_backend = MagicMock()
        monkeypatch.setattr(
            "voice_typer.server.hotkey_dispatcher.create_hotkey_backend",
            MagicMock(return_value=mock_backend),
        )

        app.hotkeys.register_esc()
        assert app.hotkeys._esc_backend is mock_backend

        app.hotkeys.unregister_esc()

        assert app.hotkeys._esc_backend is None
        mock_backend.stop.assert_called_once()

    def test_unregister_esc_hotkey_noop_when_none(self, app):
        """_unregister_esc_hotkey should not crash when _esc_backend is None."""
        app.hotkeys._esc_backend = None
        app.hotkeys.unregister_esc()  # Must not raise

    def test_register_esc_hotkey_failure_does_not_crash(self, app, monkeypatch):
        """If ESC hotkey registration fails, app should not crash."""

        def failing_create(*args):
            raise RuntimeError("no display")

        monkeypatch.setattr("voice_typer.server.hotkey_dispatcher.create_hotkey_backend", failing_create)
        # Should not raise even though create_hotkey_backend raises
        app.hotkeys.register_esc()
        assert app.hotkeys._esc_backend is None

    def test_register_hotkey_includes_esc_when_enabled(self, app, monkeypatch):
        """When esc_cancel_enabled is True, _register_hotkey should also call _register_esc_hotkey."""

        mock_listener = MagicMock()
        mock_listener.is_alive.return_value = True
        mock_ghk_cls = MagicMock(return_value=mock_listener)

        mock_kb = sys.modules["pynput.keyboard"]
        mock_kb.GlobalHotKeys = mock_ghk_cls

        app.config.esc_cancel_enabled = True
        app.hotkeys.register()

        assert app.hotkeys._esc_backend is not None

    def test_dictation_callback_respects_hotkey_capture(self, app, monkeypatch):
        """HOTKEY-FIX-001: the dictation hotkey callback must"""
        from voice_typer.server.keyboard_ownership import keyboard_ownership

        # Build the callback via the dispatcher's helper
        callback = app.hotkeys._make_dictation_callback()
        assert callable(callback)

        # Track toggle_dictation calls
        toggle_called = {"n": 0}
        monkeypatch.setattr(app, "toggle_dictation", lambda: toggle_called.__setitem__("n", toggle_called["n"] + 1))

        # Case 1: ownership = normal → callback should fire toggle_dictation
        keyboard_ownership().set_owner("normal", reason="test")
        callback()
        assert toggle_called["n"] == 1, "callback should fire when capture is NOT active"

        # Case 2: ownership = hotkey_capture → callback should be a no-op
        keyboard_ownership().set_owner("hotkey_capture", reason="test capture")
        callback()
        assert toggle_called["n"] == 1, "callback must NOT fire when capture IS active"

        # Case 3: ownership back to normal → callback fires again
        keyboard_ownership().set_owner("normal", reason="test done")
        callback()
        assert toggle_called["n"] == 2, "callback should fire again after capture ends"

    def test_repaste_callback_respects_hotkey_capture(self, app, monkeypatch):
        """HOTKEY-FIX-001: the repaste hotkey callback must"""
        from voice_typer.server.keyboard_ownership import keyboard_ownership

        callback = app.hotkeys._make_repaste_callback()
        assert callable(callback)

        repaste_called = {"n": 0}
        monkeypatch.setattr(app, "repaste_last", lambda: repaste_called.__setitem__("n", repaste_called["n"] + 1))

        keyboard_ownership().set_owner("normal", reason="test")
        callback()
        assert repaste_called["n"] == 1

        keyboard_ownership().set_owner("hotkey_capture", reason="test capture")
        callback()
        assert repaste_called["n"] == 1, "repaste must NOT fire during capture"

        keyboard_ownership().set_owner("normal", reason="test done")
        callback()
        assert repaste_called["n"] == 2

    def test_register_hotkey_skips_esc_when_disabled(self, app, monkeypatch):
        """When esc_cancel_enabled is False, _register_hotkey should skip ESC registration."""

        mock_listener = MagicMock()
        mock_listener.is_alive.return_value = True
        mock_ghk_cls = MagicMock(return_value=mock_listener)

        mock_kb = sys.modules["pynput.keyboard"]
        mock_kb.GlobalHotKeys = mock_ghk_cls

        app.config.esc_cancel_enabled = False
        app.hotkeys.register()

        assert app.hotkeys._esc_backend is None

    def test_cancel_dictation_uses_canonical_ownership_not_legacy_flag(self, app, monkeypatch):
        """Regression: ESC cancel must work from the canonical KeyboardOwnership"""
        from voice_typer.server.keyboard_ownership import keyboard_ownership

        # Simulate the divergence: canonical owner is NORMAL but the legacy
        keyboard_ownership().set_owner("normal", reason="test")
        app._esc_cancel_paused = True

        cancel_called = {"n": 0}
        monkeypatch.setattr(app.recording, "cancel", lambda: cancel_called.__setitem__("n", cancel_called["n"] + 1))

        # ESC cancel must still fire despite the stale alias.
        app._cancel_dictation()
        assert cancel_called["n"] == 1, "ESC cancel must fire when canonical ownership is not hotkey_capture"

        # And must remain a no-op while a real capture is active.
        keyboard_ownership().set_owner("hotkey_capture", reason="capture")
        app._cancel_dictation()
        assert cancel_called["n"] == 1, "ESC cancel must NOT fire during real hotkey capture"


class TestFallbackHotkeyParser:
    """Verify parse_hotkey_to_vk correctly converts hotkey strings."""

    def test_parse_f2(self):
        from voice_typer.server.hotkeys import parse_hotkey_to_vk

        result = parse_hotkey_to_vk("<f2>")
        assert result == 0x71

    def test_parse_f1(self):
        from voice_typer.server.hotkeys import parse_hotkey_to_vk

        result = parse_hotkey_to_vk("<f1>")
        assert result == 0x70

    def test_parse_f12(self):
        from voice_typer.server.hotkeys import parse_hotkey_to_vk

        result = parse_hotkey_to_vk("<f12>")
        assert result == 0x7B


class TestHotkeyCallbackChain:
    """End-to-end: hotkey callback -> toggle_dictation -> _start_dictation."""

    def test_full_callback_chain(self, app):
        """Simulate the exact callback path: GlobalHotKeys fires toggle_dictation,"""
        app.recorder = MagicMock()
        app.recorder.recording = False
        app.tray = MagicMock()
        app._busy_event.set()  # not busy
        app.models.transcriber = MagicMock()
        app.models.transcriber.is_loaded = True

        # Simulate what GlobalHotKeys does: call the registered callback directly
        from voice_typer.server.tray import AppState

        # The callback stored in the hotkey mapping IS app.toggle_dictation
        app.toggle_dictation()

        app.recorder.start.assert_called_once()
        app.tray.set_state.assert_called_once()
        args = app.tray.set_state.call_args
        assert args[0][0] == AppState.RECORDING

    def test_callback_chain_register_then_fire(self, app, monkeypatch):
        """Register hotkey, extract the callback, call it, verify recording starts.

        Toggle mode fires on release, so the pynput backend takes the manual
        ``Listener`` path; the ownership-checking dictation callback is stored
        on the backend by ``start()``.
        """
        mock_listener = MagicMock()
        mock_listener.is_alive.return_value = True
        mock_kb = sys.modules["pynput.keyboard"]
        mock_kb.Listener = MagicMock(return_value=mock_listener)

        # NATIVE-001: force the legacy pynput backend (skip native binary)
        from voice_typer.server import native_hotkeys

        monkeypatch.setattr(native_hotkeys, "get_native_binary_path", lambda: None)

        app.recorder = MagicMock()
        app.recorder.recording = False
        app.tray = MagicMock()
        app._busy_event.set()  # not busy

        # Register hotkey - the backend stores the dictation callback.
        app.hotkeys.register()

        assert app.hotkeys._hotkey_backend is not None
        callback = app.hotkeys._hotkey_backend._user_callback
        # The callback is ownership-checking (keyboard_ownership gate).
        assert callable(callback)

        # Simulate the hotkey being pressed (ownership = normal → should fire)
        from voice_typer.server.keyboard_ownership import keyboard_ownership

        keyboard_ownership().set_owner("normal", reason="test")
        callback()

        from voice_typer.server.tray import AppState

        app.recorder.start.assert_called_once()
        args = app.tray.set_state.call_args
        assert args[0][0] == AppState.RECORDING
