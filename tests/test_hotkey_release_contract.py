"""Hotkey actions fire on KEY RELEASE (key-up), never on key-down.

Contract pinned here (backend ``native_hotkeys/_matching.py`` + the
dispatcher role wiring):

* every non-push-to-talk action fires once when the chord is released;
  key-down only arms the cycle, never fires;
* push-to-talk keeps its hold semantics: start on press, stop on release;
* a held key / held modifier never re-fires on autorepeat;
* one fire per press-release cycle whatever the release order, and a
  duplicated KEY_UP line cannot double-fire;
* macOS never delivers KEY_UP for Caps Lock (``macos-key-listener.swift``
  emits KEY_DOWN from flagsChanged only), so the release is synthesized
  after a short quiet window instead of leaving the default hotkey dead.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tests.test_native_hotkeys_autorepeat import (
    _make_linux_backend,
    _make_macos_backend,
)


class TestModifierOnlyFiresOnRelease:
    """``<alt>`` / ``<ctrl>+<alt>`` fire when the modifier is released."""

    def test_toggle_defers_to_mod_up(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<alt>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Alt")
        assert fired == [], "MOD_DOWN must not fire the toggle"
        b._handle_line("MOD_UP:Alt")
        assert fired == ["toggle"], f"toggle must fire on release, got {fired}"

    def test_ptt_starts_on_press_stops_on_release(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<alt>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))  # noqa: E731
        b._handle_line("MOD_DOWN:Alt")
        assert started == ["start"], "PTT starts on press"
        assert stopped == []
        b._handle_line("MOD_UP:Alt")
        assert stopped == ["stop"], "PTT must stop on release, not hang until the safety timer"

    def test_two_modifier_chord_releases_once(self, monkeypatch):
        """``<ctrl>+<alt>`` fires once, on the first release of the chord.

        A modifier-only chord has no main key to wait for, so letting go
        of ANY part of it ends the gesture; the remaining release is a
        no-op, which keeps one fire per press-release cycle.
        """
        b = _make_linux_backend(monkeypatch, "<ctrl>+<alt>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("MOD_DOWN:Alt")
        assert fired == [], "key-down must not fire the toggle"
        b._handle_line("MOD_UP:Alt")
        assert fired == ["toggle"], f"expected one fire on the first release, got {fired}"
        b._handle_line("MOD_UP:Ctrl")
        assert fired == ["toggle"], f"second release must not re-fire, got {fired}"

    def test_autorepeat_of_held_modifier_never_refires(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<alt>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Alt")
        b._handle_line("MOD_DOWN:Alt")
        b._handle_line("MOD_DOWN:Alt")
        b._handle_line("MOD_UP:Alt")
        assert fired == ["toggle"], f"one press-release cycle must fire once, got {fired}"

    def test_extra_modifier_blocks_the_release(self, monkeypatch):
        """Holding an unrequired modifier means the exact chord never matched."""
        b = _make_linux_backend(monkeypatch, "<alt>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("MOD_DOWN:Alt")
        b._handle_line("MOD_UP:Alt")
        assert fired == []

    def test_unrelated_key_release_does_not_fire_modifier_only(self, monkeypatch):
        """Typing while the hotkey modifier is held must not fire it.

        The old matcher evaluated modifier-only specs on KEY events too,
        so releasing any unrelated key while Alt was held fired the hotkey.
        """
        b = _make_linux_backend(monkeypatch, "<alt>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Alt")
        b._handle_line("KEY_DOWN:Q")
        b._handle_line("KEY_UP:Q")
        assert fired == [], "an unrelated key release must never fire a modifier-only hotkey"
        b._handle_line("MOD_UP:Alt")
        assert fired == ["toggle"]


class TestFnOnlyFiresOnRelease:
    """macOS ``<fn>`` (Globe) follows the same release contract."""

    def test_toggle_defers_to_fn_up(self, monkeypatch):
        b = _make_macos_backend(monkeypatch, "<fn>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("FN_DOWN")
        assert fired == [], "FN_DOWN must not fire the toggle"
        b._handle_line("FN_UP")
        assert fired == ["toggle"], f"toggle must fire on Fn release, got {fired}"

    def test_ptt_starts_on_press_stops_on_fn_up(self, monkeypatch):
        b = _make_macos_backend(monkeypatch, "<fn>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))  # noqa: E731
        b._handle_line("FN_DOWN")
        assert started == ["start"]
        b._handle_line("FN_UP")
        assert stopped == ["stop"]

    def test_ptt_stop_is_never_gated_on_a_press_we_missed(self, monkeypatch):
        """A release whose press the listener never saw still stops PTT.

        Otherwise a listener that starts mid-press would leave the
        recording running until the safety timer.
        """
        b = _make_macos_backend(monkeypatch, "<fn>")
        stopped: list[str] = []
        b.set_on_release(lambda: stopped.append("stop"))  # noqa: E731
        b._handle_line("FN_UP")
        assert stopped == ["stop"], "the stop must not depend on a seen press"


class TestCapsLockFiresOnRelease:
    """Caps Lock alone follows the release contract on every platform."""

    def test_keydown_never_fires_and_keyup_fires_once(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == [], "key-down must not fire the toggle"
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"], f"toggle must fire on release, got {fired}"
        # A duplicated KEY_UP line cannot fire a second time.
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"], f"one press-release cycle fires once, got {fired}"

    def test_autorepeat_while_held_never_refires(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"], f"got {fired}"

    def test_fresh_press_after_release_fires_again(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle", "toggle"]

    def test_ptt_still_starts_on_press_and_stops_on_release(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        assert started == ["start"], "push-to-talk keeps hold semantics"
        b._handle_line("KEY_UP:CapsLock")
        assert stopped == ["stop"]

    def test_macos_synthesizes_the_release_caps_lock_has_no_key_up(self, monkeypatch):
        """macOS emits KEY_DOWN:CapsLock only, so the release is synthesized.

        Without this the default hotkey would fire once per session: the
        press latch is only cleared by a KEY_UP the macOS listener never
        sends (``macos-key-listener.swift``, Caps Lock is flagsChanged-only).
        """
        b = _make_macos_backend(monkeypatch, "<caps_lock>")
        b._CAPS_RELEASE_SYNTHESIS_SECONDS = 0.02
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")  # repeat / release-flag line, ignored
        assert fired == [], "must not fire on key-down"
        b._caps_release_timer.join(timeout=1.0)
        assert fired == ["toggle"], f"synthesized release must fire once, got {fired}"
        # A late KEY_UP (should macOS ever deliver one) cannot double-fire.
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"]
        # And the next press is a fresh cycle.
        b._handle_line("KEY_DOWN:CapsLock")
        b._caps_release_timer.join(timeout=1.0)
        assert fired == ["toggle", "toggle"]

    def test_windows_and_linux_never_arm_the_synthesis_timer(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        b._callback = lambda: None  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        assert b._caps_release_timer is None, "platforms that deliver KEY_UP:CapsLock must fire on the real release"

    def test_macos_synthesizes_the_release_for_a_caps_lock_combo(self, monkeypatch):
        """A Caps Lock COMBO must fire too, not just the bare key.

        macOS never delivers ``KEY_UP:CapsLock`` (``nameForCGEvent`` maps
        key code 57 to ``nil``), so the release of ``<ctrl>+<caps_lock>``
        is synthesized exactly like the bare ``<caps_lock>`` one. The
        synthesis used to be skipped for specs carrying modifiers, which
        left every combined Caps Lock hotkey permanently dead on macOS.
        """
        b = _make_macos_backend(monkeypatch, "<ctrl>+<caps_lock>")
        b._CAPS_RELEASE_SYNTHESIS_SECONDS = 0.02
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == [], "must not fire on key-down"
        b._caps_release_timer.join(timeout=1.0)
        assert fired == ["toggle"], f"synthesized release must fire once, got {fired}"
        # A second tap is a fresh cycle.
        b._handle_line("KEY_DOWN:CapsLock")
        b._caps_release_timer.join(timeout=1.0)
        assert fired == ["toggle", "toggle"], f"got {fired}"


class TestComboSingleFlight:
    """One fire per press-release cycle, whatever the release order."""

    def test_release_modifier_first_fires_once(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<ctrl>+v")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("KEY_DOWN:V")
        b._handle_line("MOD_UP:Ctrl")
        b._handle_line("KEY_UP:V")
        assert fired == ["toggle"], f"got {fired}"

    def test_release_main_key_first_fires_once(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<ctrl>+v")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("KEY_DOWN:V")
        b._handle_line("KEY_UP:V")
        b._handle_line("MOD_UP:Ctrl")
        assert fired == ["toggle"], f"got {fired}"

    def test_partial_release_and_repress_is_a_new_cycle(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<ctrl>+v")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("KEY_DOWN:V")
        b._handle_line("KEY_UP:V")
        b._handle_line("KEY_DOWN:V")
        b._handle_line("KEY_UP:V")
        assert fired == ["toggle", "toggle"], f"got {fired}"

    def test_unrelated_key_edges_do_not_swallow_the_release(self, monkeypatch):
        """An unrelated key pressed and released mid-chord keeps the cycle alive."""
        b = _make_linux_backend(monkeypatch, "<ctrl>+v")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("KEY_DOWN:V")
        b._handle_line("KEY_DOWN:Q")
        b._handle_line("KEY_UP:Q")
        b._handle_line("KEY_UP:V")
        assert fired == ["toggle"], f"got {fired}"

    def test_duplicate_keyup_cannot_double_fire(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<f2>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:F2")
        b._handle_line("KEY_UP:F2")
        b._handle_line("KEY_UP:F2")
        assert fired == ["toggle"], f"got {fired}"


class TestDispatcherWiresEveryRoleToKeyUp:
    """ESC and repaste actions fire on release too, not only dictation."""

    def test_pool_aux_into_shared_enables_keyup_for_the_role(self):
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        dispatcher = HotkeyDispatcher(MagicMock())
        shared = MagicMock()
        shared._state = "NATIVE"
        shared._native = MagicMock()
        dispatcher._shared_backend = shared

        assert dispatcher._pool_aux_into_shared("repaste", "<ctrl>+<alt>+v", MagicMock(), None)
        shared._native.add_extra_matcher.assert_called_once_with("repaste", "<ctrl>+<alt>+v")
        shared._native.set_role_toggle_on_keyup.assert_called_once_with("repaste", True)

    def test_repool_after_shared_swap_keeps_keyup_for_the_role(self):
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        dispatcher = HotkeyDispatcher(MagicMock())
        shared = MagicMock()
        shared._state = "NATIVE"
        shared._native = MagicMock()
        dispatcher._shared_backend = shared
        dispatcher._esc_spec = "<esc>"
        dispatcher._esc_callback = MagicMock()
        dispatcher._repaste_spec = "<ctrl>+<alt>+v"
        dispatcher._repaste_callback = MagicMock()

        dispatcher._repool_aux_into_shared()

        assert shared._native.set_role_toggle_on_keyup.call_count == 2
        shared._native.set_role_toggle_on_keyup.assert_any_call("esc", True)
        shared._native.set_role_toggle_on_keyup.assert_any_call("repaste", True)

    def test_register_esc_enables_keyup_on_the_standalone_backend(self, monkeypatch):
        from voice_typer.server import hotkey_dispatcher as facade
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        aux = MagicMock()
        aux.is_alive.return_value = True
        monkeypatch.setattr(facade, "create_hotkey_backend", lambda *a, **k: aux)

        dispatcher = HotkeyDispatcher(MagicMock())
        dispatcher.register_esc()

        aux.set_toggle_on_keyup.assert_called_with(True)

    def test_register_repaste_enables_keyup_on_the_standalone_backend(self, monkeypatch):
        from voice_typer.server import hotkey_dispatcher as facade
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        aux = MagicMock()
        aux.is_alive.return_value = True
        monkeypatch.setattr(facade, "create_hotkey_backend", lambda *a, **k: aux)

        app = MagicMock()
        app.config.repaste_hotkey = "<ctrl>+<alt>+u"
        dispatcher = HotkeyDispatcher(app)
        dispatcher.register_repaste()

        aux.set_toggle_on_keyup.assert_called_with(True)

    def test_repaste_sharing_the_dictation_key_is_disabled(self, monkeypatch):
        """One key cannot own two actions: the first matcher wins silently.

        A duplicate spec would leave repaste dead with no trace, so the
        registration disables it and says why in the log.
        """
        from voice_typer.server import hotkey_dispatcher as facade
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        aux = MagicMock()
        aux.is_alive.return_value = True
        monkeypatch.setattr(facade, "create_hotkey_backend", lambda *a, **k: aux)

        app = MagicMock()
        app.config.hotkey = "<f2>"
        app.config.repaste_hotkey = "<f2>"
        dispatcher = HotkeyDispatcher(app)
        dispatcher.register_repaste()

        assert app.config.repaste_hotkey == "", "duplicate spec must be cleared"
        aux.start.assert_not_called()


class TestStartupReconciliation:
    """Startup never leaves a dead or invalid hotkey silently."""

    def test_invalid_hotkey_reconciles_to_default_with_one_warning(self, monkeypatch, caplog):
        import logging

        from voice_typer.server import hotkey_dispatcher as facade
        from voice_typer.server.config import DEFAULT_HOTKEY
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        backend = MagicMock()
        backend.is_alive.return_value = True
        monkeypatch.setattr(facade, "create_hotkey_backend", lambda *a, **k: backend)

        app = MagicMock()
        # An OS-reserved hotkey left behind in config.json (the picker
        # rejects it, a hand-edited file does not).
        app.config.hotkey = "<alt>+<tab>"
        app.config.esc_cancel_enabled = False
        app.config.repaste_hotkey = ""
        app.config.recording_mode = "toggle"

        dispatcher = HotkeyDispatcher(app)
        with caplog.at_level(logging.WARNING, logger="voice_typer.server.hotkey_dispatcher"):
            assert dispatcher.register() is True

        assert app.config.hotkey == DEFAULT_HOTKEY, "stale hotkey must reconcile to the default"
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, f"exactly one WARNING expected, got {warnings}"
        assert "falling back to default" in warnings[0]
        assert backend.start.called, "the default hotkey must actually be registered"

    def test_registration_failure_surfaces_exactly_once(self, monkeypatch, caplog):
        import logging

        from voice_typer.server import hotkey_dispatcher as facade
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        def _boom(*args, **kwargs):
            raise RuntimeError("another app holds this hotkey")

        monkeypatch.setattr(facade, "create_hotkey_backend", _boom)

        app = MagicMock()
        app.config.hotkey = "<caps_lock>"
        app.config.esc_cancel_enabled = False
        app.config.repaste_hotkey = ""
        app.config.recording_mode = "toggle"

        dispatcher = HotkeyDispatcher(app)
        with caplog.at_level(logging.WARNING, logger="voice_typer.server.hotkey_dispatcher"):
            assert dispatcher.register() is False

        assert dispatcher._hotkey_backend is None, "no half-installed backend"
        assert app.tray.notify.call_count == 1, "the user hears about it exactly once"
        assert any("Registration FAILED" in r.getMessage() for r in caplog.records)
