"""Native hotkey backend, {name}.

Event-kind routing
~~~~~~~~~~~~~~~~~~
Each registered spec answers to ONE wire event kind, so a matcher can
never fire off an event that does not belong to it:

* ``is_fn_only`` specs -> ``FN_DOWN`` / ``FN_UP``;
* ``is_modifier_only`` specs -> ``MOD_DOWN`` / ``MOD_UP``;
* single-key / combo specs -> ``KEY_DOWN`` / ``KEY_UP`` of the main key.

Fire point
~~~~~~~~~~
Actions fire on RELEASE: key-up / mod-up / fn-up. Key-down only arms the
press cycle (and starts the recording in push-to-talk). Hold autorepeat
never re-fires: a repeat is a KEY/MOD/FN down that arrives while that key
is already tracked as held, and it is dropped before matching.

Caps Lock
~~~~~~~~~
Windows and Linux listeners emit ``KEY_UP:CapsLock`` before swallowing the
suppressed key, so Caps Lock fires on release like every other key. The
macOS listener cannot: Caps Lock is delivered as a ``flagsChanged`` event
with no key-up at all (``macos-key-listener.swift`` maps key code 57 to
``nil`` in ``nameForCGEvent``, so the CGEventTap never emits a
``KEY_UP:CapsLock`` either). The release is therefore synthesized after a
short quiet window, for EVERY Caps Lock spec -- bare ``<caps_lock>`` and
combined ones like ``<ctrl>+<caps_lock>`` alike. Without that the default
hotkey would fire once per session, the press latch never being cleared by
a KEY_UP that macOS never sends, and a combined Caps Lock hotkey would
never fire at all.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from voice_typer.server.native_hotkeys.modifiers import (
    _canonical_modifier,
    _canonical_modifier_name_for_token,
)

log = logging.getLogger(__name__)

_WIRE_EVENT_KINDS = frozenset({"key", "mod", "fn"})


class _MatchingMixin:
    # Members provided by the composed ``SubprocessHotkeyBackend``
    platform_name: str
    _match_lock: threading.Lock
    _held_modifiers: set[str]
    _fn_down: bool
    _main_key_down: bool
    _held_keys: set[str]
    _armed_roles: set[str]
    _stopped_roles: set[str]
    _caps_release_timer: threading.Timer | None
    _parsed: dict[str, Any] | None
    _extra_matchers: list[dict[str, Any]]
    _on_release_callback: Callable[[], None] | None

    # Quiet window used to synthesize the Caps Lock release on platforms
    # whose listener never emits KEY_UP:CapsLock (macOS only).
    _CAPS_RELEASE_SYNTHESIS_SECONDS: float = 0.15

    def _reset_match_state(self) -> None:
        """Forget held keys/chords before a spawn or respawn."""
        self._cancel_caps_release_synthesis()
        with self._match_lock:
            self._held_modifiers.clear()
            self._held_keys.clear()
            self._fn_down = False
            self._main_key_down = False
            self._armed_roles.clear()
            self._stopped_roles.clear()

    def _on_fn_event(self, payload: str = "", *, down: bool) -> None:
        """Handle FN_DOWN / FN_UP. Used by the macOS backend only."""
        self._try_match("fn", down)

    def _on_modifier_event(self, mod_name: str, *, down: bool) -> None:
        """Handle MOD_DOWN / MOD_UP events."""
        canonical = _canonical_modifier(mod_name)
        if canonical is None:
            return
        with self._match_lock:
            if down:
                if canonical in self._held_modifiers:
                    return  # autorepeat of a held modifier
                self._held_modifiers.add(canonical)
            else:
                # A MOD_UP for a modifier we never saw go down still reaches
                # the matchers: the cycle is disarmed so no action can fire,
                # but a push-to-talk stop must never be gated on a press we
                # may have missed.
                self._held_modifiers.discard(canonical)
        self._try_match("mod", down)

    def _on_key_event(self, key_name: str, *, down: bool) -> None:
        """Handle KEY_DOWN / KEY_UP events."""
        with self._match_lock:
            if down:
                if key_name in self._held_keys:
                    return  # autorepeat of a held key
                self._held_keys.add(key_name)
            else:
                # A KEY_UP for a key we never saw go down still reaches the
                # matchers: the cycle is disarmed so the action cannot fire
                # twice, but a push-to-talk stop must never be gated on a
                # press we may have missed.
                self._held_keys.discard(key_name)
            self._main_key_down = bool(self._held_keys)
        self._try_match("key", down, key_name=key_name)
        if not down and key_name == "CapsLock":
            # A real release made the synthesized one unnecessary.
            self._cancel_caps_release_synthesis()

    def _try_match(
        self,
        event_kind: str,
        down: bool,
        *,
        key_name: str | None = None,
    ) -> None:
        """Check the current event against every registered hotkey spec."""
        # A different key pressed while a modifier-only chord is held means
        # the user is typing a shortcut, not tapping the hotkey. Cancel
        # BEFORE the matcher loop: an early return from another role would
        # otherwise skip it.
        if event_kind == "key" and down:
            self._cancel_armed_modifier_only()
        # Primary matcher (role "dictation"). Uses the legacy
        primary = {
            "role": "dictation",
            "parsed": self._parsed,
            "callback": getattr(self, "_callback", None),
            "on_release_callback": self._on_release_callback,
            "toggle_on_keyup": getattr(self, "_toggle_on_keyup", False),
        }
        if self._try_match_one(primary, event_kind, down, key_name=key_name):
            return
        # Extra matchers (roles "esc", "repaste", etc.). Each is
        for matcher in self._extra_matchers:
            if self._try_match_one(matcher, event_kind, down, key_name=key_name):
                return

    def _cancel_armed_modifier_only(self) -> None:
        """Disarm EVERY armed modifier-only cycle after an unrelated key press.

        Toggle roles just drop the arm (their action fires on the release,
        which would otherwise turn Alt+Tab into a dictation toggle). Push-
        to-talk roles fire their release once and record the role so the
        following modifier release cannot stop a second time.
        """
        matchers = [
            {
                "role": "dictation",
                "parsed": self._parsed,
                "on_release_callback": self._on_release_callback,
            },
            *self._extra_matchers,
        ]
        with self._match_lock:
            armed = set(self._armed_roles)
        for matcher in matchers:
            parsed = matcher.get("parsed")
            if not parsed or not parsed.get("is_modifier_only"):
                continue
            role = matcher.get("role", "dictation")
            if role not in armed:
                continue
            release_cb = matcher.get("on_release_callback")
            with self._match_lock:
                self._armed_roles.discard(role)
                if release_cb is not None:
                    self._stopped_roles.add(role)
            if release_cb is not None:
                self._fire_on_release_for(matcher)

    def _try_match_one(
        self,
        matcher: dict[str, Any],
        event_kind: str,
        down: bool,
        *,
        key_name: str | None = None,
    ) -> bool:
        """Try a single matcher against the current event.

        Returns True if the matcher matched (and fired its callback or
        decided to defer it to the release edge).

        A cycle is ARMED when the press completes the spec (the main key
        down with every required modifier held, or the last modifier of a
        modifier-only chord down). It fires on the matching release in any
        order, and it disarms so a duplicated release cannot fire twice.
        """
        parsed = matcher["parsed"]
        if parsed is None:
            return False
        if event_kind not in _WIRE_EVENT_KINDS:
            return False

        # FN-only hotkey (macOS Globe/Fn): own event kind, release fires.
        if parsed["is_fn_only"]:
            if event_kind != "fn":
                return False
            return self._arm_and_fire(matcher, down, complete=True)

        # Modifier-only hotkey (e.g. <alt>, or <ctrl>+<alt>)
        if parsed["is_modifier_only"]:
            if event_kind != "mod":
                return False
            required_canonical: set[str] = set()
            for token in parsed["modifiers"]:
                if token == "fn":
                    # Fn cannot complete a modifier-only chord here: the
                    # wire protocol has no Fn state for it, so only the
                    # non-Fn modifiers decide the match.
                    continue
                c = _canonical_modifier_name_for_token(token)
                if c is not None:
                    required_canonical.add(c)
            if not required_canonical:
                return False
            with self._match_lock:
                # The hotkey is "these exact modifiers and no others"
                complete = set(self._held_modifiers) == required_canonical
            return self._arm_and_fire(matcher, down, complete=complete)

        # Regular hotkey (single key or combo): own event kind, and the
        # event must carry its main key.
        if event_kind != "key":
            return False
        if key_name != parsed["main_key"]:
            return False

        required_mods = parsed["modifiers"]
        with self._match_lock:
            held_mods = set(self._held_modifiers)
            # For FN-containing combos, add 'fn' to held_mods if FN is down
            if self._fn_down:
                held_mods.add("fn")
        # The chord completes when every required modifier is held and
        # nothing else is (the shortcut is judged at the press, like the
        # OS does), then it fires at the release whatever is still held.
        complete = required_mods.issubset(held_mods) and not (held_mods - required_mods)
        return self._arm_and_fire(matcher, down, complete=complete)

    def _arm_and_fire(self, matcher: dict[str, Any], down: bool, *, complete: bool) -> bool:
        """Arm the cycle on a completing press, fire it on its release."""
        role = matcher.get("role", "dictation")
        with self._match_lock:
            if down:
                self._stopped_roles.discard(role)
                if not complete:
                    self._armed_roles.discard(role)
                    return False
                self._armed_roles.add(role)
            else:
                if role not in self._armed_roles:
                    # The chord-cancel already stopped this cycle; the
                    # remaining modifier release must not stop it again.
                    if role in self._stopped_roles:
                        self._stopped_roles.discard(role)
                        return True
                    # A stop is never gated on a press we may have missed
                    # (listener starting mid-press): push-to-talk must be
                    # able to end a recording whose press it never saw.
                    if matcher.get("on_release_callback") is not None:
                        self._fire_on_release_for(matcher)
                        return True
                    return False
                self._armed_roles.discard(role)
        return self._fire_edge(matcher, down)

    def _fire_edge(self, matcher: dict[str, Any], down: bool) -> bool:
        """Fire one matched edge: release owns the action.

        * push-to-talk (``on_release_callback``): press starts, release stops;
        * ``toggle_on_keyup``: press is deferred, release fires the action;
        * legacy press-fire (neither): fires on press, release is a no-op.
        """
        release_cb = matcher.get("on_release_callback")
        deferred = bool(matcher.get("toggle_on_keyup", False))
        if down:
            if release_cb is not None:
                # Push-to-talk: start recording on press.
                self._fire_callback_for(matcher)
            elif not deferred:
                # Legacy toggle (e.g. a role not wired for release firing)
                self._fire_callback_for(matcher)
            # else: release-firing mode, the action waits for the release
            self._arm_caps_release_synthesis_if_needed(matcher)
            return True
        if release_cb is not None:
            # Push-to-talk: stop recording on release.
            self._fire_on_release_for(matcher)
        elif deferred:
            # Release-firing mode: the action fires exactly once here.
            self._fire_callback_for(matcher)
        # else: legacy press-fire, nothing to do on release
        return True

    # Caps Lock release synthesis ──────────────────────────────────────

    def _arm_caps_release_synthesis_if_needed(self, matcher: dict[str, Any]) -> None:
        """Arm the macOS-only Caps Lock release fallback (see module docs).

        Windows and Linux listeners emit ``KEY_UP:CapsLock``, which cancels
        this timer through the normal release path; arming it there would
        make a held Caps Lock fire while still down.

        Every Caps Lock spec is covered, combined ones included: macOS
        sends no ``KEY_UP:CapsLock`` for ``<ctrl>+<caps_lock>`` either, so
        skipping those left the hotkey permanently dead.
        """
        if self.platform_name != "macOS":
            return
        parsed = matcher.get("parsed")
        if not parsed or not parsed.get("is_caps_lock"):
            return
        if matcher.get("on_release_callback") is not None:
            return  # push-to-talk needs a real release, never a guess
        if not matcher.get("toggle_on_keyup", False):
            return
        with self._match_lock:
            if self._caps_release_timer is not None:
                return
            timer = threading.Timer(self._CAPS_RELEASE_SYNTHESIS_SECONDS, self._synthesize_caps_release)
            # RACE-008: daemon because a queued release synthesis must never
            # hold up process exit; it is cancelled on every real KEY_UP.
            timer.daemon = True
            self._caps_release_timer = timer
        timer.start()
        log.debug(
            "[NATIVE-HOTKEY] %s Caps Lock release synthesis armed (%.3fs)",
            self.platform_name,
            self._CAPS_RELEASE_SYNTHESIS_SECONDS,
        )

    def _synthesize_caps_release(self) -> None:
        """Fire the Caps Lock release the OS will never deliver (macOS)."""
        with self._match_lock:
            timer = self._caps_release_timer
            self._caps_release_timer = None
            if "CapsLock" not in self._held_keys:
                return  # a real KEY_UP already closed the cycle
            self._held_keys.discard("CapsLock")
            self._main_key_down = bool(self._held_keys)
        if timer is not None:
            timer.cancel()
        log.debug(
            "[NATIVE-HOTKEY] %s synthesized the Caps Lock release",
            self.platform_name,
        )
        self._try_match("key", False, key_name="CapsLock")

    def _cancel_caps_release_synthesis(self) -> None:
        """Drop a pending Caps Lock release synthesis (real release/stop)."""
        with self._match_lock:
            timer = self._caps_release_timer
            self._caps_release_timer = None
        if timer is not None:
            timer.cancel()

    # Callback invocation ──────────────────────────────────────────────

    def _fire_callback(self) -> None:
        """Invoke the press callback (with exception shielding)."""
        primary = {
            "role": "dictation",
            "callback": getattr(self, "_callback", None),
        }
        self._fire_callback_for(primary)

    def _fire_callback_for(self, matcher: dict[str, Any]) -> None:
        """Invoke ``matcher["callback"]`` with exception shielding."""
        cb = matcher.get("callback")
        if cb is None:
            return
        role = matcher.get("role", "dictation")
        try:
            cb()
        except Exception:
            log.exception(
                "[NATIVE-HOTKEY] Press callback raised in %s backend (role=%s)",
                self.platform_name,
                role,
            )

    def _fire_on_release(self) -> None:
        """Invoke the release callback (push-to-talk mode)."""
        primary = {
            "role": "dictation",
            "on_release_callback": self._on_release_callback,
        }
        self._fire_on_release_for(primary)

    def _fire_on_release_for(self, matcher: dict[str, Any]) -> None:
        """Invoke ``matcher["on_release_callback"]`` with exception
        shielding. Shared by the primary and extra matchers."""
        cb = matcher.get("on_release_callback")
        if cb is None:
            return
        role = matcher.get("role", "dictation")
        try:
            cb()
        except Exception:
            log.exception(
                "[NATIVE-HOTKEY] Release callback raised in %s backend (role=%s)",
                self.platform_name,
                role,
            )
